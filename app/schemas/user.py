from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.permissions import clean_permissions

PASSWORD_MIN = 8


def _check_password(value: str) -> str:
    if len(value) < PASSWORD_MIN:
        raise ValueError(f"La contraseña debe tener al menos {PASSWORD_MIN} caracteres.")
    if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("La contraseña debe tener letras y números.")
    return value


def _check_name(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


# ─── Autenticación ───
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str

    @field_validator("full_name")
    @classmethod
    def _name(cls, v):
        return _check_name(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v):
        return _check_password(v)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password(cls, v):
        return _check_password(v)


class PasswordRecoveryRequest(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _password(cls, v):
        return _check_password(v)


class CurrentUser(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    is_superadmin: bool
    permissions: list[str]
    last_login_at: Optional[datetime] = None


# ─── Gestión de usuarios ───
Module = Literal["programs", "students", "groups", "assignments", "weekend", "sound", "talks", "reports", "users"]


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    full_name: Optional[str] = Field(default=None, max_length=120)
    password: str
    permissions: list[Module] = []
    is_superadmin: bool = False

    @field_validator("full_name")
    @classmethod
    def _name(cls, v):
        return _check_name(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v):
        return _check_password(v)

    @field_validator("permissions")
    @classmethod
    def _perms(cls, v):
        return clean_permissions(v)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=120)
    password: Optional[str] = None
    permissions: Optional[list[Module]] = None
    is_superadmin: Optional[bool] = None
    status: Optional[Literal["active", "disabled"]] = None
    unlock: Optional[bool] = None

    @field_validator("full_name")
    @classmethod
    def _name(cls, v):
        return _check_name(v)

    @field_validator("password")
    @classmethod
    def _password(cls, v):
        return _check_password(v) if v else None

    @field_validator("permissions")
    @classmethod
    def _perms(cls, v):
        return clean_permissions(v) if v is not None else None


class UserApprove(BaseModel):
    permissions: list[Module] = []
    is_superadmin: bool = False

    @field_validator("permissions")
    @classmethod
    def _perms(cls, v):
        return clean_permissions(v)


class UserResponse(UserBase):
    id: int
    full_name: Optional[str] = None
    role: str
    status: str
    is_superadmin: bool
    permissions: list[str]
    created_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    locked: bool = False

    class Config:
        from_attributes = True

