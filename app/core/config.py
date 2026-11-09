from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

_DEFAULT_SECRET = "your-super-secret-key-change-it-in-production"

class Settings(BaseSettings):
    PORT: int = 3001
    DATABASE_URL: str
    DATABASE_PRIVATE_URL: str = ""

    @property
    def db_url(self) -> str:
        return self.DATABASE_PRIVATE_URL or self.DATABASE_URL

    SECRET_KEY: str = _DEFAULT_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALLOWED_ORIGINS: str = ""

    # Sesión: sin "Recordarme" dura SESSION_HOURS; con "Recordarme", SESSION_REMEMBER_DAYS
    SESSION_HOURS: int = 12
    SESSION_REMEMBER_DAYS: int = 30

    # Bloqueo temporal tras varios intentos fallidos seguidos
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15

    # Día de la reunión de entre semana (0 = lunes … 6 = domingo). Sonido arma cada fila
    # desde el sábado hasta ese día de la semana siguiente.
    MIDWEEK_MEETING_WEEKDAY: int = 1  # martes

    # Recuperación de contraseña por correo
    PASSWORD_RESET_MINUTES: int = 60
    FRONTEND_URL: str = ""  # ej. https://cartelera.up.railway.app (para el enlace del correo)
    EMAIL_FROM: str = ""    # ej. "Cartelera <no-responder@tudominio.com>"
    RESEND_API_KEY: str = ""  # opción 1: Resend (API por HTTPS)
    SMTP_HOST: str = ""       # opción 2: SMTP
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_SSL: bool = False  # True para el puerto 465; con False se usa STARTTLS

    @property
    def email_enabled(self) -> bool:
        has_provider = bool(self.RESEND_API_KEY or self.SMTP_HOST)
        return bool(has_provider and self.EMAIL_FROM and self.FRONTEND_URL)

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v == _DEFAULT_SECRET:
            raise ValueError(
                "SECRET_KEY no puede ser el valor por defecto. "
                "Define SECRET_KEY en tu archivo .env con al menos 32 caracteres aleatorios."
            )
        if len(v) < 32:
            raise ValueError("SECRET_KEY debe tener al menos 32 caracteres.")
        return v

    def get_allowed_origins(self) -> list:
        if not self.ALLOWED_ORIGINS.strip():
            return []
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

settings = Settings()
