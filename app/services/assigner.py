import random
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from app.models.student import Student
from app.models.program import MeetingProgram

async def fetch_historical_data(db: AsyncSession):
    # 1. Traer los ultimos 5 programas publicados para marcar descansos
    query_last_5 = select(MeetingProgram).order_by(desc(MeetingProgram.week_start)).limit(5)
    result_5 = await db.execute(query_last_5)
    last_5_programs = result_5.scalars().all()

    # Extraer names que participaron en los últimos 5 programas
    recent_names = set()
    historical_pairs = set()

    # Para historical pairs, idealmente traemos TODO el histórico, 
    # pero para optimizar podemos traer los ultimos 50 o todos si no son muchos.
    query_all = select(MeetingProgram)
    result_all = await db.execute(query_all)
    all_programs = result_all.scalars().all()

    def add_pair(n1, n2):
        if n1 and n2:
            pair = tuple(sorted([n1.strip().lower(), n2.strip().lower()]))
            historical_pairs.add(pair)

    # Llenar historial de parejas con todos los programas
    for prog in all_programs:
        payload = prog.payload
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except:
                continue
        parts = payload.get("parts", [])
        for part in parts:
            if part.get("type") == "section":
                for item in part.get("items", []):
                    assigned = item.get("assigned", [])
                    if len(assigned) >= 2:
                        add_pair(assigned[0], assigned[1])

    # Llenar descansos con los ultimos 5 programas
    for prog in last_5_programs:
        payload = prog.payload
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except:
                continue
        parts = payload.get("parts", [])
        for part in parts:
            if part.get("type") == "section":
                for item in part.get("items", []):
                    assigned = item.get("assigned", [])
                    for name in assigned:
                        if name and name.strip():
                            recent_names.add(name.strip().lower())

    return recent_names, historical_pairs

async def generate_proposal(db: AsyncSession, items: list):
    # Obtener data historica
    recent_names, historical_pairs = await fetch_historical_data(db)

    # Obtener todos los estudiantes activos
    result = await db.execute(select(Student).filter(Student.status.ilike('activo')))
    active_students = result.scalars().all()

    # Mezclar aleatoriamente
    random.shuffle(active_students)

    # Separar por sexo y filtrar estudiantes válidos (no descanso, sexo definido)
    available_men = []
    available_women = []

    for s in active_students:
        name_clean = s.name.strip().lower()
        if name_clean in recent_names:
            continue # En descanso
        if s.gender == 1:
            available_men.append(s)
        elif s.gender == 0:
            available_women.append(s)

    used_in_session = set()
    discursos_assigned = 0

    def get_available(pool):
        return [p for p in pool if p.name not in used_in_session]

    output_items = []

    for item in items:
        new_item = dict(item)  # copiar
        title = (item.get("text") or "").lower()
        
        is_discurso = False
        is_demostracion = False

        if "empiece" in title or "haga" in title or "explique" in title:
            is_demostracion = True
        else:
            is_discurso = True # Asumimos discurso u otra tarea individual si no es demostracion, el prompt implicaba q los q no son parejas son discursos
            
        if item.get("type") == "song" or not title:
            output_items.append(new_item)
            continue
            
        # Si es demostración explícita según palabras clave
        if is_demostracion:
            # 50/50 Men or Women pool
            primary_pool = available_men if random.random() < 0.5 else available_women
            secondary_pool = available_women if primary_pool is available_men else available_men
            
            def find_pair_in_pool(pool):
                current_pool = get_available(pool)
                for i in range(len(current_pool)):
                    for j in range(i + 1, len(current_pool)):
                        p1, p2 = current_pool[i], current_pool[j]
                        pair_tuple = tuple(sorted([p1.name.strip().lower(), p2.name.strip().lower()]))
                        if pair_tuple not in historical_pairs:
                            return (p1, p2)
                return None
            
            # Intentar encontrar una pareja válida en el pool primario
            found_pair = find_pair_in_pool(primary_pool)
            
            # Si falló, intentar con la OTRA pool como fallback
            if not found_pair:
                found_pair = find_pair_in_pool(secondary_pool)
            
            if found_pair:
                used_in_session.add(found_pair[0].name)
                used_in_session.add(found_pair[1].name)
                new_item["assigned"] = [found_pair[0].name, found_pair[1].name]
            else:
                new_item["assigned"] = ["❌ Parejas agotadas", "❌ No disponible"]
                
        else:
            # DISCURSO (O individual)
            if discursos_assigned >= 3:
                new_item["assigned"] = ["❌ Máximo 3 discursos limit", ""]
            else:
                men_pool = get_available(available_men)
                if men_pool:
                    selected = men_pool[0]
                    used_in_session.add(selected.name)
                    new_item["assigned"] = [selected.name, ""]
                    discursos_assigned += 1
                else:
                    new_item["assigned"] = ["❌ No disponible (sexo 1)", ""]
                    
        output_items.append(new_item)

    return output_items
