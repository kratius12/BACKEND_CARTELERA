from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, desc, func
from datetime import date
from app.models.program import MeetingProgram, MeetingProgramStaging, AssignmentHistory
from app.schemas.program import ProgramCreate, ProgramUpdate

async def _sync_assignment_history(db: AsyncSession, program_id: int, week_start: date, payload: dict):
    # Borrar historial viejo
    await db.execute(delete(AssignmentHistory).where(AssignmentHistory.program_id == program_id))
    
    parts = payload.get("parts", [])
    history_entries = []
    
    for part in parts:
        if part.get("type") == "section":
            for item in part.get("items", []):
                assigned = item.get("assigned", [])
                
                title = (item.get("text") or "").lower()
                is_demostracion = "empiece" in title or "haga" in title or "explique" in title
                part_type = "demostracion" if is_demostracion else "discurso"

                student = assigned[0] if len(assigned) > 0 else None
                assistant = assigned[1] if len(assigned) > 1 else None

                if student and "❌" in student: student = None
                if assistant and "❌" in assistant: assistant = None
                
                if not student:
                    continue
                    
                entry = AssignmentHistory(
                    program_id=program_id,
                    week_start=week_start,
                    student_name=student.strip(),
                    assistant_name=assistant.strip() if assistant else None,
                    part_type=part_type
                )
                history_entries.append(entry)
                
    if history_entries:
        db.add_all(history_entries)

async def get_current_program_id(db: AsyncSession, today: date) -> int:
    stmt = (
        select(MeetingProgram.id)
        .where(MeetingProgram.week_start <= today, MeetingProgram.week_end >= today)
        .order_by(desc(MeetingProgram.week_start))
        .limit(1)
    )
    result = await db.execute(stmt)
    prog_id = result.scalar_one_or_none()
    return prog_id if prog_id else 1

async def get_programs(db: AsyncSession):
    stmt = (
        select(
            MeetingProgram.id,
            MeetingProgram.week_start,
            MeetingProgram.week_end,
            MeetingProgram.payload
        ).order_by(desc(MeetingProgram.week_start))
    )
    result = await db.execute(stmt)
    
    rows = []
    for row in result.all():
        payload = row.payload or {}
        rows.append({
            "id": row.id,
            "week_start": row.week_start,
            "week_end": row.week_end,
            "title": payload.get("title")
        })
    return rows

async def get_program(db: AsyncSession, prog_id: int):
    stmt = select(MeetingProgram).where(MeetingProgram.id == prog_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

# --- STAGING CRUD ---

async def get_staging_programs(db: AsyncSession):
    stmt = (
        select(
            MeetingProgramStaging.id,
            MeetingProgramStaging.week_start,
            MeetingProgramStaging.week_end,
            MeetingProgramStaging.payload
        ).order_by(desc(MeetingProgramStaging.week_start))
    )
    result = await db.execute(stmt)
    
    rows = []
    for row in result.all():
        payload = row.payload or {}
        rows.append({
            "id": row.id,
            "week_start": row.week_start,
            "week_end": row.week_end,
            "title": payload.get("title")
        })
    return rows

async def get_staging_program(db: AsyncSession, prog_id: int):
    stmt = select(MeetingProgramStaging).where(MeetingProgramStaging.id == prog_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create_staging_program(db: AsyncSession, program: ProgramCreate):
    max_id_stmt = select(func.coalesce(func.max(MeetingProgramStaging.id), 0) + 1)
    result = await db.execute(max_id_stmt)
    next_id = result.scalar_one()

    db_obj = MeetingProgramStaging(
        id=next_id,
        week_start=program.week_start,
        week_end=program.week_end,
        payload=program.payload
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def update_staging_program(db: AsyncSession, prog_id: int, program: ProgramUpdate):
    stmt = (
        update(MeetingProgramStaging)
        .where(MeetingProgramStaging.id == prog_id)
        .values(
            week_start=program.week_start,
            week_end=program.week_end,
            payload=program.payload
        )
        .returning(MeetingProgramStaging.id)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.scalar_one_or_none()

async def delete_staging_program(db: AsyncSession, prog_id: int):
    stmt = delete(MeetingProgramStaging).where(MeetingProgramStaging.id == prog_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0

async def update_program(db: AsyncSession, prog_id: int, program: ProgramUpdate):
    stmt = (
        update(MeetingProgram)
        .where(MeetingProgram.id == prog_id)
        .values(
            week_start=program.week_start,
            week_end=program.week_end,
            payload=program.payload
        )
        .returning(MeetingProgram.id)
    )
    result = await db.execute(stmt)
    
    # Update assignment history
    await _sync_assignment_history(db, prog_id, program.week_start, program.payload)
    
    await db.commit()
    return result.scalar_one_or_none()

async def delete_program(db: AsyncSession, prog_id: int):
    stmt = delete(MeetingProgram).where(MeetingProgram.id == prog_id)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount > 0

async def publish_program(db: AsyncSession, prog_id: int):
    # 1. Get from staging
    staging_prog = await get_staging_program(db, prog_id)
    if not staging_prog:
        return None

    # 2. Get next ID for main table
    max_id_stmt = select(func.coalesce(func.max(MeetingProgram.id), 0) + 1)
    result = await db.execute(max_id_stmt)
    next_id = result.scalar_one()

    # 3. Create in main table
    db_prog = MeetingProgram(
        id=next_id,
        week_start=staging_prog.week_start,
        week_end=staging_prog.week_end,
        payload=staging_prog.payload
    )
    db.add(db_prog)

    # 4. Sync history
    await _sync_assignment_history(db, next_id, staging_prog.week_start, staging_prog.payload)

    # 5. Delete from staging
    stmt_del = delete(MeetingProgramStaging).where(MeetingProgramStaging.id == prog_id)
    await db.execute(stmt_del)

    await db.commit()
    await db.refresh(db_prog)
    return db_prog
