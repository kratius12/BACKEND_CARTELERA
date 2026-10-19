from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.schemas.preaching_report import (
    MONTH_PATTERN,
    GroupLinkOut,
    PioneerYear,
    PreachingReportsMonth,
    PreachingReportsSave,
)
from app.services.preaching_reports import (
    ensure_month_available,
    get_group_links,
    get_month_reports,
    get_pioneer_year,
    parse_month,
    regenerate_group_link,
    save_month_reports,
)

router = APIRouter()


@router.get("", response_model=PreachingReportsMonth)
def api_get_month_reports(
    month: str = Query(..., pattern=MONTH_PATTERN, description="Mes del informe (YYYY-MM)"),
    db: Session = Depends(get_db),
):
    """Grupos con sus integrantes y el informe de cada uno para el mes."""
    month_date = parse_month(month)
    ensure_month_available(month_date)
    return get_month_reports(db, month_date)


@router.put("", response_model=PreachingReportsMonth)
def api_save_month_reports(payload: PreachingReportsSave, db: Session = Depends(get_db)):
    """Crea o actualiza los informes enviados y devuelve el mes actualizado."""
    month = parse_month(payload.month)
    ensure_month_available(month)
    save_month_reports(db, month, payload.reports, allow_status_change=True)
    return get_month_reports(db, month)


@router.get("/pioneers", response_model=PioneerYear)
def api_pioneer_year(
    month: str = Query(..., pattern=MONTH_PATTERN, description="Calcular las metas hasta este mes (YYYY-MM)"),
    db: Session = Depends(get_db),
):
    """Precursores del año de servicio, mes a mes, para seguir sus metas."""
    month_date = parse_month(month)
    ensure_month_available(month_date)
    return get_pioneer_year(db, month_date)


@router.get("/links", response_model=List[GroupLinkOut])
def api_group_links(db: Session = Depends(get_db)):
    """Link secreto de cada grupo para compartir con su encargado."""
    return get_group_links(db)


@router.post("/links/{group_id}/regenerate", response_model=GroupLinkOut)
def api_regenerate_group_link(group_id: UUID, db: Session = Depends(get_db)):
    """Crea un link nuevo para el grupo; el anterior deja de funcionar."""
    return regenerate_group_link(db, group_id)
