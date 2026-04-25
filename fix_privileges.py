import asyncio
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from sqlalchemy import update
from app.core.database import AsyncSessionLocal, engine
from app.models.student import Student

async def fix_privileges():
    async with AsyncSessionLocal() as db:
        # 1. Women: Inactive by default
        print("Actualizando privilegios para mujeres...")
        stmt1 = update(Student).where(Student.gender == 0).values(
            aseo=False,
            acomodador=False,
            microfonos=False
        )
        await db.execute(stmt1)
        
        # 2. Men active: Active by default
        print("Actualizando privilegios para hombres activos...")
        stmt2 = update(Student).where(Student.gender == 1, Student.status == "Activo").values(
            aseo=True,
            acomodador=True,
            microfonos=True
        )
        await db.execute(stmt2)
        
        await db.commit()
        print("¡Listo! Privilegios actualizados.")

if __name__ == "__main__":
    asyncio.run(fix_privileges())
