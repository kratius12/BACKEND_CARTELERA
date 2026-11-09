from datetime import datetime, timedelta, timezone
import hashlib
import bcrypt
import jwt
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if isinstance(hashed_password, str):
            # Formateamos si es string desde postgres
            hashed_password = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password)
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

# Hash fijo para comparar cuando el correo no existe: así la respuesta tarda lo mismo
_DUMMY_HASH = bcrypt.hashpw(b"cartelera-dummy-password", bcrypt.gensalt()).decode("utf-8")


def verify_password_timing_safe(plain_password: str, hashed_password: str | None) -> bool:
    """Como verify_password, pero gasta el mismo tiempo si el usuario no existe."""
    if not hashed_password:
        verify_password(plain_password, _DUMMY_HASH)
        return False
    return verify_password(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None, expires_at: datetime | None = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_at:
        expire = expires_at
    elif expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": int(now.timestamp())})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def hash_token(token: str) -> str:
    """Hash de los tokens de recuperación (en la base de datos nunca se guarda el token)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    """Fecha y hora UTC sin zona, como se guardan en la base de datos."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
