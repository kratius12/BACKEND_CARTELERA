import asyncio
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal
from app.models.assignments import MicrophoneAssignment, AttendantAssignment
from app.models.cleaning import CleaningHistory

async def debug_db():
    async with AsyncSessionLocal() as db:
        micro_count = await db.execute(select(func.count()).select_from(MicrophoneAssignment))
        attendant_count = await db.execute(select(func.count()).select_from(AttendantAssignment))
        cleaning_count = await db.execute(select(func.count()).select_from(CleaningHistory))
        
        m_c = micro_count.scalar()
        a_c = attendant_count.scalar()
        c_c = cleaning_count.scalar()
        
        print(f"Micros: {m_c}")
        print(f"Attendants: {a_c}")
        print(f"Cleaning: {c_c}")
        
        if m_c > 0:
            last_micro = await db.execute(select(MicrophoneAssignment).order_by(MicrophoneAssignment.date.desc()).limit(5))
            for m in last_micro.scalars().all():
                print(f"Micro Date: {m.date}")
        
        if c_c > 0:
            last_cleaning = await db.execute(select(CleaningHistory).order_by(CleaningHistory.week_start.desc()).limit(5))
            for c in last_cleaning.scalars().all():
                print(f"Cleaning Week: {c.week_start} - {c.week_end}")

if __name__ == "__main__":
    asyncio.run(debug_db())
