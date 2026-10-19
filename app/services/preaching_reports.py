import secrets
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Set
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.group import Group
from app.models.student import Student
from app.models.student_group import StudentGroup
from app.models.preaching_report import PreachingReport, GroupReportLink
from app.schemas.preaching_report import (
    GroupLinkOut,
    PioneerMonth,
    PioneerPerson,
    PioneerYear,
    PreachingReportIn,
    PreachingReportGroup,
    PreachingReportRow,
    PreachingReportsMonth,
)


def parse_month(value: str) -> date:
    """'2026-09' -> date(2026, 9, 1)"""
    year, month = value.split("-")
    return date(int(year), int(month), 1)


# ─── Año de servicio ─────────────────────────────────────────────────────────
# El año de servicio va de septiembre a agosto: el año de servicio 2027 es de
# septiembre 2026 a agosto 2027. Solo está disponible el año de servicio del mes
# cuyos informes se están recogiendo (el mes anterior), así en septiembre todavía
# se pueden terminar los informes de agosto.

COLOMBIA = timezone(timedelta(hours=-5))  # Colombia no tiene horario de verano


def current_service_year(today: Optional[date] = None) -> int:
    today = today or datetime.now(COLOMBIA).date()
    report_month = today.replace(day=1) - timedelta(days=1)  # mes anterior
    return report_month.year + 1 if report_month.month >= 9 else report_month.year


def service_year_bounds(service_year: int):
    return date(service_year - 1, 9, 1), date(service_year, 8, 1)


def ensure_month_available(month: date) -> None:
    sy = current_service_year()
    first, last = service_year_bounds(sy)
    if not first <= month <= last:
        raise HTTPException(
            status_code=400,
            detail=f"Solo está disponible el año de servicio {sy} (septiembre {sy - 1} a agosto {sy}).",
        )


def _sort_key(name: str) -> str:
    # Orden alfabético sin importar tildes ni mayúsculas
    normalized = unicodedata.normalize("NFKD", name or "")
    return "".join(c for c in normalized if not unicodedata.combining(c)).casefold()


def pioneer_status(student: Student) -> Optional[str]:
    """Precursorado fijo según Estudiantes: regular o auxiliar indefinido.

    La campaña no cuenta aquí: es solo del mes en que se asigna y queda guardada
    en el informe de ese mes (PreachingReport.pioneer_status).
    """
    if student.es_precursor_reg:
        return "regular"
    if student.es_precursor_aux_ind:
        return "aux_ind"
    return None


def report_status(publisher_type: str, stored: Optional[str], student: Student) -> Optional[str]:
    """Precursorado de un informe guardado. Si el informe es anterior a guardar el
    precursorado del mes, un auxiliar es indefinido si así está en Estudiantes y si no, de campaña."""
    if publisher_type == "regular":
        return "regular"
    if publisher_type == "auxiliar":
        if stored in ("aux_ind", "aux_camp"):
            return stored
        return "aux_ind" if student.es_precursor_aux_ind else "aux_camp"
    return None


def type_from_status(status: Optional[str]) -> str:
    """Tipo de publicador para el informe a partir del precursorado."""
    if status == "regular":
        return "regular"
    if status in ("aux_ind", "aux_camp"):
        return "auxiliar"
    return "publicador"


def group_member_ids(db: Session, group_id: UUID) -> Set[int]:
    return set(
        db.execute(select(StudentGroup.student_id).where(StudentGroup.group_id == group_id)).scalars().all()
    )


def _members_by_group(db: Session, only_group_id: Optional[UUID] = None):
    """Grupos (en orden) y sus integrantes. Si alguien quedó en dos grupos, cuenta solo en el primero."""
    groups_stmt = select(Group).order_by(Group.created_at)
    memberships_stmt = (
        select(StudentGroup.group_id, Student)
        .join(Student, Student.id == StudentGroup.student_id)
        .join(Group, Group.id == StudentGroup.group_id)
        .order_by(Group.created_at, StudentGroup.created_at)
    )
    if only_group_id is not None:
        groups_stmt = groups_stmt.where(Group.id == only_group_id)
        memberships_stmt = memberships_stmt.where(StudentGroup.group_id == only_group_id)

    groups = db.execute(groups_stmt).scalars().all()
    members_by_group: Dict = {}
    seen_students = set()
    for group_id, student in db.execute(memberships_stmt).all():
        if student.id in seen_students:
            continue
        seen_students.add(student.id)
        members_by_group.setdefault(group_id, []).append(student)
    return groups, members_by_group


