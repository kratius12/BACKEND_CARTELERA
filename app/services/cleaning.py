import random
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, or_, func
from sqlalchemy.orm import selectinload
from app.models.cleaning import CleaningHistory
from app.models.student import Student
from app.models.group import Group
from app.models.student_group import StudentGroup

# Secuencia base definida en duro (hardcoded) exacta e inalterable de 15 combinaciones
SECUENCIA_BASE = [
    (4, 5), (1, 6), (2, 5), (3, 4), (1, 5), (6, 4), (2, 3), (1, 4),
    (5, 3), (6, 2), (1, 3), (2, 4), (5, 6), (1, 2), (3, 6)
]

def _get_group_ids_by_numbers(db: Session, g1_num: int, g2_num: int):
    grp_query = select(Group).where(or_(
        Group.name.ilike(f"%{g1_num}%"),
        Group.name.ilike(f"%{g2_num}%")
    ))
    groups_res = db.execute(grp_query)
    groups = groups_res.scalars().all()
    return [g.id for g in groups]

def _get_last_role_dates(db: Session, student_ids: list[int], role_field: str):
    if not student_ids:
        return {}

    role_col = getattr(CleaningHistory, role_field)
    stmt = (
        select(role_col, func.max(CleaningHistory.week_end))
        .where(role_col.in_(student_ids))
        .group_by(role_col)
    )
    res = db.execute(stmt)
    return {student_id: last_date for student_id, last_date in res.all()}

def _sort_by_least_recent(candidates: list[Student], last_dates: dict[int, date]) -> list[Student]:
    def sort_key(student: Student):
        last = last_dates.get(student.id)
        return (last or date.min, random.random())
    return sorted(candidates, key=sort_key)

def _is_elder(student: Student) -> bool:
    return bool(student.es_anciano)

def _is_ministerial(student: Student) -> bool:
    return bool(student.es_siervo)

def _pick_cleaning_roles(db: Session, g1_num: int, g2_num: int):
    """Helper to pick an encargado and a supervisor from two group numbers."""
    group_ids = _get_group_ids_by_numbers(db, g1_num, g2_num)
    if not group_ids:
        return None, None

    students_query = select(Student).join(
        StudentGroup, Student.id == StudentGroup.student_id
    ).where(StudentGroup.group_id.in_(group_ids), Student.status == "Activo")
    students_res = db.execute(students_query)
    students = students_res.scalars().all()

    if not students:
        return None, None

    encargado_candidates = [s for s in students if s.aseo]
    supervisor_candidates = [s for s in students if _is_elder(s) or _is_ministerial(s)]

    encargado = None
    supervisor = None

    if encargado_candidates:
        encargado_last_dates = _get_last_role_dates(db, [s.id for s in encargado_candidates], "encargado_id")
        sorted_encargados = _sort_by_least_recent(encargado_candidates, encargado_last_dates)
        encargado = sorted_encargados[0]

    if supervisor_candidates:
        elder_candidates = [s for s in supervisor_candidates if _is_elder(s)]
        ministerial_candidates = [s for s in supervisor_candidates if _is_ministerial(s) and not _is_elder(s)]
        selected_group = elder_candidates or ministerial_candidates

        if selected_group:
            supervisor_last_dates = _get_last_role_dates(db, [s.id for s in selected_group], "supervisor_id")
            sorted_supervisors = _sort_by_least_recent(selected_group, supervisor_last_dates)
            supervisor = sorted_supervisors[0]

    if encargado and supervisor and encargado.id == supervisor.id:
        alternative = [s for s in supervisor_candidates if s.id != encargado.id]
        if alternative:
            supervisor_last_dates = _get_last_role_dates(db, [s.id for s in alternative], "supervisor_id")
            sorted_alternatives = _sort_by_least_recent(alternative, supervisor_last_dates)
            supervisor = sorted_alternatives[0]

    return encargado, supervisor

