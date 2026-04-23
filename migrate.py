import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.models import Base # Ensures all models are imported
from app.core.database import db_url

async def main():
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        from sqlalchemy import text
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