def get_month_reports(db: Session, month: date, only_group_id: Optional[UUID] = None) -> PreachingReportsMonth:
    groups, members_by_group = _members_by_group(db, only_group_id)

    student_ids = [st.id for members in members_by_group.values() for st in members]
    reports = {}
    if student_ids:
        reports = {
            r.student_id: r
            for r in db.execute(
                select(PreachingReport).where(
                    PreachingReport.month == month,
                    PreachingReport.student_id.in_(student_ids),
                )
            ).scalars().all()
        }

    result_groups: List[PreachingReportGroup] = []
    for grp in groups:
        members = members_by_group.get(grp.id, [])
        # En la vista general se omiten grupos vacíos; con el link de un grupo se muestra igual
        if not members and only_group_id is None:
            continue
        rows = []
        for student in sorted(members, key=lambda m: _sort_key(m.name)):
            r = reports.get(student.id)
            if r:
                rows.append(PreachingReportRow(
                    student_id=student.id,
                    name=student.name,
                    publisher_type=r.publisher_type,
                    participated=r.participated,
                    hours=r.hours,
                    bible_studies=r.bible_studies,
                    sacred_service_hours=r.sacred_service_hours,
                    observations=r.observations,
                    saved=True,
                    pioneer_status=report_status(r.publisher_type, r.pioneer_status, student),
                ))
            else:
                # Sin informe todavía: el tipo sale del precursorado fijo de Estudiantes
                # (regular o indefinido; la campaña solo aparece en el mes asignado)
                status = pioneer_status(student)
                rows.append(PreachingReportRow(
                    student_id=student.id,
                    name=student.name,
                    publisher_type=type_from_status(status),
                    pioneer_status=status,
                ))
        result_groups.append(PreachingReportGroup(id=grp.id, name=grp.name, rows=rows))

    return PreachingReportsMonth(month=month.strftime("%Y-%m"), groups=result_groups)


