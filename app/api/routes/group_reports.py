"""Informes de predicación con el link secreto de un grupo (sin iniciar sesión).

Quien tiene el link solo puede ver y guardar los informes de las personas de ese grupo.
"""
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.models.group import Group
from app.schemas.preaching_report import (
    MONTH_PATTERN,
    GroupReportMonth,
    PreachingReportGroup,
    PreachingReportsSave,
)
from app.services.preaching_reports import (
    ensure_month_available,
    get_group_by_token,
    get_month_reports,
    group_member_ids,
    parse_month,
    save_month_reports,
)

router = APIRouter()

TOKEN_PATTERN = r"^[A-Za-z0-9_-]{16,64}$"
INVALID_LINK = "Este link no es válido o fue cambiado. Pídele el link nuevo al secretario."


def _group_or_404(db: Session, token: str) -> Group:
    group = get_group_by_token(db, token)
    if not group:
        raise HTTPException(status_code=404, detail=INVALID_LINK)
    return group


def _group_month(db: Session, group: Group, month_value: str) -> GroupReportMonth:
    month_date = parse_month(month_value)
    ensure_month_available(month_date)
    data = get_month_reports(db, month_date, only_group_id=group.id)
    grp = data.groups[0] if data.groups else PreachingReportGroup(id=group.id, name=group.name, rows=[])
    return GroupReportMonth(month=data.month, group=grp)


@router.get("/{token}", response_model=GroupReportMonth)
def api_group_month(
    token: str = Path(..., pattern=TOKEN_PATTERN),
    month: str = Query(..., pattern=MONTH_PATTERN, description="Mes del informe (YYYY-MM)"),
    db: Session = Depends(get_db),
):
    group = _group_or_404(db, token)
    return _group_month(db, group, month)


@router.put("/{token}", response_model=GroupReportMonth)
def api_save_group_month(
    payload: PreachingReportsSave,
    token: str = Path(..., pattern=TOKEN_PATTERN),
    db: Session = Depends(get_db),
):
    group = _group_or_404(db, token)
    month_date = parse_month(payload.month)
    ensure_month_available(month_date)
    save_month_reports(
        db,
        month_date,
        payload.reports,
        allowed_student_ids=group_member_ids(db, group.id),
        type_locked=True,  # el encargado no cambia el tipo; lo administra el secretario
    )
    return _group_month(db, group, payload.month)
