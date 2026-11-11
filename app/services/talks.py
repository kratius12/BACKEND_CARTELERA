"""Conferencias: conferenciantes que vienen y que van, organizados por mes.

- Vienen (incoming): visitantes de otra congregación. Se escribe nombre, teléfono,
  congregación de origen, bosquejo, título, canción e imágenes. Solo una conferencia por fecha.
- Van (outgoing): hermanos de esta congregación con perfil de conferenciante. Solo
  pueden ser conferenciantes los ancianos y siervos ministeriales activos. Cada uno tiene su teléfono y sus bosquejos; al programar
  se elige uno de sus bosquejos (con su título, imágenes y canción). Un hermano no puede
  ir a dos lugares la misma fecha.
- El catálogo de bosquejos (número → título) se llena solo con lo que se escribe.
"""
import re
from datetime import date
from typing import Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.models.student import Student
from app.models.talks import LocalSpeaker, PublicTalk, SpeakerOutline, TalkOutline

DIRECTIONS = ("incoming", "outgoing")
MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
PHONE_RE = re.compile(r"^[0-9+()\-.\s]{7,30}$")


class TalkError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "invalid"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


# ── Utilidades ────────────────────────────────────────────────────────────────

def month_bounds(month: str) -> tuple[date, date]:
    """'2026-11' → (2026-11-01, 2026-11-30)."""
    match = re.fullmatch(r"(\d{4})-(\d{2})", month or "")
    if not match or not 1 <= int(match.group(2)) <= 12:
        raise TalkError("El mes debe tener el formato AAAA-MM.", code="invalid_month")
    year, mon = int(match.group(1)), int(match.group(2))
    first = date(year, mon, 1)
    last = date(year + (mon == 12), mon % 12 + 1, 1)
    return first, date.fromordinal(last.toordinal() - 1)


def month_label(month: str) -> str:
    first, _ = month_bounds(month)
    return f"{MONTHS[first.month - 1]} {first.year}"


def clean_text(value: Optional[str], field: str, required: bool = True, max_len: int = 150) -> Optional[str]:
    value = " ".join((value or "").split())
    if not value:
        if required:
            raise TalkError(f"Falta {field}.", code="missing")
        return None
    if len(value) > max_len:
        raise TalkError(f"{field.capitalize()} es demasiado largo (máximo {max_len} caracteres).", code="too_long")
    return value


def clean_phone(value: Optional[str]) -> Optional[str]:
    value = " ".join((value or "").split())
    if not value:
        return None
    if not PHONE_RE.match(value) or sum(c.isdigit() for c in value) < 7:
        raise TalkError("El teléfono debe tener al menos 7 dígitos y solo números, espacios, +, - o paréntesis.", code="invalid_phone")
    return value


def clean_outline(number, title: Optional[str]) -> tuple[int, str]:
    try:
        number = int(number)
    except (TypeError, ValueError):
        raise TalkError("El bosquejo debe ser un número.", code="invalid_outline")
    if not 1 <= number <= 9999:
        raise TalkError("El número de bosquejo no es válido.", code="invalid_outline")
    return number, clean_text(title, "el título del discurso", max_len=200)


