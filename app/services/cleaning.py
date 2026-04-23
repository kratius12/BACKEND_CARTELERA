from datetime import timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.cleaning import CleaningHistory

# Secuencia base definida en duro (hardcoded) exacta e inalterable de 15 combinaciones
SECUENCIA_BASE = [
    (4, 5), (1, 6), (2, 5), (3, 4), (1, 5), (6, 4), (2, 3), (1, 4),
    (5, 3), (6, 2), (1, 3), (2, 4), (5, 6), (1, 2), (3, 6)
]

async def generate_cleaning_pairs(db: AsyncSession, n_parejas_a_generar: int = 5, start_date: str = None):
    """
    Genera e inserta emparejamientos cíclicos basándose en el historial de la base de datos
    y la secuencia base de 15 parejas. Permite recibir un start_date (YYYY-MM-DD) si la tabla está vacía.
    """
    # 1. Consultar el último registro insertado (ordenado por id descendente)
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
        # Caso B o C (Tabla con datos): identificar la pareja y encontrar su posición
        last_pair = (last_record.grupo1, last_record.grupo2)
        
        # Calcular fecha siguiente basándose en el último registro
        current_date = last_record.week_end + timedelta(days=1)
        
        try:
            # Encontrar en qué posición de la secuencia base está el último insertado
            current_index = SECUENCIA_BASE.index(last_pair)
            # El siguiente a insertar es el inmediatamente posterior (con índice circular)
            start_index = (current_index + 1) % len(SECUENCIA_BASE)
        except ValueError:
            # Fallback en caso de que en la tabla exista una pareja anómala
            start_index = 0

    nuevos_registros = []
    current_index = start_index

    # 2. Generar n_parejas_a_generar utilizando un índice circular
    for _ in range(n_parejas_a_generar):
        g1, g2 = SECUENCIA_BASE[current_index]
        
        end_date = current_date + timedelta(days=6)
        
        nuevo_registro = CleaningHistory(
            grupo1=g1,
            grupo2=g2,
            week_start=current_date,
            week_end=end_date
        )
        nuevos_registros.append(nuevo_registro)
        
        # Avanzar el índice de forma circular (volver al inicio si pasa de 14)
        current_index = (current_index + 1) % len(SECUENCIA_BASE)
        
        # Avanzar fechas
        current_date = end_date + timedelta(days=1)

    # 3. Guardar en base de datos
    if nuevos_registros:
        db.add_all(nuevos_registros)
        await db.commit()
        
    # Devolver las parejas generadas para mostrarlas al frontend
    return [{"grupo1": r.grupo1, "grupo2": r.grupo2, "week_start": r.week_start, "week_end": r.week_end} for r in nuevos_registros]

async def get_cleaning_history(db: AsyncSession, limit: int = 20):
    """
    Obtiene los últimos N registros de limpieza ordenados por los más recientes.
    """
    query = select(CleaningHistory).order_by(desc(CleaningHistory.id)).limit(limit)
    result = await db.execute(query)
    records = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "grupo1": r.grupo1,
            "grupo2": r.grupo2,
            "week_start": r.week_start,
            "week_end": r.week_end,
            "created_at": r.created_at
        }
        for r in records
    ]
