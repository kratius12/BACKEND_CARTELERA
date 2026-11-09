"""Fin de semana: presidente y lector del estudio de La Atalaya, cada sábado.

Las reglas comunes (permisos, aseo, micrófonos, acomodador, generador) están en
app/services/saturday_schedule.py. Además, nadie puede presidir o leer el sábado en
que tiene una parte de Sonido.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sound import SoundAssignment
from app.models.weekend import WeekendAssignment
from app.services import availability
from app.services.saturday_schedule import Role, SaturdaySchedule, ScheduleError, label_day, upcoming_saturday

ROLES = [
    Role(key="president", label="Presidente", noun="presidencia", flag="fds_presidente"),
    Role(key="reader", label="Lector", noun="lectura", flag="fds_lector"),
]


def _sound_parts(db: Session, saturdays: list[date]) -> dict:
    """Quién tiene Sonido esos sábados."""
    from app.services.sound import ROLES as SOUND_ROLES

    out: dict[date, dict[int, list[dict]]] = {}
    rows = db.execute(select(SoundAssignment).where(SoundAssignment.date.in_(saturdays))).scalars().all()
    for row in rows:
        target = out.setdefault(row.date, {})
        for role in SOUND_ROLES:
            availability.add_reason(target, getattr(row, f"{role.key}_id"), "sonido", f"Sonido: {role.label.lower()}")
    return out


schedule = SaturdaySchedule(
    name="Fin de semana",
    model=WeekendAssignment,
    roles=ROLES,
    module_phrase="del fin de semana",
    label=lambda saturday, _midweek: label_day(saturday),
    extra_busy=_sound_parts,
)

# Atajos usados por las rutas y las pruebas
WeekendError = ScheduleError
label_date = label_day
__all__ = ["schedule", "ROLES", "WeekendError", "label_date", "upcoming_saturday", "busy_for"]


def busy_for(db: Session, saturday: date) -> dict[int, list[dict]]:
    return schedule.busy_for(db, saturday)
