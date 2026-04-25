from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import date

from app.api.dependencies import get_db
from app.schemas.program import ProgramResponse, ProgramListResponse
from app.crud import program as crud_program

from app.models.cleaning import CleaningHistory
from app.models.assignments import MicrophoneAssignment, AttendantAssignment
from sqlalchemy import select, and_, desc

router = APIRouter()

@router.get("/schedule")
async def get_full_schedule(db: AsyncSession = Depends(get_db)):
    """
    Returns the consolidated schedule for Aseo, Microphones and Attendants.
    Limited to the 13 most recent/upcoming weeks.
    """
    from sqlalchemy.orm import selectinload
    # 1. Get last 12 cleaning records (newest)
    cleaning_query = select(CleaningHistory).options(
        selectinload(CleaningHistory.encargado),
        selectinload(CleaningHistory.supervisor)
    ).order_by(CleaningHistory.week_start.desc()).limit(12)
    
    # 2. Get last assignments (12 weeks * 2 people = 24)
    micro_query = select(MicrophoneAssignment).options(
        selectinload(MicrophoneAssignment.student)
    ).order_by(MicrophoneAssignment.date.desc()).limit(24)
    
    attendant_query = select(AttendantAssignment).options(
        selectinload(AttendantAssignment.student)
    ).order_by(AttendantAssignment.date.desc()).limit(24)
    
    cleaning_res = await db.execute(cleaning_query)
    micro_res = await db.execute(micro_query)
    attendant_res = await db.execute(attendant_query)
    
    cleaning = cleaning_res.scalars().all()
    micros = micro_res.scalars().all()
    attendants = attendant_res.scalars().all()
    
    # Group by week/date if possible, but the image shows them as separate tables
    # so we return them as separate lists.
    
    return {
        "cleaning": [
            {
                "week_start": c.week_start,
                "week_end": c.week_end,
                "grupo1": c.grupo1,
                "grupo2": c.grupo2,
                "encargado": c.encargado.name if c.encargado else "N/A",
                "supervisor": c.supervisor.name if c.supervisor else "N/A"
            } for c in cleaning
        ],
        "micros": [
            {
                "date": m.date,
                "student": m.student.name
            } for m in micros
        ],
        "attendants": [
            {
                "date": a.date,
                "student": a.student.name
            } for a in attendants
        ]
    }

@router.get("/current")
async def get_current_program(db: AsyncSession = Depends(get_db)):
    today = date.today()
    prog_id = await crud_program.get_current_program_id(db, today)
    return {"id": prog_id}

@router.get("/cleaning/today")
async def get_cleaning_today(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select, and_
    from sqlalchemy.orm import selectinload
    from app.models.cleaning import CleaningHistory
    today = date.today()
    
    query = select(CleaningHistory).options(
        selectinload(CleaningHistory.supervisor)
    ).where(
        and_(
            CleaningHistory.week_start <= today,
            CleaningHistory.week_end >= today
        )
    )
    result = await db.execute(query)
    record = result.scalar_one_or_none()
    
    if not record:
        return {"grupo1": None, "grupo2": None}
        
    return {
        "grupo1": record.grupo1,
        "grupo2": record.grupo2,
        "week_start": record.week_start,
        "week_end": record.week_end,
        "supervisor": record.supervisor.name if record.supervisor else None
    }

@router.get("", response_model=List[ProgramListResponse])
async def list_programs(db: AsyncSession = Depends(get_db)):
    programs = await crud_program.get_programs(db)
    return programs

@router.get("/{prog_id}")
async def get_program_by_id(prog_id: int, db: AsyncSession = Depends(get_db)):
    program = await crud_program.get_program(db, prog_id)
    if not program:
        raise HTTPException(status_code=404, detail="No encontrado")
    return program.payload

@router.get("/staging/{prog_id}")
async def get_public_staging_program(prog_id: int, db: AsyncSession = Depends(get_db)):
    # Permite leer un borrador específico públicamente si se tiene el ID.
    program = await crud_program.get_staging_program(db, prog_id)
    if not program:
        raise HTTPException(status_code=404, detail="Borrador no encontrado")
    return program.payload
