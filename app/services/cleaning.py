import random
from datetime import timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, or_
from app.models.cleaning import CleaningHistory
from app.models.student import Student
from app.models.group import Group
from app.models.student_group import StudentGroup

# Secuencia base definida en duro (hardcoded) exacta e inalterable de 15 combinaciones
SECUENCIA_BASE = [
    (4, 5), (1, 6), (2, 5), (3, 4), (1, 5), (6, 4), (2, 3), (1, 4),
    (5, 3), (6, 2), (1, 3), (2, 4), (5, 6), (1, 2), (3, 6)
]

async def generate_cleaning_pairs(db: AsyncSession, n_parejas_a_generar: int = 5, start_date: str = None):
    """
    Genera e inserta emparejamientos cíclicos basándose en el historial de la base de datos
    y la secuencia base de 15 parejas.
    """
    # 1. Consultar el último registro insertado
    query = select(CleaningHistory).order_by(desc(CleaningHistory.id)).limit(1)
    result = await db.execute(query)
    last_record = result.scalar_one_or_none()

    start_index = 0
    current_date = date.today()

    if last_record:
        last_pair = (last_record.grupo1, last_record.grupo2)
        current_date = last_record.week_end + timedelta(days=1)
        try:
            current_index = SECUENCIA_BASE.index(last_pair)
            start_index = (current_index + 1) % len(SECUENCIA_BASE)
        except ValueError:
            start_index = 0

    if start_date:
        try:
            from datetime import datetime
            current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    nuevos_registros = []
    current_index = start_index

    # 2. Generar n_parejas_a_generar
    for _ in range(n_parejas_a_generar):
        g1_num, g2_num = SECUENCIA_BASE[current_index]
        end_date = current_date + timedelta(days=6)
        
async def _pick_cleaning_roles(db: AsyncSession, g1_num: int, g2_num: int):
    """Helper to pick an encargado and a supervisor from two group numbers."""
    # 1. Buscar los IDs de los grupos
    grp_query = select(Group).where(or_(
        Group.name.ilike(f"%{g1_num}%"),
        Group.name.ilike(f"%{g2_num}%")
    ))
    groups_res = await db.execute(grp_query)
    groups = groups_res.scalars().all()
    group_ids = [g.id for g in groups]
    
    if not group_ids:
        return None, None
        
    # 2. Obtener estudiantes de esos grupos
    students_query = select(Student).join(
        StudentGroup, Student.id == StudentGroup.student_id
    ).where(StudentGroup.group_id.in_(group_ids), Student.status == "Activo")
    students_res = await db.execute(students_query)
    students = students_res.scalars().all()
    
    # 3. Filtrar candidatos
    encargado_candidates = [s for s in students if s.aseo]
    supervisor_candidates = [
        s for s in students 
        if s.infoadd and any(keyword in s.infoadd.upper() for keyword in ["ANCIANO", "SIERVO"])
    ]
    
    encargado = random.choice(encargado_candidates) if encargado_candidates else None
    supervisor = random.choice(supervisor_candidates) if supervisor_candidates else None
    
    return encargado, supervisor

async def generate_cleaning_pairs(db: AsyncSession, n_parejas_a_generar: int = 5, start_date: str = None):
    """
    Genera e inserta emparejamientos cíclicos basándose en el historial de la base de datos
    y la secuencia base de 15 parejas.
    """
    query = select(CleaningHistory).order_by(desc(CleaningHistory.id)).limit(1)
    result = await db.execute(query)
    last_record = result.scalar_one_or_none()

    start_index = 0
    current_date = date.today()

    if start_date:
        try:
            from datetime import datetime
            current_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    if last_record:
        last_pair = (last_record.grupo1, last_record.grupo2)
        current_date = last_record.week_end + timedelta(days=1)
        try:
            current_index = SECUENCIA_BASE.index(last_pair)
            start_index = (current_index + 1) % len(SECUENCIA_BASE)
        except ValueError:
            start_index = 0

    nuevos_registros = []
    current_index = start_index

    for _ in range(n_parejas_a_generar):
        g1_num, g2_num = SECUENCIA_BASE[current_index]
        end_date = current_date + timedelta(days=6)
        
        encargado, supervisor = await _pick_cleaning_roles(db, g1_num, g2_num)
        
        nuevo_registro = CleaningHistory(
            grupo1=g1_num,
            grupo2=g2_num,
            week_start=current_date,
            week_end=end_date,
            encargado_id=encargado.id if encargado else None,
            supervisor_id=supervisor.id if supervisor else None
        )
        nuevos_registros.append(nuevo_registro)
        
        current_index = (current_index + 1) % len(SECUENCIA_BASE)
        current_date = end_date + timedelta(days=1)

    if nuevos_registros:
        db.add_all(nuevos_registros)
        await db.commit()
        
    return [{"grupo1": r.grupo1, "grupo2": r.grupo2, "week_start": r.week_start, "week_end": r.week_end} for r in nuevos_registros]

async def get_cleaning_history(db: AsyncSession, limit: int = 20):
    """
    Obtiene los últimos N registros de limpieza con sus encargados y supervisores.
    """
    from sqlalchemy.orm import selectinload
    query = select(CleaningHistory).options(
        selectinload(CleaningHistory.encargado),
        selectinload(CleaningHistory.supervisor)
    ).order_by(desc(CleaningHistory.id)).limit(limit)
    
    result = await db.execute(query)
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