def clean_song(value) -> Optional[int]:
    """Número de canción (opcional)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        song = int(value)
    except (TypeError, ValueError):
        raise TalkError("La canción debe ser un número.", code="invalid_song")
    if not 1 <= song <= 999:
        raise TalkError("El número de canción no es válido.", code="invalid_song")
    return song


def remember_outline(db: Session, number: int, title: str) -> None:
    """Guarda o actualiza el título del bosquejo en el catálogo."""
    stmt = pg_insert(TalkOutline).values(number=number, title=title)
    stmt = stmt.on_conflict_do_update(index_elements=[TalkOutline.number], set_={"title": title, "updated_at": func.now()})
    db.execute(stmt)


def privilege(student: Student) -> Optional[str]:
    if student.es_anciano:
        return "Anciano"
    if student.es_siervo:
        return "Siervo ministerial"
    return None


def speaker_problem(student: Student) -> Optional[str]:
    """Por qué el estudiante no puede ser conferenciante de la congregación, o None."""
    if student.status != "Activo":
        return f"{student.name} no está activo."
    if student.gender != 1 or privilege(student) is None:
        return f"{student.name} no puede dar conferencias: solo los ancianos y siervos ministeriales."
    return None


def _require_local_speaker(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise TalkError("El estudiante no existe.", status_code=404, code="not_found")
    problem = speaker_problem(student)
    if problem:
        raise TalkError(problem, code="not_eligible")
    return student


# ── Conferencias del mes ─────────────────────────────────────────────────────

def serialize_talk(talk: PublicTalk, with_phone: bool = True) -> dict:
    item = {
        "id": talk.id,
        "direction": talk.direction,
        "date": talk.date,
        "congregation": talk.congregation,
        "student_id": talk.student_id,
        "speaker_name": talk.speaker_name,
        "outline_number": talk.outline_number,
        "title": talk.title,
        "has_images": talk.has_images,
        "song": talk.song,
    }
    if with_phone:
        item["phone"] = talk.phone
    return item


def list_talks(db: Session, month: str, direction: Optional[str] = None) -> list[PublicTalk]:
    first, last = month_bounds(month)
    query = select(PublicTalk).where(PublicTalk.date >= first, PublicTalk.date <= last)
    if direction:
        query = query.where(PublicTalk.direction == direction)
    return db.execute(query.order_by(PublicTalk.date, PublicTalk.direction, PublicTalk.speaker_name)).scalars().all()


def _check_conflicts(db: Session, talk_id: Optional[int], direction: str, day: date, student_id: Optional[int]):
    if direction == "incoming":
        clash = db.execute(
            select(PublicTalk).where(
                PublicTalk.direction == "incoming", PublicTalk.date == day,
                *( [PublicTalk.id != talk_id] if talk_id else [] ),
            )
        ).scalars().first()
        if clash:
            raise TalkError(
                f"El {day.day} de {MONTHS[day.month - 1]} ya viene {clash.speaker_name}. Solo hay una conferencia por reunión.",
                status_code=409, code="duplicate_date",
            )
    elif student_id is not None:
        clash = db.execute(
            select(PublicTalk).where(
                PublicTalk.direction == "outgoing", PublicTalk.date == day, PublicTalk.student_id == student_id,
                *( [PublicTalk.id != talk_id] if talk_id else [] ),
            )
        ).scalars().first()
        if clash:
            raise TalkError(
                f"{clash.speaker_name} ya va a {clash.congregation} el {day.day} de {MONTHS[day.month - 1]}.",
                status_code=409, code="speaker_busy",
            )


def _values_from_payload(db: Session, data: dict) -> dict:
    direction = data.get("direction")
    if direction not in DIRECTIONS:
        raise TalkError("Indica si el conferenciante viene o va.", code="invalid_direction")
    if not isinstance(data.get("date"), date):
        raise TalkError("Falta la fecha.", code="missing")
    values = {
        "direction": direction,
        "date": data["date"],
        "congregation": clean_text(data.get("congregation"), "la congregación", max_len=120),
    }
    if direction == "incoming":
        number, title = clean_outline(data.get("outline_number"), data.get("title"))
        values.update(
            student_id=None,
            speaker_name=clean_text(data.get("speaker_name"), "el nombre del conferenciante"),
            phone=clean_phone(data.get("phone")),
            outline_number=number,
            title=title,
            has_images=bool(data.get("has_images")),
            song=clean_song(data.get("song")),
        )
    else:
        student_id = data.get("student_id")
        if not student_id:
            raise TalkError("Elige al conferenciante de la congregación.", code="missing")
        speaker = db.execute(
            select(LocalSpeaker).options(selectinload(LocalSpeaker.student), selectinload(LocalSpeaker.outlines))
            .where(LocalSpeaker.student_id == student_id)
        ).scalar_one_or_none()
        if speaker is None:
            raise TalkError("Ese hermano no está en la lista de conferenciantes.", code="not_speaker")
        _require_local_speaker(db, student_id)
        outline = next((o for o in speaker.outlines if o.id == data.get("outline_id")), None)
        if outline is None:
            raise TalkError(f"Elige uno de los bosquejos de {speaker.student.name}.", code="invalid_outline")
        phone = data.get("phone") if data.get("phone") is not None else speaker.phone
        values.update(
            student_id=student_id,
            speaker_name=speaker.student.name,
            phone=clean_phone(phone),
            outline_number=outline.number,
            title=outline.title,
            has_images=outline.has_images,
            song=outline.song,
        )
    return values


def create_talk(db: Session, data: dict) -> dict:
    values = _values_from_payload(db, data)
    _check_conflicts(db, None, values["direction"], values["date"], values["student_id"])
    talk = PublicTalk(**values)
    db.add(talk)
    remember_outline(db, values["outline_number"], values["title"])
    db.commit()
    db.refresh(talk)
    return serialize_talk(talk)


def update_talk(db: Session, talk_id: int, data: dict) -> dict:
    talk = db.get(PublicTalk, talk_id)
    if talk is None:
        raise TalkError("No se encontró esa conferencia.", status_code=404, code="not_found")
    merged = {**serialize_talk(talk), "outline_id": None, **{k: v for k, v in data.items()}}
    if merged["direction"] == "outgoing" and "outline_id" not in data:
        # Conserva el bosquejo actual si sigue en la lista del conferenciante
        outline = db.execute(
            select(SpeakerOutline).where(
                SpeakerOutline.student_id == merged["student_id"], SpeakerOutline.number == talk.outline_number,
            )
        ).scalar_one_or_none()
        merged["outline_id"] = outline.id if outline else None
    if merged["direction"] == "outgoing" and "phone" not in data:
        merged["phone"] = talk.phone
    values = _values_from_payload(db, merged)
    _check_conflicts(db, talk.id, values["direction"], values["date"], values["student_id"])
    for key, value in values.items():
        setattr(talk, key, value)
    remember_outline(db, values["outline_number"], values["title"])
    db.commit()
    db.refresh(talk)
    return serialize_talk(talk)


def delete_talk(db: Session, talk_id: int) -> None:
    talk = db.get(PublicTalk, talk_id)
    if talk is None:
        raise TalkError("No se encontró esa conferencia.", status_code=404, code="not_found")
    db.delete(talk)
    db.commit()


# ── Conferenciantes locales ──────────────────────────────────────────────────

def serialize_speaker(speaker: LocalSpeaker, stats: dict) -> dict:
    problem = speaker_problem(speaker.student)
    return {
        "student_id": speaker.student_id,
        "name": speaker.student.name,
        "status": speaker.student.status,
        "privilege": privilege(speaker.student),
        "eligible": problem is None,
        "problem": problem,
        "phone": speaker.phone,
        "outlines": [
            {"id": o.id, "number": o.number, "title": o.title, "has_images": o.has_images, "song": o.song}
            for o in speaker.outlines
        ],
        "talks_count": stats.get(speaker.student_id, (0, None))[0],
        "last_talk": stats.get(speaker.student_id, (0, None))[1],
    }


def _speaker_stats(db: Session) -> dict:
    rows = db.execute(
        select(PublicTalk.student_id, func.count(), func.max(PublicTalk.date))
        .where(PublicTalk.direction == "outgoing", PublicTalk.student_id.is_not(None))
        .group_by(PublicTalk.student_id)
    ).all()
    return {sid: (n, last) for sid, n, last in rows}


def list_speakers(db: Session) -> list[dict]:
    speakers = db.execute(
        select(LocalSpeaker).options(selectinload(LocalSpeaker.student), selectinload(LocalSpeaker.outlines))
    ).scalars().all()
    stats = _speaker_stats(db)
    return sorted((serialize_speaker(s, stats) for s in speakers), key=lambda s: s["name"])


def _get_speaker(db: Session, student_id: int) -> LocalSpeaker:
    speaker = db.execute(
        select(LocalSpeaker).options(selectinload(LocalSpeaker.student), selectinload(LocalSpeaker.outlines))
        .where(LocalSpeaker.student_id == student_id)
    ).scalar_one_or_none()
    if speaker is None:
        raise TalkError("Ese hermano no está en la lista de conferenciantes.", status_code=404, code="not_found")
    return speaker


def get_speaker(db: Session, student_id: int) -> dict:
    return serialize_speaker(_get_speaker(db, student_id), _speaker_stats(db))


def add_speaker(db: Session, student_id: int, phone: Optional[str]) -> dict:
    student = _require_local_speaker(db, student_id)
    if db.get(LocalSpeaker, student_id) is not None:
        raise TalkError(f"{student.name} ya está en la lista de conferenciantes.", status_code=409, code="duplicate")
    db.add(LocalSpeaker(student_id=student_id, phone=clean_phone(phone)))
    db.commit()
    return get_speaker(db, student_id)


def update_speaker(db: Session, student_id: int, phone: Optional[str]) -> dict:
    speaker = _get_speaker(db, student_id)
    speaker.phone = clean_phone(phone)
    db.commit()
    return get_speaker(db, student_id)


def remove_speaker(db: Session, student_id: int) -> None:
    speaker = _get_speaker(db, student_id)
    db.delete(speaker)  # las conferencias ya programadas conservan nombre y bosquejo
    db.commit()


def add_outline(db: Session, student_id: int, number, title: Optional[str], has_images: bool, song=None) -> dict:
    speaker = _get_speaker(db, student_id)
    number, title = clean_outline(number, title)
    song = clean_song(song)
    if any(o.number == number for o in speaker.outlines):
        raise TalkError(f"{speaker.student.name} ya tiene el bosquejo {number}.", status_code=409, code="duplicate")
    speaker.outlines.append(SpeakerOutline(number=number, title=title, has_images=bool(has_images), song=song))
    speaker.outlines.sort(key=lambda o: o.number)
    remember_outline(db, number, title)
    db.commit()
    return get_speaker(db, student_id)


def update_outline(
    db: Session, student_id: int, outline_id: int, number, title: Optional[str], has_images: bool, song=None,
) -> dict:
    speaker = _get_speaker(db, student_id)
    outline = next((o for o in speaker.outlines if o.id == outline_id), None)
    if outline is None:
        raise TalkError("No se encontró ese bosquejo.", status_code=404, code="not_found")
    number, title = clean_outline(number, title)
    song = clean_song(song)
    if any(o.number == number and o.id != outline_id for o in speaker.outlines):
        raise TalkError(f"{speaker.student.name} ya tiene el bosquejo {number}.", status_code=409, code="duplicate")
    previous_number = outline.number
    outline.number, outline.title, outline.has_images, outline.song = number, title, bool(has_images), song
    # Las salidas que todavía no han pasado se actualizan con el bosquejo; el historial no cambia
    db.execute(
        update(PublicTalk)
        .where(
            PublicTalk.direction == "outgoing", PublicTalk.student_id == student_id,
            PublicTalk.outline_number == previous_number, PublicTalk.date >= date.today(),
        )
        .values(outline_number=number, title=title, has_images=bool(has_images), song=song, updated_at=func.now())
        .execution_options(synchronize_session=False)
    )
    remember_outline(db, number, title)
    db.commit()
    return get_speaker(db, student_id)


def delete_outline(db: Session, student_id: int, outline_id: int) -> dict:
    speaker = _get_speaker(db, student_id)
    outline = next((o for o in speaker.outlines if o.id == outline_id), None)
    if outline is None:
        raise TalkError("No se encontró ese bosquejo.", status_code=404, code="not_found")
    speaker.outlines.remove(outline)
    db.commit()
    return get_speaker(db, student_id)


def eligible_students(db: Session) -> list[dict]:
    """Ancianos y siervos ministeriales activos que todavía no están en la lista."""
    taken = select(LocalSpeaker.student_id)
    students = db.execute(
        select(Student)
        .where(
            Student.gender == 1, Student.status == "Activo", Student.id.not_in(taken),
            or_(Student.es_anciano.is_(True), Student.es_siervo.is_(True)),
        )
        .order_by(Student.name)
    ).scalars().all()
    return [{"id": s.id, "name": s.name, "privilege": privilege(s)} for s in students]


# ── Ayudas para los formularios ──────────────────────────────────────────────

def outline_catalog(db: Session) -> list[dict]:
    rows = db.execute(select(TalkOutline.number, TalkOutline.title).order_by(TalkOutline.number)).all()
    return [{"number": n, "title": t} for n, t in rows]


def visitors(db: Session) -> list[dict]:
    """Visitantes anteriores (para autocompletar teléfono y congregación)."""
    rows = db.execute(
        select(PublicTalk).where(PublicTalk.direction == "incoming").order_by(PublicTalk.date.desc())
    ).scalars().all()
    seen: dict[str, dict] = {}
    for talk in rows:
        key = talk.speaker_name.casefold()
        if key not in seen:
            seen[key] = {"name": talk.speaker_name, "phone": talk.phone, "congregation": talk.congregation, "last_date": talk.date}
    return sorted(seen.values(), key=lambda v: v["name"])


def public_month(db: Session, month: str) -> dict:
    """Para la hoja impresa pública: sin teléfonos."""
    talks = list_talks(db, month)
    return {
        "month": month,
        "label": month_label(month),
        "incoming": [serialize_talk(t, with_phone=False) for t in talks if t.direction == "incoming"],
        "outgoing": [serialize_talk(t, with_phone=False) for t in talks if t.direction == "outgoing"],
    }
