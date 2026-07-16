from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool
from app.core.config import settings

# Usa URL interna de Railway si está disponible, si no la pública
db_url = settings.db_url
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# NullPool: una conexión nueva por request, sin pool en background.
# Evita que health checks del pool crasheen el proceso en Railway.
# ssl=False: TCP plano, sin negociación SSL (Railway proxy lo requiere así).
engine = create_async_engine(
    db_url,
    echo=False,
    poolclass=NullPool,
    connect_args={"ssl": False},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