def generate_cleaning_pairs(db: Session, n_parejas_a_generar: int = 5, start_date: str = None):
    """
    Genera e inserta emparejamientos cíclicos basándose en el historial de la base de datos
    y la secuencia base de 15 parejas.
    """
    query = select(CleaningHistory).order_by(desc(CleaningHistory.id)).limit(1)
    result = db.execute(query)
    last_record = result.scalar_one_or_none()

    start_index = 0
    current_date = date.today()

    if last_record:
        last_pair = (last_record.grupo1, last_record.grupo2)
        # Continuar desde el último registro solo si no se forzó una fecha
        if not start_date:
            current_date = last_record.week_end + timedelta(days=1)
        try:
            current_index = SECUENCIA_BASE.index(last_pair)
            start_index = (current_index + 1) % len(SECUENCIA_BASE)
        except ValueError:
            start_index = 0

    # start_date explícito siempre tiene prioridad sobre la fecha calculada
    if start_date:
        try:
            current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Guardamos los nombres junto al registro para no acceder a relaciones post-commit
    registros_con_nombres = []
    current_index = start_index

    for _ in range(n_parejas_a_generar):
        g1_num, g2_num = SECUENCIA_BASE[current_index]
        end_date = current_date + timedelta(days=6)

        encargado, supervisor = _pick_cleaning_roles(db, g1_num, g2_num)

        nuevo_registro = CleaningHistory(
            grupo1=g1_num,
            grupo2=g2_num,
            week_start=current_date,
            week_end=end_date,
            encargado_id=encargado.id if encargado else None,
            supervisor_id=supervisor.id if supervisor else None
        )
        # Capturar nombres ANTES del commit (evita lazy-load en contexto async)
        registros_con_nombres.append((
            nuevo_registro,
            encargado.name if encargado else "N/A",
            supervisor.name if supervisor else "N/A",
        ))

        current_index = (current_index + 1) % len(SECUENCIA_BASE)
        current_date = end_date + timedelta(days=1)

    nuevos_registros = [r for r, _, _ in registros_con_nombres]
    if nuevos_registros:
        db.add_all(nuevos_registros)
        db.commit()

    return [
        {
            "id": r.id,
            "grupo1": r.grupo1,
            "grupo2": r.grupo2,
            "week_start": r.week_start,
            "week_end": r.week_end,
            "encargado": enc_name,
            "supervisor": sup_name,
        }
        for r, enc_name, sup_name in registros_con_nombres
    ]

def assign_cleaning_roles_for_week(db: Session, reference_date: str = None):
    """
    Asigna encargados y supervisores a todos los registros de aseo que aún no tienen
    uno o ambos roles.
    """
    query = select(CleaningHistory).options(
        selectinload(CleaningHistory.encargado),
        selectinload(CleaningHistory.supervisor)
    ).where(
        or_(CleaningHistory.encargado_id == None, CleaningHistory.supervisor_id == None)
    )
    result = db.execute(query)
    records = result.scalars().all()

    if not records:
        return []

    changed = False
    updated_records = []

    for record in records:
        if not record.encargado_id or not record.supervisor_id:
            encargado, supervisor = _pick_cleaning_roles(db, record.grupo1, record.grupo2)

            if not record.encargado_id and encargado:
                record.encargado_id = encargado.id
                record.encargado = encargado
                changed = True
            if not record.supervisor_id and supervisor:
                record.supervisor_id = supervisor.id
                record.supervisor = supervisor
                changed = True

        updated_records.append(
            {
                "id": record.id,
                "grupo1": record.grupo1,
                "grupo2": record.grupo2,
                "week_start": record.week_start,
                "week_end": record.week_end,
                "encargado": record.encargado.name if record.encargado else "N/A",
                "supervisor": record.supervisor.name if record.supervisor else "N/A"
            }
        )

    if changed:
        db.commit()

    return updated_records

def get_cleaning_history(db: Session, limit: int = 20):
    """
    Obtiene los últimos N registros de limpieza con sus encargados y supervisores.
    """
    query = select(CleaningHistory).options(
        selectinload(CleaningHistory.encargado),
        selectinload(CleaningHistory.supervisor)
    ).order_by(desc(CleaningHistory.id)).limit(limit)

    result = db.execute(query)
    records = result.scalars().all()

    return [
        {
            "id": r.id,
            "grupo1": r.grupo1,
            "grupo2": r.grupo2,
            "week_start": r.week_start,
            "week_end": r.week_end,
            "encargado": r.encargado.name if r.encargado else "N/A",
            "supervisor": r.supervisor.name if r.supervisor else "N/A",
            "created_at": r.created_at
        }
        for r in records
    ]
