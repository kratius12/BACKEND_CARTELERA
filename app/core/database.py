from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Usa URL interna de Railway si está disponible, si no la pública
db_url = settings.db_url

# Normalizar a psycopg2 (sync, probado con alembic)
for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgres://"):
    if db_url.startswith(prefix):
        db_url = "postgresql+psycopg2://" + db_url[len(prefix):]
        break
if db_url.startswith("postgresql://"):
    db_url = "postgresql+psycopg2://" + db_url[len("postgresql://"):]

engine = create_engine(db_url, echo=False, poolclass=NullPool)

SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

Base = declarative_base()

def get_db():
    with SessionLocal() as session:
        yield session
