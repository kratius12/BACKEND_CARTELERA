"""Quién ya tiene aseo, micrófonos o acomodador en la semana de una fecha.

La semana de una fecha va de lunes a domingo. Aseo cuenta a todos los integrantes
de los dos grupos que limpian esa semana, más el encargado y el supervisor.
"""
import re
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignments import MicrophoneAssignment, AttendantAssignment
from app.models.cleaning import CleaningHistory
from app.models.group import Group
from app.models.student_group import StudentGroup


def week_bounds(day: date) -> tuple[date, date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def _group_number(name: str):
    match = re.search(r"\d+", name or "")
    return int(match.group()) if match else None


def _members_by_group_number(db: Session) -> dict[int, set[int]]:
    groups = db.execute(select(Group.id, Group.name)).all()
    number_of = {gid: _group_number(name) for gid, name in groups}
    members: dict[int, set[int]] = {}
    for group_id, student_id in db.execute(select(StudentGroup.group_id, StudentGroup.student_id)).all():
        number = number_of.get(group_id)
        if number is not None:
            members.setdefault(number, set()).add(student_id)
    return members


def add_reason(target: dict[int, list[dict]], student_id, kind: str, label: str) -> None:
    if student_id is None:
        return
    reasons = target.setdefault(student_id, [])
    if not any(r["label"] == label for r in reasons):
        reasons.append({"kind": kind, "label": label})


def busy_for_dates(db: Session, dates) -> dict[date, dict[int, list[dict]]]:
    """Para cada fecha: {student_id: [{kind, label}, ...]} con lo que ya tiene esa semana."""
    dates = sorted(set(dates))
    result: dict[date, dict[int, list[dict]]] = {d: {} for d in dates}
    if not dates:
        return result

    bounds = {d: week_bounds(d) for d in dates}
    first = bounds[dates[0]][0]
    last = bounds[dates[-1]][1]

    cleanings = db.execute(
        select(CleaningHistory).where(
            CleaningHistory.week_start <= last,
            CleaningHistory.week_end >= first,
        )
    ).scalars().all()
    if cleanings:
        members = _members_by_group_number(db)
        for record in cleanings:
            for day in dates:
                if not (record.week_start <= day <= record.week_end):
                    continue
                add_reason(result[day], record.encargado_id, "aseo", "Encargado de aseo")
                add_reason(result[day], record.supervisor_id, "aseo", "Supervisor de aseo")
                for number in (record.grupo1, record.grupo2):
                    for student_id in members.get(number, ()):
                        add_reason(result[day], student_id, "aseo", f"Aseo (grupo {number})")

    for model, kind, label in (
        (MicrophoneAssignment, "microfonos", "Micrófonos"),
        (AttendantAssignment, "acomodador", "Acomodador"),
    ):
        rows = db.execute(
            select(model.student_id, model.date).where(model.date >= first, model.date <= last)
        ).all()
        for student_id, assigned in rows:
            for day in dates:
                monday, sunday = bounds[day]
                if monday <= assigned <= sunday:
                    add_reason(result[day], student_id, kind, label)

    return result
