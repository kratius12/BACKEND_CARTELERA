from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import date

from app.api.dependencies import get_db
from app.schemas.program import ProgramResponse, ProgramListResponse
from app.crud import program as crud_program

router = APIRouter()

@router.get("/current")
async def get_current_program(db: AsyncSession = Depends(get_db)):
    today = date.today()
    prog_id = await crud_program.get_current_program_id(db, today)
    return {"id": prog_id}

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
