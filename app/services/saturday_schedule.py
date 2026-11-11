"""Programas con una fila por sábado y una persona por rol (Fin de semana, Sonido).

Reglas comunes:
- Solo varones activos con el permiso del rol (una columna booleana en students).
- Una misma persona no puede tener dos roles en la misma fila.
- Nadie puede tener aseo, micrófonos ni acomodador la semana de cada reunión que
  cubre la fila (ver app/services/availability.py), ni las partes que agregue
  extra_busy (por ejemplo, Fin de semana y Sonido se revisan entre sí). En aseo,
  cleaning_blocks dice qué cuenta: los grupos que limpian, el encargado y el
  supervisor (por defecto los tres).
"""
import random
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Callable, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.student import Student
from app.services import availability

MONTHS = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
CLEANING_ALL = frozenset({"grupo", "encargado", "supervisor"})


class ScheduleError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "invalid", problems=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.problems = problems or []


@dataclass(frozen=True)
class Role:
    key: str    # "president" → columnas president_id, president_name y relación president
    label: str  # "Presidente", "Audio y video"
    noun: str   # para "el permiso de <noun>": "presidencia", "audio y video"
    flag: str   # columna booleana en students: "fds_presidente"


# ── Fechas ────────────────────────────────────────────────────────────────────

def is_saturday(day: date) -> bool:
    return day.weekday() == 5


def upcoming_saturday(day: date) -> date:
    """El sábado de la semana de day (el mismo día si ya es sábado; el domingo pasa al siguiente)."""
    return day + timedelta(days=(5 - day.weekday()) % 7)


def label_day(day: date) -> str:
    """15 DE AGOSTO, como en las hojas impresas."""
    return f"{day.day} DE {MONTHS[day.month - 1].upper()}"


def spoken_day(day: date) -> str:
    return f"{day.day} de {MONTHS[day.month - 1]}"


def require_saturday(day: date) -> date:
    if not is_saturday(day):
        raise ScheduleError(
            f"El {spoken_day(day)} de {day.year} no es sábado. Este programa va por sábados.",
            code="not_saturday",
        )
    return day


