from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from app.api.dependencies import get_db
from app.services.cleaning import generate_cleaning_pairs, get_cleaning_history

router = APIRouter()

@router.get("/history", response_model=List[Dict[str, Any]])
async def api_get_cleaning_history(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el historial de asignaciones de aseo.
    """
    try:
        history = await get_cleaning_history(db, limit)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate", response_model=List[Dict[str, Any]])
async def api_generate_cleaning_pairs(
    n_pairs: int = Query(5, ge=1, le=50, alias="n_parejas_a_generar"),
    start_date: str = Query(None, description="Fecha de inicio en formato YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db)
):
    """
    Genera e inserta `n_parejas_a_generar` basándose en la secuencia cíclica y
    el último registro en la base de datos.
    """
    try:
        nuevas_parejas = await generate_cleaning_pairs(db, n_parejas_a_generar=n_pairs, start_date=start_date)
        return nuevas_parejas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
