from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

_DEFAULT_SECRET = "your-super-secret-key-change-it-in-production"

class Settings(BaseSettings):
    PORT: int = 3001
    DATABASE_URL: str

    # JWT Settings
    SECRET_KEY: str = _DEFAULT_SECRET
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS — lista separada por comas en el .env, e.g.:
    # ALLOWED_ORIGINS=http://localhost:5173,https://tudominio.com
    # Deja en blanco o no configures para permitir todos los orígenes (solo desarrollo).
    ALLOWED_ORIGINS: str = ""

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

    def get_allowed_origins(self) -> list[str]:
        """Devuelve la lista de orígenes permitidos para CORS."""
        if not self.ALLOWED_ORIGINS.strip():
            # Con credentials=True, "*" no funciona — devolver lista vacía
            # para que el dev sepa que debe configurar ALLOWED_ORIGINS
            return []
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

settings = Settings()
