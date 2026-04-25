from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from datetime import date

from app.api.dependencies import get_db
from app.services.assignments import generate_weekly_assignments, get_assignment_history

router = APIRouter()

@router.get("/{type}/history", response_model=List[Dict[str, Any]])
async def api_get_assignment_history(
    type: str, # 'micro' or 'attendant'
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    if type not in ["micro", "attendant"]:
        raise HTTPException(status_code=400, detail="Tipo de asignación inválido")
    return await get_assignment_history(db, type, limit)

@router.post("/{type}/generate", response_model=List[Dict[str, Any]])
async def api_generate_assignments(
    type: str,
    n_weeks: int = Query(5, ge=1, le=50),
    start_date: date = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db)
):
    if type not in ["micro", "attendant"]:
        raise HTTPException(status_code=400, detail="Tipo de asignación inválido")
    
    assignments = await generate_weekly_assignments(db, type, n_weeks, start_date)
    return [
        {"id": a.id, "student_id": a.student_id, "date": a.date}
        for a in assignments
    ]
