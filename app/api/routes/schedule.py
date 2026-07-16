from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import date, datetime, timedelta

from app.api.dependencies import get_db
from app.models.cleaning import CleaningHistory
from app.models.assignments import MicrophoneAssignment, AttendantAssignment
from app.services.cleaning import generate_cleaning_pairs, assign_cleaning_roles_for_week
from app.services.assignments import generate_weekly_assignments

router = APIRouter()


@router.post("/generate-all")
def generate_all_schedule(
    n_weeks: int = Query(4, ge=1, le=50, description="Semanas a generar"),
    start_date: str = Query(None, description="Fecha de inicio YYYY-MM-DD. Si se omite, se calcula automáticamente."),
    db: Session = Depends(get_db)
):
    """
    Genera aseo, micrófonos y acomodadores para el mismo rango de semanas.
    Si no se provee start_date, se calcula como la semana siguiente al último
    registro existente entre los tres módulos.
    """
    # ── 1. Calcular fecha de inicio común ─────────────────────────────────────
    if start_date:
        try:
            forced_start = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de fecha inválido. Usa YYYY-MM-DD.")
    else:
        last_cleaning   = (db.execute(select(func.max(CleaningHistory.week_end)))).scalar()
        last_micro      = (db.execute(select(func.max(MicrophoneAssignment.date)))).scalar()
        last_attendant  = (db.execute(select(func.max(AttendantAssignment.date)))).scalar()

        existing = [d for d in [last_cleaning, last_micro, last_attendant] if d is not None]
        if existing:
            latest = max(existing)
            # Siguiente lunes después del último registro
            forced_start = latest + timedelta(days=7)
            forced_start = forced_start - timedelta(days=forced_start.weekday())
        else:
            # Sin datos previos: lunes de la semana actual
            today = date.today()
            forced_start = today - timedelta(days=today.weekday())

    forced_start_str = forced_start.isoformat()

    # ── 2. Generar los tres módulos con la misma fecha ────────────────────────
    try:
        cleaning_records = generate_cleaning_pairs(
            db, n_parejas_a_generar=n_weeks, start_date=forced_start_str
        )
        assign_cleaning_roles_for_week(db)

        micro_records     = generate_weekly_assignments(db, "micro",     n_weeks, forced_start)
        attendant_records = generate_weekly_assignments(db, "attendant", n_weeks, forced_start)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "start_date":           forced_start_str,
        "n_weeks":              n_weeks,
        "cleaning_weeks":       len(cleaning_records),
        "micro_weeks":          len(micro_records) // 2,
        "attendant_weeks":      len(attendant_records) // 2,
    }
