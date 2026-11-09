from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies import auth_error, get_current_user, get_token_payload
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import MODULES, STATUS_ACTIVE, STATUS_PENDING, effective_permissions, has_permission
from app.core.security import create_access_token, utcnow, verify_password, verify_password_timing_safe
from app.crud import crud_user
from app.models.user import User
from app.schemas.user import (
    ChangePasswordRequest,
    CurrentUser,
    PasswordRecoveryRequest,
    PasswordReset,
    RegisterRequest,
    Token,
)
from app.services import email as email_service

router = APIRouter()


def _issue_token(user: User, remember: bool = False, expires_at: datetime | None = None) -> str:
    if expires_at is None:
        delta = timedelta(days=settings.SESSION_REMEMBER_DAYS) if remember else timedelta(hours=settings.SESSION_HOURS)
        expires_at = datetime.now(timezone.utc) + delta
    return create_access_token(
        data={"sub": user.email, "role": user.role}, expires_at=expires_at
    )


def _current_user_out(user: User) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_superadmin=user.is_superadmin,
        permissions=effective_permissions(user),
        last_login_at=user.last_login_at,
    )


@router.post("/login", response_model=Token)
def login_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    remember: bool = Form(False),
) -> Token:
    """Inicio de sesión. Bloquea la cuenta un rato tras varios intentos fallidos seguidos."""
    user = crud_user.get_user_by_email(db, email=form_data.username)

    if user and crud_user.is_locked(user):
        minutes = max(1, int((user.locked_until - utcnow()).total_seconds() // 60) + 1)
        raise auth_error(
            423, "account_locked",
            f"Demasiados intentos fallidos. Vuelve a intentarlo en {minutes} min.", minutes=minutes,
        )

    if not verify_password_timing_safe(form_data.password, user.hashed_password if user else None):
        if user and crud_user.register_failed_login(db, user, settings.LOGIN_MAX_ATTEMPTS, settings.LOGIN_LOCK_MINUTES):
            raise auth_error(
                423, "account_locked",
                f"Demasiados intentos fallidos. Vuelve a intentarlo en {settings.LOGIN_LOCK_MINUTES} min.",
                minutes=settings.LOGIN_LOCK_MINUTES,
            )
        raise auth_error(400, "invalid_credentials", "Correo o contraseña incorrectos.")

    # La contraseña es correcta: ahora sí se puede decir en qué estado está la cuenta
    if user.status == STATUS_PENDING:
        raise auth_error(403, "account_pending", "Tu cuenta todavía no ha sido aprobada por un administrador.")
    if user.status != STATUS_ACTIVE:
        raise auth_error(403, "account_disabled", "Tu cuenta está desactivada. Habla con un administrador.")

    crud_user.register_successful_login(db, user)
    return Token(access_token=_issue_token(user, remember=remember), token_type="bearer")


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, background: BackgroundTasks, db: Session = Depends(get_db)) -> dict:
    """Crea una cuenta pendiente: un administrador debe aprobarla y elegir sus permisos."""
    if crud_user.get_user_by_email(db, email=payload.email):
        raise auth_error(400, "email_taken", "Ya existe una cuenta con ese correo.")

    user = crud_user.create_user(
        db, email=payload.email, password=payload.password, full_name=payload.full_name,
        status=STATUS_PENDING,
    )
    # Aviso por correo a quienes pueden aprobar (si el envío de correos está configurado)
    if settings.email_enabled:
        for approver in crud_user.get_users(db, status=STATUS_ACTIVE):
            if has_permission(approver, "users"):
                background.add_task(email_service.send_new_registration, approver.email, user.email, user.full_name)
    return {"message": "Solicitud enviada. Un administrador debe aprobar tu acceso."}


@router.get("/me", response_model=CurrentUser)
def read_current_user(current_user: User = Depends(get_current_user)) -> CurrentUser:
    return _current_user_out(current_user)


@router.get("/modules")
def list_modules() -> list[dict]:
    """Módulos del panel a los que se puede dar acceso."""
    return [{"key": key, "label": label} for key, label in MODULES.items()]


@router.post("/change-password", response_model=Token)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    token_payload: dict = Depends(get_token_payload),
) -> Token:
    """Cambia la contraseña propia. Devuelve un token nuevo; las demás sesiones se cierran."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise auth_error(400, "wrong_password", "La contraseña actual no es correcta.")
    if payload.current_password == payload.new_password:
        raise auth_error(400, "same_password", "La nueva contraseña debe ser distinta de la actual.")
    crud_user.set_password(db, current_user, payload.new_password)
    # La sesión actual sigue con la misma duración que tenía
    expires_at = datetime.fromtimestamp(token_payload["exp"], tz=timezone.utc)
    return Token(access_token=_issue_token(current_user, expires_at=expires_at), token_type="bearer")


@router.post("/recover-password")
def recover_password(
    request: PasswordRecoveryRequest, background: BackgroundTasks, db: Session = Depends(get_db)
) -> dict:
    """Envía por correo un enlace para elegir una contraseña nueva.

    La respuesta es la misma exista o no el correo, y el token nunca se devuelve aquí.
    """
    message = "Si el correo pertenece a una cuenta activa, te enviamos un enlace para restablecer la contraseña."
    if not settings.email_enabled:
        return {"message": message, "email_enabled": False}

    user = crud_user.get_user_by_email(db, email=request.email)
    if user and user.status == STATUS_ACTIVE:
        token = secrets.token_urlsafe(32)
        crud_user.set_password_reset_token(db, user, token, settings.PASSWORD_RESET_MINUTES)
        background.add_task(email_service.send_password_reset, user.email, token)
    return {"message": message, "email_enabled": True}


@router.get("/recover-password/status")
def recover_password_status() -> dict:
    """Le dice al frontend si la recuperación por correo está disponible."""
    return {"email_enabled": settings.email_enabled}


@router.post("/reset-password")
def reset_password_endpoint(request: PasswordReset, db: Session = Depends(get_db)) -> dict:
    """Elige una contraseña nueva con el enlace recibido por correo."""
    user = crud_user.get_user_by_reset_token(db, token=request.token)
    if not user:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_reset_token", "message": "El enlace no es válido o ya expiró. Pide uno nuevo."},
        )
    crud_user.set_password(db, user, request.new_password)
    return {"message": "Contraseña actualizada. Ya puedes iniciar sesión."}
