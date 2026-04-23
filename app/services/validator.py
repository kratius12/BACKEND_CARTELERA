from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.program import AssignmentHistory, MeetingProgram
from app.models.student import Student
from collections import defaultdict

async def validate_program_payload(db: AsyncSession, payload: dict, prog_id: int = None):
    warnings = []
    
    parts = payload.get("parts", [])
    
    # 1. Extraer todas las asignaciones del payload
    assignments = []
    discursos_count = 0
    name_counts = defaultdict(int)
    
    for part in parts:
        if part.get("type") == "section":
            for item in part.get("items", []):
                assigned = item.get("assigned", [])
                
                title = (item.get("text") or "").lower()
                is_demostracion = "empiece" in title or "haga" in title or "explique" in title
                part_type = "demostracion" if is_demostracion else "discurso"

                student = assigned[0] if len(assigned) > 0 else None
                assistant = assigned[1] if len(assigned) > 1 else None
                
                # Ignorar si dice "❌ ..."
                if student and "❌" in student: student = None
                if assistant and "❌" in assistant: assistant = None
                
                if student: student = student.strip()
                if assistant: assistant = assistant.strip()

                if student or assistant:
                    assignments.append({
                        "title": title,
                        "part_type": part_type,
                        "student": student,
                        "assistant": assistant
                    })
                    
                    if student: name_counts[student.lower()] += 1
                    if assistant: name_counts[assistant.lower()] += 1
                    
                    if part_type == "discurso":
                        discursos_count += 1
                        
    # Regla: Sobrecarga en la sesión (más de 3 discursos)
    if discursos_count > 3:
        warnings.append(f"Hay {discursos_count} discursos/partes individuales asignadas en este programa (el máximo recomendado es 3).")
        
    # Regla: Más de 1 participación por persona
    for name, count in name_counts.items():
        if count > 1:
            warnings.append(f"El estudiante '{name.title()}' está asignado {count} veces en este mismo programa.")

    # 2. Obtener IDs de programas recientes para regla de "descanso"
    recent_query = select(MeetingProgram.id).order_by(desc(MeetingProgram.week_start))
    if prog_id:
        recent_query = recent_query.filter(MeetingProgram.id != prog_id)
    recent_query = recent_query.limit(5)
    
    res_recent = await db.execute(recent_query)
    recent_program_ids = [row for row in res_recent.scalars().all()]
    
    # Obtener nombres de historial reciente
    recent_names = set()
    if recent_program_ids:
        hist_query = select(AssignmentHistory.student_name, AssignmentHistory.assistant_name).where(AssignmentHistory.program_id.in_(recent_program_ids))
        res_hist = await db.execute(hist_query)
        for row in res_hist.fetchall():
            if row[0]: recent_names.add(row[0].strip().lower())
            if row[1]: recent_names.add(row[1].strip().lower())

    # Obtener historial de parejas (todo el historial anterior a este programa)
    pairs_query = select(AssignmentHistory.student_name, AssignmentHistory.assistant_name)
    if prog_id:
        pairs_query = pairs_query.filter(AssignmentHistory.program_id != prog_id)
    res_pairs = await db.execute(pairs_query)
    historical_pairs = set()
    for row in res_pairs.fetchall():
        if row[0] and row[1]:
            pair = tuple(sorted([row[0].strip().lower(), row[1].strip().lower()]))
            historical_pairs.add(pair)

    # 3. Obtener info de estudiantes de la DB para comprobar género
    all_names = list(name_counts.keys())
    students_dict = {}
    if all_names:
        student_query = select(Student).filter(Student.name.ilike(any_(all_names)))
        # Workaround since SQLite doesn't have any_() and postgres needs it correctly formed
        # Instead, just query all active students or use IN
        student_query = select(Student)
        res_students = await db.execute(student_query)
        for s in res_students.scalars().all():
            students_dict[s.name.strip().lower()] = s

    # 4. Validar asignaciones una por una
    for a in assignments:
        st = a["student"]
        ast = a["assistant"]
        
        st_lower = st.lower() if st else None
        ast_lower = ast.lower() if ast else None
        
        # Descanso
        if st_lower and st_lower in recent_names:
            warnings.append(f"'{st}' participó recientemente (en los últimos 5 programas).")
        if ast_lower and ast_lower in recent_names:
            warnings.append(f"'{ast}' participó recientemente (en los últimos 5 programas).")
            
        # Pareja Repetida
        if st_lower and ast_lower:
            pair = tuple(sorted([st_lower, ast_lower]))
            if pair in historical_pairs:
                warnings.append(f"'{st}' y '{ast}' ya han tenido una asignación juntos en el pasado.")
                
        # Género (sólo para demostraciones)
        if a["part_type"] == "demostracion" and st_lower and ast_lower:
            s_obj = students_dict.get(st_lower)
            a_obj = students_dict.get(ast_lower)
            
            if not s_obj:
                warnings.append(f"Estudiante '{st}' no encontrado en la base de datos.")
            elif s_obj.gender is None:
                warnings.append(f"El estudiante '{st}' no tiene género configurado en su perfil.")
                
            if not a_obj:
                warnings.append(f"Ayudante '{ast}' no encontrado en la base de datos.")
            elif a_obj.gender is None:
                warnings.append(f"El ayudante '{ast}' no tiene género configurado en su perfil.")
                
            if s_obj and a_obj and s_obj.gender is not None and a_obj.gender is not None:
                if s_obj.gender != a_obj.gender:
                    warnings.append(f"Géneros mixtos en demostración: '{st}' y '{ast}' son de diferente género.")

    return list(set(warnings)) # Eliminar duplicados
