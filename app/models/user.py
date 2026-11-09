from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, false, func, text
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String(120), nullable=True)
    hashed_password = Column(String, nullable=False)
    # Se conserva por compatibilidad: "admin" para superadministradores, "user" para el resto
    role = Column(String, default="user", nullable=False)

    # Acceso al panel (ver app/core/permissions.py)
    status = Column(String(20), nullable=False, default="pending", server_default="pending", index=True)
    is_superadmin = Column(Boolean, nullable=False, default=False, server_default=false())
    permissions = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))

    created_at = Column(DateTime, nullable=True, server_default=func.now())
    approved_at = Column(DateTime, nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    last_login_at = Column(DateTime, nullable=True)

    # Bloqueo temporal por intentos fallidos
    failed_login_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    locked_until = Column(DateTime, nullable=True)

    # Los tokens emitidos antes de esta fecha dejan de valer (cambio o recuperación de contraseña)
    password_changed_at = Column(DateTime, nullable=True)

    # Recuperación de contraseña: se guarda el hash SHA-256 del token, nunca el token
    reset_token = Column(String, nullable=True, index=True)
    reset_token_expires = Column(DateTime, nullable=True)
