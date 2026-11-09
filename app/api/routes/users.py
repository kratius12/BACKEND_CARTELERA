"""Gestión de usuarios del panel: aprobar registros, permisos por módulo, activar y desactivar.

Reglas (también para quien tiene el módulo "users" sin ser superadministrador):
- Solo un superadministrador puede dar o quitar "superadministrador" y el módulo "users",
  y solo él puede modificar o borrar a otro superadministrador.
- Quien no es superadministrador solo puede dar los módulos que él mismo tiene.
- Nadie puede desactivarse, borrarse ni quitarse su propio acceso a Usuarios.
- Siempre debe quedar al menos un superadministrador activo.
"""
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import MODULES, STATUS_ACTIVE, STATUS_PENDING, STATUSES, effective_permissions
from app.crud import crud_user
from app.models.user import User
from app.schemas.user import UserApprove, UserCreate, UserResponse, UserUpdate
from app.services import email as email_service

router = APIRouter()


def _out(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        status=user.status,
        is_superadmin=user.is_superadmin,
        permissions=effective_permissions(user),
        created_at=user.created_at,
        approved_at=user.approved_at,
        last_login_at=user.last_login_at,
        locked=crud_user.is_locked(user),
    )


def _forbid(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)


def _get_or_404(db: Session, user_id: int) -> User:
    user = crud_user.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return user


def _check_grants(actor: User, permissions: Optional[list], is_superadmin: Optional[bool], target: Optional[User] = None):
    """Valida que quien edita pueda dar esos permisos."""
    if actor.is_superadmin:
        return
    if is_superadmin:
        raise _forbid("Solo un superadministrador puede nombrar superadministradores.")
    if target is not None and target.is_superadmin:
        raise _forbid("Solo un superadministrador puede modificar a otro superadministrador.")
    if permissions is None:
        return
    current = set(target.permissions or []) if target is not None else set()
    changed = set(permissions) ^ current
    if "users" in changed:
        raise _forbid("Solo un superadministrador puede dar o quitar el acceso a Usuarios.")
    not_owned = changed - set(actor.permissions or [])
    if not_owned:
        names = ", ".join(MODULES[m] for m in sorted(not_owned))
        raise _forbid(f"No puedes dar ni quitar módulos que tú no tienes: {names}.")


def _keeps_a_superadmin(db: Session, target: User, will_be_superadmin: bool, will_be_active: bool) -> None:
    if target.is_superadmin and target.status == STATUS_ACTIVE and not (will_be_superadmin and will_be_active):
        if crud_user.count_active_superadmins(db) <= 1:
            raise HTTPException(status_code=400, detail="Debe quedar al menos un superadministrador activo.")


@router.get("/", response_model=List[UserResponse])
def list_all_users(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> List[UserResponse]:
    """Usuarios del panel; primero los pendientes de aprobación."""
    if status_filter and status_filter not in STATUSES:
        raise HTTPException(status_code=422, detail="Estado no válido")
    return [_out(u) for u in crud_user.get_users(db, status=status_filter)]


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_new_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> UserResponse:
    """Crea un usuario ya aprobado, con sus permisos."""
    if crud_user.get_user_by_email(db, email=user_in.email):
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo.")
    _check_grants(current, user_in.permissions, user_in.is_superadmin)
    user = crud_user.create_user(
        db,
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        permissions=user_in.permissions,
        is_superadmin=user_in.is_superadmin,
        status=STATUS_ACTIVE,
        approved_by=current,
    )
    return _out(user)


@router.post("/{user_id}/approve", response_model=UserResponse)
def approve_user(
    user_id: int,
    payload: UserApprove,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> UserResponse:
    """Aprueba una solicitud de registro con los módulos elegidos."""
    user = _get_or_404(db, user_id)
    if user.status != STATUS_PENDING:
        raise HTTPException(status_code=400, detail="Esta cuenta no está pendiente de aprobación.")
    _check_grants(current, payload.permissions, payload.is_superadmin, target=user)
    user = crud_user.approve_user(db, user, payload.permissions, payload.is_superadmin, actor=current)
    if settings.email_enabled:
        labels = [MODULES[m] for m in effective_permissions(user)]
        background.add_task(email_service.send_access_approved, user.email, labels)
    return _out(user)


@router.put("/{user_id}", response_model=UserResponse)
def update_existing_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
) -> UserResponse:
    """Edita datos, contraseña, permisos o estado; también desbloquea la cuenta."""
    user = _get_or_404(db, user_id)
    data = user_in.model_dump(exclude_unset=True)

    if user.status == STATUS_PENDING and data.get("status") == STATUS_ACTIVE:
        raise HTTPException(status_code=400, detail="Usa «Aprobar» para dar acceso a una solicitud pendiente.")

    is_self = user.id == current.id
    if is_self:
        if data.get("status") == "disabled":
            raise HTTPException(status_code=400, detail="No puedes desactivar tu propia cuenta.")
        if data.get("is_superadmin") is False and user.is_superadmin:
            raise HTTPException(status_code=400, detail="No puedes quitarte el permiso de superadministrador.")
        if data.get("permissions") is not None and "users" in (user.permissions or []) and "users" not in data["permissions"] and not user.is_superadmin:
            raise HTTPException(status_code=400, detail="No puedes quitarte el acceso a Usuarios.")

    _check_grants(current, data.get("permissions"), data.get("is_superadmin"), target=user)

    will_be_super = data["is_superadmin"] if data.get("is_superadmin") is not None else user.is_superadmin
    will_be_active = (data.get("status") or user.status) == STATUS_ACTIVE
    _keeps_a_superadmin(db, user, will_be_super, will_be_active)

    if data.get("email") and data["email"].lower() != user.email.lower():
        if crud_user.get_user_by_email(db, email=data["email"]):
            raise HTTPException(status_code=400, detail="Ese correo ya está registrado.")

    updated = crud_user.update_user(db, db_user=user, data=data, actor=current)
    return _out(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """Borra un usuario. También sirve para rechazar una solicitud pendiente."""
    if user_id == current.id:
        raise HTTPException(status_code=400, detail="No puedes borrar tu propia cuenta.")
    user = _get_or_404(db, user_id)
    if user.is_superadmin and not current.is_superadmin:
        raise _forbid("Solo un superadministrador puede borrar a otro superadministrador.")
    _keeps_a_superadmin(db, user, will_be_superadmin=False, will_be_active=False)
    crud_user.delete_user(db, user)
    return None