def service_year_months(service_year: int) -> List[date]:
    """Los 12 meses del año de servicio, de septiembre a agosto."""
    first, _ = service_year_bounds(service_year)
    return [date(first.year + (first.month - 1 + i) // 12, (first.month - 1 + i) % 12 + 1, 1) for i in range(12)]


def get_pioneer_year(db: Session, until: date) -> PioneerYear:
    """Cada persona que es o fue precursora en el año de servicio, con su precursorado
    y sus horas mes a mes. Cada mes se lee igual que en la planilla: el informe guardado
    o, si no hay, el precursorado fijo de Estudiantes. Las metas se calculan en la vista."""
    sy = current_service_year()
    months = service_year_months(sy)
    groups, members_by_group = _members_by_group(db)
    members = [(grp, st) for grp in groups for st in members_by_group.get(grp.id, [])]

    reports = {}
    if members:
        for r in db.execute(
            select(PreachingReport).where(
                PreachingReport.month >= months[0],
                PreachingReport.month <= months[-1],
                PreachingReport.student_id.in_([st.id for _, st in members]),
            )
        ).scalars().all():
            reports[(r.student_id, r.month)] = r

    people: List[PioneerPerson] = []
    for grp, st in members:
        fixed = pioneer_status(st)
        entries = []
        for m in months:
            r = reports.get((st.id, m))
            if r:
                entries.append(PioneerMonth(
                    month=m.strftime("%Y-%m"),
                    status=report_status(r.publisher_type, r.pioneer_status, st),
                    saved=True,
                    hours=r.hours,
                    sacred_service_hours=r.sacred_service_hours,
                ))
            else:
                entries.append(PioneerMonth(month=m.strftime("%Y-%m"), status=fixed))
        if any(e.status for e in entries):
            people.append(PioneerPerson(student_id=st.id, name=st.name, group_name=grp.name, months=entries))

    people.sort(key=lambda p: _sort_key(p.name))
    return PioneerYear(
        service_year=sy,
        until=until.strftime("%Y-%m"),
        months=[m.strftime("%Y-%m") for m in months],
        people=people,
    )


def save_month_reports(
    db: Session,
    month: date,
    reports: List[PreachingReportIn],
    allowed_student_ids: Optional[Set[int]] = None,
    type_locked: bool = False,
    allow_status_change: bool = False,
) -> None:
    """Guarda los informes del mes.

    Cada informe guarda el precursorado de ese mes (pioneer_status). Si no se cambia,
    se mantiene el del informe ya guardado o, si es nuevo, sale del precursorado fijo
    de Estudiantes (regular o indefinido).

    type_locked=True (link del encargado): el tipo no lo elige quien guarda.

    allow_status_change=True (panel del admin): si un informe trae pioneer_status, ese es
    el precursorado del mes. Regular, indefinido o publicador también se guardan en
    Estudiantes (salvo al corregir un mes anterior); la campaña no, porque es solo de ese mes.
    """
    if not reports:
        return

    ids = {r.student_id for r in reports}
    if allowed_student_ids is not None:
        outside = ids - allowed_student_ids
        if outside:
            raise HTTPException(status_code=403, detail="Solo puedes guardar informes de las personas de tu grupo.")

    students = {st.id: st for st in db.execute(select(Student).where(Student.id.in_(ids))).scalars().all()}
    missing = ids - set(students)
    if missing:
        raise HTTPException(status_code=400, detail=f"Personas no encontradas: {sorted(missing)}")

    # Si llega la misma persona dos veces, gana la última
    by_student = {r.student_id: r for r in reports}

    # Precursorado que ya tiene cada uno este mes (informe guardado o, si no hay, Estudiantes)
    saved = {
        sid: (ptype, stored)
        for sid, ptype, stored in db.execute(
            select(PreachingReport.student_id, PreachingReport.publisher_type, PreachingReport.pioneer_status).where(
                PreachingReport.month == month, PreachingReport.student_id.in_(ids)
            )
        ).all()
    }

    def current_status(st: Student) -> Optional[str]:
        if st.id in saved:
            return report_status(saved[st.id][0], saved[st.id][1], st)
        return pioneer_status(st)

    # Cambios de precursorado pedidos desde la planilla del admin
    status_changes: Dict[int, Optional[str]] = {}
    if allow_status_change and not type_locked:
        status_changes = {
            r.student_id: r.pioneer_status
            for r in by_student.values()
            if "pioneer_status" in r.model_fields_set
        }

    values = []
    for r in by_student.values():
        st = students[r.student_id]
        obs = (r.observations or "").strip() or None
        if r.student_id in status_changes:
            status = status_changes[r.student_id]
        else:
            status = current_status(st)
            # Compatibilidad: el admin todavía puede mandar solo publisher_type
            if not type_locked and r.publisher_type != type_from_status(status):
                status = report_status(r.publisher_type, None, st)
        publisher_type = type_from_status(status)
        hours, participated = r.hours, r.participated
        if type_locked:
            # Publicadores: solo SP/NP. Precursores: horas (participó si tiene horas)
            if publisher_type == "publicador":
                hours = None
            else:
                participated = None if hours is None else hours > 0
        values.append({
            "student_id": r.student_id,
            "month": month,
            "publisher_type": publisher_type,
            "pioneer_status": status,
            "participated": participated,
            "hours": hours,
            "bible_studies": r.bible_studies,
            "sacred_service_hours": r.sacred_service_hours,
            "observations": obs,
        })

    stmt = pg_insert(PreachingReport).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_preaching_reports_student_month",
        set_={
            "publisher_type": stmt.excluded.publisher_type,
            "pioneer_status": stmt.excluded.pioneer_status,
            "participated": stmt.excluded.participated,
            "hours": stmt.excluded.hours,
            "bible_studies": stmt.excluded.bible_studies,
            "sacred_service_hours": stmt.excluded.sacred_service_hours,
            "observations": stmt.excluded.observations,
            "updated_at": func.now(),
        },
    )
    db.execute(stmt)

    # Actualizar Estudiantes (como mucho una marca en True). La campaña es solo de este
    # mes: no cambia el precursorado fijo de la persona. Tampoco se cambia si la persona
    # ya tiene un informe de un mes posterior (sin contar campañas): corregir un mes
    # anterior solo corrige ese mes.
    fixed_changes = {sid: s for sid, s in status_changes.items() if s != "aux_camp"}
    newer = set()
    if fixed_changes:
        newer = set(db.execute(
            select(PreachingReport.student_id).where(
                PreachingReport.student_id.in_(list(fixed_changes)),
                PreachingReport.month > month,
                or_(PreachingReport.pioneer_status.is_(None), PreachingReport.pioneer_status != "aux_camp"),
            )
        ).scalars().all())
    for sid, status in fixed_changes.items():
        if sid in newer:
            continue
        st = students[sid]
        st.es_precursor_reg = status == "regular"
        st.es_precursor_aux_ind = status == "aux_ind"
        st.es_precursor_aux_camp = False

    db.commit()


# ─── Links secretos por grupo ────────────────────────────────────────────────

def _new_token() -> str:
    # 128 bits aleatorios: imposible de adivinar
    return secrets.token_urlsafe(16)


def get_group_links(db: Session) -> List[GroupLinkOut]:
    """Link de cada grupo (se crea la primera vez que se pide)."""
    groups = db.execute(select(Group).order_by(Group.created_at)).scalars().all()
    links = {l.group_id: l for l in db.execute(select(GroupReportLink)).scalars().all()}
    counts = dict(
        db.execute(select(StudentGroup.group_id, func.count()).group_by(StudentGroup.group_id)).all()
    )

    created = False
    for grp in groups:
        if grp.id not in links:
            link = GroupReportLink(group_id=grp.id, token=_new_token())
            db.add(link)
            links[grp.id] = link
            created = True
    if created:
        db.commit()

    return [
        GroupLinkOut(group_id=g.id, name=g.name, token=links[g.id].token, members=counts.get(g.id, 0))
        for g in groups
    ]


def regenerate_group_link(db: Session, group_id: UUID) -> GroupLinkOut:
    """Cambia el link de un grupo; el anterior deja de funcionar."""
    grp = db.get(Group, group_id)
    if not grp:
        raise HTTPException(status_code=404, detail="Grupo no encontrado")
    link = db.get(GroupReportLink, group_id)
    if link:
        link.token = _new_token()
    else:
        link = GroupReportLink(group_id=group_id, token=_new_token())
        db.add(link)
    db.commit()
    return GroupLinkOut(group_id=grp.id, name=grp.name, token=link.token, members=len(group_member_ids(db, grp.id)))


def get_group_by_token(db: Session, token: str) -> Optional[Group]:
    link = db.execute(select(GroupReportLink).where(GroupReportLink.token == token)).scalar_one_or_none()
    if not link:
        return None
    return db.get(Group, link.group_id)
