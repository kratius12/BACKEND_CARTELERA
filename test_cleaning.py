import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.services.cleaning import generate_cleaning_pairs, get_cleaning_history

async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        print("--- HISTORY BEFORE ---")
        hist = await get_cleaning_history(db)
        print(hist)
        
        print("\n--- GENERATING 5 PAIRS ---")
        res = await generate_cleaning_pairs(db, 5)
        print(res)
        
        print("\n--- HISTORY AFTER ---")
        hist2 = await get_cleaning_history(db)
        for h in hist2:
            print(f"{h['grupo1']} - {h['grupo2']} ({h['fecha_asignacion']})")
        
        print("\n--- GENERATING 3 MORE PAIRS ---")
        res2 = await generate_cleaning_pairs(db, 3)
        print(res2)
        
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
