import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.models import Base # Ensures all models are imported
from app.core.config import settings

async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.execute(text("DROP TABLE IF EXISTS historial_emparejamientos CASCADE;"))
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
