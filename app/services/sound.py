"""Sonido: audio y video, micrófonos y Zoom; una fila por semana.

Cada fila va del sábado a la reunión de entre semana siguiente (por defecto el día
de MIDWEEK_MEETING_WEEKDAY, martes). Se revisan las dos semanas: nadie puede ser
encargado de aseo, tener micrófonos (la asignación de /admin/microfonos) ni ser
acomodador en la semana del sábado ni en la de la reunión de entre semana. Que su
grupo tenga aseo esa semana no lo bloquea, ni ser supervisor de aseo. Tampoco puede
presidir o leer el sábado (Fin de semana). Las demás reglas están en
app/services/saturday_schedule.py.
"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.sound import SoundAssignment
from app.models.weekend import WeekendAssignment
from app.services import availability
from app.services.saturday_schedule import MONTHS, Role, SaturdaySchedule

ROLES = [
    Role(key="audio", label="Audio y video", noun="audio y video", flag="sonido_audio_video"),
    Role(key="micro", label="Micrófonos", noun="micrófonos", flag="sonido_microfonos"),
    Role(key="zoom", label="Zoom", noun="Zoom", flag="sonido_zoom"),
]


def default_midweek(saturday: date) -> date:
    """Primer día MIDWEEK_MEETING_WEEKDAY (0 = lunes … 6 = domingo) después del sábado."""
    weekday = settings.MIDWEEK_MEETING_WEEKDAY % 7
    days = (weekday - saturday.weekday()) % 7 or 7
    return saturday + timedelta(days=days)


def label(saturday: date, midweek: date | None) -> str:
    """5 - 8 DE SEPTIEMBRE, o 31 DE OCTUBRE AL 3 DE NOVIEMBRE si cambia el mes."""
    midweek = midweek or default_midweek(saturday)
    if saturday.month == midweek.month:
        return f"{saturday.day} - {midweek.day} DE {MONTHS[midweek.month - 1].upper()}"
    return (
        f"{saturday.day} DE {MONTHS[saturday.month - 1].upper()} AL "
        f"{midweek.day} DE {MONTHS[midweek.month - 1].upper()}"
    )


def _weekend_parts(db: Session, saturdays: list[date]) -> dict:
    """Quién preside o lee esos sábados."""
    out: dict[date, dict[int, list[dict]]] = {}
    rows = db.execute(select(WeekendAssignment).where(WeekendAssignment.date.in_(saturdays))).scalars().all()
    for row in rows:
        target = out.setdefault(row.date, {})
        availability.add_reason(target, row.president_id, "fin_de_semana", "Fin de semana: presidente")
        availability.add_reason(target, row.reader_id, "fin_de_semana", "Fin de semana: lector")
    return out


schedule = SaturdaySchedule(
    name="Sonido",
    model=SoundAssignment,
    roles=ROLES,
    module_phrase="de sonido",
    label=label,
    default_midweek=default_midweek,
    extra_busy=_weekend_parts,
    # En sonido solo cuenta ser encargado de aseo; el resto del grupo sí puede estar
    cleaning_blocks=frozenset({"encargado"}),
)
