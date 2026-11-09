from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.permissions import STATUS_ACTIVE, STATUS_PENDING, clean_permissions
from app.core.security import get_password_hash, hash_token, utcnow
from app.models.user import User


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    # El correo se compara sin distinguir mayúsculas (sin LIKE: "%" o "_" no son comodines)
    query = select(User).where(func.lower(User.email) == email.strip().lower())
    result = db.execute(query)
    return result.scalars().first()


def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)


def _role_for(is_superadmin: bool) -> str:
    return "admin" if is_superadmin else "user"


def create_user(
    db: Session,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    permissions: Optional[list] = None,
    is_superadmin: bool = False,
    status: str = STATUS_PENDING,
    approved_by: Optional[User] = None,
) -> User:
    now = utcnow()
    db_user = User(
        email=email.strip().lower(),
        full_name=full_name,
        hashed_password=get_password_hash(password),
        role=_role_for(is_superadmin),
        status=status,
        is_superadmin=is_superadmin,
        permissions=clean_permissions(permissions),
        created_at=now,
        approved_at=now if status == STATUS_ACTIVE else None,
        approved_by_id=approved_by.id if approved_by else None,
        failed_login_attempts=0,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_users(db: Session, status: Optional[str] = None, skip: int = 0, limit: int = 500) -> List[User]:
    # Primero los pendientes de aprobación, luego por correo
    pending_first = case((User.status == STATUS_PENDING, 0), else_=1)
    query = select(User).order_by(pending_first, User.email)
    if status:
        query = query.where(User.status == status)
    result = db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


def count_active_superadmins(db: Session) -> int:
    query = select(User).where(User.is_superadmin.is_(True), User.status == STATUS_ACTIVE)
    return len(db.execute(query).scalars().all())


def set_password(db: Session, user: User, new_password: str) -> None:
    """Cambia la contraseña y cierra las sesiones abiertas con la anterior."""
    user.hashed_password = get_password_hash(new_password)
    user.password_changed_at = utcnow()
    user.reset_token = None
    user.reset_token_expires = None
    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)
    db.commit()
    db.refresh(user)


def set_password_reset_token(db: Session, user: User, token: str, minutes: int) -> None:
    user.reset_token = hash_token(token)
    user.reset_token_expires = utcnow() + timedelta(minutes=minutes)
    db.add(user)
    db.commit()


def get_user_by_reset_token(db: Session, token: str) -> Optional[User]:
    query = select(User).where(
        User.reset_token == hash_token(token),
        User.reset_token_expires > utcnow(),
    )
    return db.execute(query).scalars().first()


def register_failed_login(db: Session, user: User, max_attempts: int, lock_minutes: int) -> bool:
    """Suma un intento fallido; devuelve True si la cuenta quedó bloqueada."""
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    locked = False
    if user.failed_login_attempts >= max_attempts:
        user.locked_until = utcnow() + timedelta(minutes=lock_minutes)
        user.failed_login_attempts = 0
        locked = True
    db.add(user)
    db.commit()
    return locked


def register_successful_login(db: Session, user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    db.add(user)
    db.commit()


def is_locked(user: User, now: Optional[datetime] = None) -> bool:
    return bool(user.locked_until and user.locked_until > (now or utcnow()))


def update_user(db: Session, db_user: User, data: dict, actor: Optional[User] = None) -> User:
    """Aplica los cambios ya validados por la ruta (ver app/api/routes/users.py)."""
    if "email" in data and data["email"]:
        db_user.email = data["email"].strip().lower()
    if "full_name" in data:
        db_user.full_name = data["full_name"]
    if data.get("password"):
        db_user.hashed_password = get_password_hash(data["password"])
        db_user.password_changed_at = utcnow()
    if "permissions" in data and data["permissions"] is not None:
        db_user.permissions = clean_permissions(data["permissions"])
    if "is_superadmin" in data and data["is_superadmin"] is not None:
        db_user.is_superadmin = data["is_superadmin"]
        db_user.role = _role_for(data["is_superadmin"])
    if data.get("status"):
        if data["status"] == STATUS_ACTIVE and db_user.status != STATUS_ACTIVE and not db_user.approved_at:
            db_user.approved_at = utcnow()
            db_user.approved_by_id = actor.id if actor else None
        db_user.status = data["status"]
    if data.get("unlock"):
        db_user.failed_login_attempts = 0
        db_user.locked_until = None

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def approve_user(db: Session, db_user: User, permissions: list, is_superadmin: bool, actor: User) -> User:
    db_user.status = STATUS_ACTIVE
    db_user.permissions = clean_permissions(permissions)
    db_user.is_superadmin = is_superadmin
    db_user.role = _role_for(is_superadmin)
    db_user.approved_at = utcnow()
    db_user.approved_by_id = actor.id
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, db_user: User) -> None:
    db.delete(db_user)
    db.commit()
