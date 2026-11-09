from datetime import timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import STATUS_ACTIVE, STATUS_PENDING, has_permission
from app.crud.crud_user import get_user_by_email
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def auth_error(status_code: int, code: str, message: str, **extra) -> HTTPException:
    """Errores de acceso con un código que el frontend puede reconocer."""
    headers = {"WWW-Authenticate": "Bearer"} if status_code == status.HTTP_401_UNAUTHORIZED else None
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **extra}, headers=headers)


def get_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.InvalidTokenError:
        raise auth_error(401, "invalid_token", "Tu sesión expiró. Vuelve a iniciar sesión.")
    if not payload.get("sub"):
        raise auth_error(401, "invalid_token", "Tu sesión expiró. Vuelve a iniciar sesión.")
    return payload


def get_current_user(
    db: Session = Depends(get_db), payload: dict = Depends(get_token_payload)
) -> User:
    user = get_user_by_email(db, email=payload["sub"])
    if user is None:
        raise auth_error(401, "invalid_token", "Tu sesión expiró. Vuelve a iniciar sesión.")

    # Un cambio o recuperación de contraseña cierra las sesiones abiertas antes
    if user.password_changed_at:
        changed = int(user.password_changed_at.replace(tzinfo=timezone.utc).timestamp())
        if int(payload.get("iat", 0)) < changed:
            raise auth_error(401, "invalid_token", "Tu contraseña cambió. Vuelve a iniciar sesión.")

    if user.status == STATUS_PENDING:
        raise auth_error(403, "account_pending", "Tu cuenta todavía no ha sido aprobada por un administrador.")
    if user.status != STATUS_ACTIVE:
        raise auth_error(403, "account_disabled", "Tu cuenta está desactivada. Habla con un administrador.")
    return user


def require_permission(*modules: str):
    """Dependencia: el usuario debe tener al menos uno de los módulos indicados."""
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if not any(has_permission(current_user, m) for m in modules):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough privileges")
        return current_user
    return checker


def get_current_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough privileges")
    return current_user


# Nombre anterior: ahora significa "superadministrador"
get_current_admin_user = get_current_superadmin