class SaturdaySchedule:
    """Lógica de un programa por sábados. El modelo debe tener date, <rol>_id y <rol>_name
    por cada rol, la relación <rol> con Student y, si usa reunión de entre semana,
    midweek_date."""

    def __init__(
        self,
        *,
        name: str,
        model,
        roles: list[Role],
        module_phrase: str,
        label: Callable[[date, Optional[date]], str],
        default_midweek: Optional[Callable[[date], date]] = None,
        extra_busy: Optional[Callable[[Session, list[date]], dict]] = None,
        cleaning_blocks: frozenset = CLEANING_ALL,
    ):
        self.name = name                    # "Fin de semana"
        self.model = model
        self.roles = roles
        self.role_by_key = {r.key: r for r in roles}
        self.module_phrase = module_phrase  # "del fin de semana", "de sonido"
        self.label = label
        self.default_midweek = default_midweek
        self.extra_busy = extra_busy
        self.cleaning_blocks = cleaning_blocks  # "grupo", "encargado", "supervisor"

    @property
    def has_midweek(self) -> bool:
        return self.default_midweek is not None

    # ── Reuniones que cubre cada fila ────────────────────────────────────────

    def resolve_midweek(self, saturday: date, midweek: Optional[date]) -> Optional[date]:
        if not self.has_midweek:
            return None
        if midweek is None:
            return self.default_midweek(saturday)
        if not (saturday < midweek <= saturday + timedelta(days=6)):
            raise ScheduleError(
                "La reunión de entre semana debe caer en los seis días siguientes al sábado.",
                code="invalid_midweek",
            )
        return midweek

    def meetings(self, saturday: date, midweek: Optional[date]) -> list[tuple[date, Optional[str]]]:
        """Fechas que se revisan y el sufijo de los motivos ("el martes 8")."""
        if midweek is None:
            return [(saturday, None)]
        return [
            (saturday, f"el sábado {saturday.day}"),
            (midweek, f"el {WEEKDAYS[midweek.weekday()]} {midweek.day}"),
        ]

    def busy_for_slots(self, db: Session, slots: list[tuple[date, Optional[date]]]) -> dict[date, dict[int, list[dict]]]:
        """slots: [(sábado, entre semana | None)] → {sábado: {student_id: [motivos]}}."""
        plans = {saturday: self.meetings(saturday, midweek) for saturday, midweek in slots}
        by_date = availability.busy_for_dates(db, {d for plan in plans.values() for d, _ in plan})
        extra = self.extra_busy(db, list(plans)) if self.extra_busy and plans else {}
        result: dict[date, dict[int, list[dict]]] = {}
        for saturday, plan in plans.items():
            out: dict[int, list[dict]] = {}
            for day, suffix in plan:
                for student_id, reasons in by_date.get(day, {}).items():
                    for reason in reasons:
                        if reason.get("aseo") and reason["aseo"] not in self.cleaning_blocks:
                            continue
                        label = f"{reason['label']} {suffix}" if suffix else reason["label"]
                        availability.add_reason(out, student_id, reason["kind"], label)
            for student_id, reasons in extra.get(saturday, {}).items():
                for reason in reasons:
                    availability.add_reason(out, student_id, reason["kind"], reason["label"])
            result[saturday] = out
        return result

    def busy_for(self, db: Session, saturday: date, midweek: Optional[date] = None) -> dict[int, list[dict]]:
        return self.busy_for_slots(db, [(saturday, self.resolve_midweek(saturday, midweek))])[saturday]

    # ── Estudiantes ──────────────────────────────────────────────────────────

    def eligibility_problem(self, student: Student, role: Role) -> Optional[str]:
        if student.status != "Activo":
            return f"{student.name} no está activo."
        if student.gender != 1:
            return f"{student.name} no está registrado como varón."
        if not getattr(student, role.flag):
            return f"{student.name} no tiene el permiso de {role.noun} {self.module_phrase}."
        return None

    def eligible(self, db: Session, role: Role) -> list[Student]:
        flag = getattr(Student, role.flag)
        return db.execute(
            select(Student)
            .where(flag.is_(True), Student.status == "Activo", Student.gender == 1)
            .order_by(Student.name)
        ).scalars().all()

    def _column(self, role: Role):
        return getattr(self.model, f"{role.key}_id")

    def last_dates(self, db: Session) -> dict[str, dict[int, date]]:
        last = {}
        for role in self.roles:
            column = self._column(role)
            rows = db.execute(
                select(column, func.max(self.model.date)).where(column.is_not(None)).group_by(column)
            ).all()
            last[role.key] = {student_id: day for student_id, day in rows}
        return last

    def counts(self, db: Session) -> dict[str, dict[int, int]]:
        counts = {}
        for role in self.roles:
            column = self._column(role)
            rows = db.execute(
                select(column, func.count()).where(column.is_not(None)).group_by(column)
            ).all()
            counts[role.key] = {student_id: n for student_id, n in rows}
        return counts

    # ── Lectura ──────────────────────────────────────────────────────────────

    def _person(self, row, role: Role):
        student = getattr(row, role.key)
        if student is not None:
            return {"id": student.id, "name": student.name, "linked": True}
        stored = getattr(row, f"{role.key}_name")
        if stored:
            return {"id": None, "name": stored, "linked": False}
        return None

    def _midweek_of(self, row) -> Optional[date]:
        return getattr(row, "midweek_date", None) if self.has_midweek else None

    def serialize(self, rows, busy_map: dict) -> list[dict]:
        out = []
        for row in rows:
            busy = busy_map.get(row.date, {})
            conflicts = []
            seen: dict[int, Role] = {}
            for role in self.roles:
                student_id = getattr(row, f"{role.key}_id")
                if student_id is None:
                    continue
                for reason in busy.get(student_id, []):
                    conflicts.append({"role": role.key, **reason})
                if student_id in seen:
                    conflicts.append({
                        "role": role.key,
                        "kind": "repetido",
                        "label": f"También está en {seen[student_id].label.lower()}",
                    })
                seen.setdefault(student_id, role)
            item = {
                "id": row.id,
                "date": row.date,
                "label": self.label(row.date, self._midweek_of(row)),
            }
            if self.has_midweek:
                item["midweek_date"] = row.midweek_date
            for role in self.roles:
                item[role.key] = self._person(row, role)
            item["conflicts"] = conflicts
            out.append(item)
        return out

    def list_rows(self, db: Session, start: Optional[date] = None, end: Optional[date] = None):
        query = select(self.model).options(*(selectinload(getattr(self.model, r.key)) for r in self.roles))
        if start:
            query = query.where(self.model.date >= start)
        if end:
            query = query.where(self.model.date <= end)
        return db.execute(query.order_by(self.model.date.asc())).scalars().all()

    def _busy_for_rows(self, db: Session, rows) -> dict:
        return self.busy_for_slots(db, [(r.date, self._midweek_of(r)) for r in rows])

    def list_with_conflicts(self, db: Session, start: Optional[date] = None, end: Optional[date] = None) -> list[dict]:
        rows = self.list_rows(db, start, end)
        return self.serialize(rows, self._busy_for_rows(db, rows))

    def get_with_conflicts(self, db: Session, row_id: int) -> dict:
        row = self._get(db, row_id)
        return self.serialize([row], self._busy_for_rows(db, [row]))[0]

    def public_rows(self, db: Session, start: Optional[date], weeks: int) -> dict:
        first = upcoming_saturday(start or date.today())
        last = first + timedelta(days=7 * (weeks - 1))
        rows = []
        for row in self.list_rows(db, first, last):
            item = {"date": row.date, "label": self.label(row.date, self._midweek_of(row))}
            if self.has_midweek:
                item["midweek_date"] = row.midweek_date
            for role in self.roles:
                person = self._person(row, role)
                item[role.key] = person["name"] if person else None
            rows.append(item)
        return {"start": first, "end": last, "rows": rows}

    # ── Candidatos ───────────────────────────────────────────────────────────

    def candidates(self, db: Session, saturday: date, exclude_id: Optional[int] = None,
                   midweek: Optional[date] = None) -> dict:
        require_saturday(saturday)
        midweek = self.resolve_midweek(saturday, midweek)
        busy = self.busy_for(db, saturday, midweek)
        last = self.last_dates(db)
        current = db.execute(select(self.model).where(self.model.date == saturday)).scalar_one_or_none()
        taken = set()
        if current is not None and current.id != exclude_id:
            taken = {getattr(current, f"{r.key}_id") for r in self.roles} - {None}

        monday, sunday = availability.week_bounds(saturday)
        out = {
            "date": saturday,
            "label": self.label(saturday, midweek),
            "week_start": monday,
            "week_end": sunday,
            "meetings": [
                {"date": day, "week_start": availability.week_bounds(day)[0], "week_end": availability.week_bounds(day)[1]}
                for day, _ in self.meetings(saturday, midweek)
            ],
        }
        if self.has_midweek:
            out["midweek_date"] = midweek
        for role in self.roles:
            items = []
            for student in self.eligible(db, role):
                reasons = list(busy.get(student.id, []))
                if student.id in taken:
                    reasons.append({"kind": "repetido", "label": "Ya tiene una parte este sábado"})
                items.append({
                    "id": student.id,
                    "name": student.name,
                    "available": not reasons,
                    "reasons": reasons,
                    "last_date": last[role.key].get(student.id),
                })
            items.sort(key=lambda c: (not c["available"], c["last_date"] or date.min, c["name"]))
            out[role.key] = items
        return out

    # ── Escritura ────────────────────────────────────────────────────────────

    def _get(self, db: Session, row_id: int):
        row = db.get(self.model, row_id)
        if row is None:
            raise ScheduleError("No se encontró ese sábado.", status_code=404, code="not_found")
        return row

    def _validate(self, db: Session, saturday: date, midweek: Optional[date],
                  changes: dict[str, Optional[int]], others: dict[str, Optional[int]]) -> dict[str, Student]:
        """Valida los roles de changes (rol → student_id | None). others son los que no cambian."""
        problems = []
        busy = None
        students: dict[str, Student] = {}
        for key, student_id in changes.items():
            if student_id is None:
                continue
            role = self.role_by_key[key]
            student = db.get(Student, student_id)
            if student is None:
                problems.append({"role": key, "code": "not_found", "message": "El estudiante elegido no existe."})
                continue
            students[key] = student
            problem = self.eligibility_problem(student, role)
            if problem:
                problems.append({"role": key, "code": "not_eligible", "message": problem})
                continue
            if busy is None:
                busy = self.busy_for(db, saturday, midweek)
            reasons = busy.get(student_id, [])
            if reasons:
                labels = ", ".join(r["label"].lower() for r in reasons)
                problems.append({
                    "role": key,
                    "code": "busy",
                    "message": f"{student.name} no está libre: {labels}.",
                    "reasons": reasons,
                })

        final = {**others, **changes}
        seen: dict[int, Role] = {}
        for role in self.roles:
            student_id = final.get(role.key)
            if student_id is None:
                continue
            if student_id in seen:
                problems.append({
                    "role": role.key,
                    "code": "same_person",
                    "message": f"Una misma persona no puede estar en {seen[student_id].label.lower()} y en {role.label.lower()} el mismo sábado.",
                })
            seen.setdefault(student_id, role)

        if problems:
            busy_only = all(p["code"] == "busy" for p in problems)
            raise ScheduleError(
                " ".join(p["message"] for p in problems),
                status_code=409 if busy_only else 400,
                code="busy" if busy_only else problems[0]["code"],
                problems=problems,
            )
        return students

    def create(self, db: Session, saturday: date, people: dict[str, Optional[int]],
               midweek: Optional[date] = None) -> dict:
        require_saturday(saturday)
        midweek = self.resolve_midweek(saturday, midweek)
        exists = db.execute(select(self.model.id).where(self.model.date == saturday)).scalar_one_or_none()
        if exists is not None:
            raise ScheduleError(
                f"El sábado {spoken_day(saturday)} ya está programado. Edítalo en la lista.",
                status_code=409,
                code="duplicate",
            )
        changes = {r.key: people.get(r.key) for r in self.roles}
        students = self._validate(db, saturday, midweek, changes, {})
        values = {"date": saturday}
        if self.has_midweek:
            values["midweek_date"] = midweek
        for role in self.roles:
            values[f"{role.key}_id"] = changes[role.key]
            values[f"{role.key}_name"] = students[role.key].name if role.key in students else None
        row = self.model(**values)
        db.add(row)
        db.commit()
        return self.get_with_conflicts(db, row.id)

    def update(self, db: Session, row_id: int, people: dict[str, Optional[int]],
               midweek: Optional[date] = None, midweek_sent: bool = False) -> dict:
        """people solo trae los roles enviados. Mandar null en un rol sin estudiante
        vinculado borra el nombre importado."""
        row = self._get(db, row_id)
        new_midweek = self._midweek_of(row)
        midweek_changed = False
        if self.has_midweek and midweek_sent:
            new_midweek = self.resolve_midweek(row.date, midweek)
            midweek_changed = new_midweek != row.midweek_date

        changes = {}
        for key, student_id in people.items():
            current_id = getattr(row, f"{key}_id")
            if student_id != current_id or (student_id is None and getattr(row, f"{key}_name")):
                changes[key] = student_id
        to_validate = dict(changes)
        if midweek_changed:
            # Cambian las semanas que se revisan: se validan de nuevo todos los asignados
            for role in self.roles:
                current_id = getattr(row, f"{role.key}_id")
                if current_id is not None:
                    to_validate.setdefault(role.key, current_id)
        others = {r.key: getattr(row, f"{r.key}_id") for r in self.roles if r.key not in to_validate}
        students = self._validate(db, row.date, new_midweek, to_validate, others)

        if midweek_changed:
            row.midweek_date = new_midweek
        for key, student_id in changes.items():
            setattr(row, f"{key}_id", student_id)
            setattr(row, f"{key}_name", students[key].name if key in students else None)
        db.commit()
        return self.get_with_conflicts(db, row.id)

    def delete(self, db: Session, row_id: int) -> None:
        db.delete(self._get(db, row_id))
        db.commit()

    def generate(self, db: Session, weeks: int, start: Optional[date] = None) -> dict:
        """Programa los próximos sábados sin tocar los que ya existen.

        Rota por antigüedad: primero quien hace más tiempo no tiene el rol y, a igualdad,
        quien hace más tiempo no tiene ninguna parte de este programa.
        """
        if start is None:
            last_saved = db.execute(select(func.max(self.model.date))).scalar()
            start = upcoming_saturday(date.today())
            if last_saved is not None and last_saved + timedelta(days=7) > start:
                start = last_saved + timedelta(days=7)
        else:
            start = upcoming_saturday(start)

        saturdays = [start + timedelta(days=7 * i) for i in range(weeks)]
        existing = set(db.execute(
            select(self.model.date).where(self.model.date.in_(saturdays))
        ).scalars().all())
        pending = [s for s in saturdays if s not in existing]
        slots = [(s, self.resolve_midweek(s, None)) for s in pending]
        busy_map = self.busy_for_slots(db, slots)

        pools = {role.key: self.eligible(db, role) for role in self.roles}
        last = self.last_dates(db)
        last_any: dict[int, date] = {}
        for per_role in last.values():
            for student_id, day in per_role.items():
                if day > last_any.get(student_id, date.min):
                    last_any[student_id] = day

        created, warnings = 0, []
        for saturday, midweek in slots:
            busy = busy_map.get(saturday, {})
            picked: dict[str, Optional[Student]] = {}
            # Primero el rol con menos candidatos libres, para no dejarlo sin nadie
            order = sorted(self.roles, key=lambda r: sum(1 for s in pools[r.key] if s.id not in busy))
            for role in order:
                taken = {s.id for s in picked.values() if s is not None}
                options = [s for s in pools[role.key] if s.id not in busy and s.id not in taken]
                options.sort(key=lambda s: (
                    last[role.key].get(s.id, date.min),
                    last_any.get(s.id, date.min),
                    random.random(),
                ))
                choice = options[0] if options else None
                picked[role.key] = choice
                if choice is None:
                    warnings.append(
                        f"{self.label(saturday, midweek)}: nadie libre para {role.label.lower()} "
                        f"(con permiso de {role.noun} y sin otra asignación esa semana)."
                    )
                else:
                    last[role.key][choice.id] = saturday
                    last_any[choice.id] = saturday
            values = {"date": saturday}
            if self.has_midweek:
                values["midweek_date"] = midweek
            for role in self.roles:
                student = picked[role.key]
                values[f"{role.key}_id"] = student.id if student else None
                values[f"{role.key}_name"] = student.name if student else None
            db.add(self.model(**values))
            created += 1
        db.commit()
        return {"start_date": start, "created": created, "skipped": sorted(existing), "warnings": warnings}

    # ── Permisos de los estudiantes ──────────────────────────────────────────

    def people(self, db: Session) -> list[dict]:
        """Varones activos (y cualquiera que conserve un permiso) con permisos y conteos."""
        flags = [getattr(Student, r.flag).is_(True) for r in self.roles]
        students = db.execute(
            select(Student).where(or_(and_(Student.gender == 1, Student.status == "Activo"), *flags))
            .order_by(Student.name)
        ).scalars().all()
        last = self.last_dates(db)
        counts = self.counts(db)
        out = []
        for s in students:
            item = {"id": s.id, "name": s.name, "status": s.status, "gender": s.gender}
            for role in self.roles:
                item[role.flag] = bool(getattr(s, role.flag))
                item[f"last_{role.key}"] = last[role.key].get(s.id)
                item[f"times_{role.key}"] = counts[role.key].get(s.id, 0)
            out.append(item)
        return out

    def set_flags(self, db: Session, student_id: int, values: dict[str, Optional[bool]]) -> Student:
        student = db.get(Student, student_id)
        if student is None:
            raise ScheduleError("El estudiante no existe.", status_code=404, code="not_found")
        enabling = any(v is True and not getattr(student, flag) for flag, v in values.items())
        if enabling and (student.gender != 1 or student.status != "Activo"):
            raise ScheduleError(
                f"{student.name} debe ser un varón activo para tener permisos {self.module_phrase}.",
                code="not_eligible",
            )
        for flag, value in values.items():
            if value is not None:
                setattr(student, flag, value)
        db.commit()
        db.refresh(student)
        return student
