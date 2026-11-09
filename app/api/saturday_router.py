"""Rutas del panel para los programas por sábado (Fin de semana, Sonido).

GET    ""                  sábados con conflictos (?start, ?end)
POST   ""                  programar un sábado
PUT    "/{id}"             cambiar personas (y la reunión de entre semana, si aplica)
DELETE "/{id}"             quitar un sábado
POST   "/generate"         generar los próximos sábados
GET    "/candidates"       habilitados por rol y su disponibilidad (?date, ?exclude_id, ?midweek)
GET    "/people"           varones con sus permisos y cuántas veces tuvieron cada rol
PUT    "/people/{id}"      activar o quitar permisos
"""
from datetime import date as Date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field, create_model
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.services.saturday_schedule import SaturdaySchedule, ScheduleError


def _fail(error: ScheduleError):
    raise HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message, "problems": error.problems},
    )


def build_router(schedule: SaturdaySchedule, model_prefix: str) -> APIRouter:
    router = APIRouter()
    role_fields = {f"{r.key}_id": (Optional[int], None) for r in schedule.roles}
    midweek_field = {"midweek_date": (Optional[Date], None)} if schedule.has_midweek else {}

    Create = create_model(f"{model_prefix}Create", date=(Date, ...), **midweek_field, **role_fields)
    Update = create_model(f"{model_prefix}Update", **midweek_field, **role_fields)
    Generate = create_model(
        f"{model_prefix}Generate",
        weeks=(int, Field(8, ge=1, le=26)),
        start_date=(Optional[Date], None),
    )
    Flags = create_model(f"{model_prefix}Flags", **{r.flag: (Optional[bool], None) for r in schedule.roles})

    @router.get("")
    def list_rows(
        start: Optional[Date] = Query(None, description="Desde este sábado (YYYY-MM-DD)"),
        end: Optional[Date] = Query(None, description="Hasta este sábado (YYYY-MM-DD)"),
        db: Session = Depends(get_db),
    ):
        return schedule.list_with_conflicts(db, start, end)

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_row(payload: Create, db: Session = Depends(get_db)):
        people = {r.key: getattr(payload, f"{r.key}_id") for r in schedule.roles}
        try:
            return schedule.create(db, payload.date, people, getattr(payload, "midweek_date", None))
        except ScheduleError as error:
            _fail(error)

    @router.put("/{row_id}")
    def update_row(row_id: int, payload: Update, db: Session = Depends(get_db)):
        sent = payload.model_fields_set
        people = {r.key: getattr(payload, f"{r.key}_id") for r in schedule.roles if f"{r.key}_id" in sent}
        try:
            return schedule.update(
                db, row_id, people,
                midweek=getattr(payload, "midweek_date", None),
                midweek_sent="midweek_date" in sent,
            )
        except ScheduleError as error:
            _fail(error)

    @router.delete("/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_row(row_id: int, db: Session = Depends(get_db)):
        try:
            schedule.delete(db, row_id)
        except ScheduleError as error:
            _fail(error)
        return None

    @router.post("/generate")
    def generate_rows(payload: Generate, db: Session = Depends(get_db)):
        try:
            return schedule.generate(db, payload.weeks, payload.start_date)
        except ScheduleError as error:
            _fail(error)

    @router.get("/candidates")
    def candidates(
        date_: Date = Query(..., alias="date", description="Sábado (YYYY-MM-DD)"),
        exclude_id: Optional[int] = Query(None, description="Fila que se está editando"),
        midweek: Optional[Date] = Query(None, description="Reunión de entre semana (YYYY-MM-DD)"),
        db: Session = Depends(get_db),
    ):
        try:
            return schedule.candidates(db, date_, exclude_id, midweek)
        except ScheduleError as error:
            _fail(error)

    @router.get("/people")
    def people(db: Session = Depends(get_db)):
        return schedule.people(db)

    @router.put("/people/{student_id}")
    def update_people(student_id: int, payload: Flags, db: Session = Depends(get_db)):
        values = {flag: getattr(payload, flag) for flag in payload.model_fields_set}
        try:
            student = schedule.set_flags(db, student_id, values)
        except ScheduleError as error:
            _fail(error)
        return {"id": student.id, "name": student.name, **{r.flag: getattr(student, r.flag) for r in schedule.roles}}

    return router
