import random
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func, and_
from app.models.assignments import MicrophoneAssignment, AttendantAssignment
from app.models.student import Student
from app.models.cleaning import CleaningHistory

async def get_available_students(db: AsyncSession, assignment_type: str, for_date: date):
    """
    Returns students available for a specific assignment type on a specific date,
    excluding those already assigned to cleaning in the same week.
    Sorted by the ones who haven't been assigned recently.
    """
    # 1. Get cleaning participants for that week
    cleaning_query = select(CleaningHistory).where(
        and_(
            CleaningHistory.week_start <= for_date,
            CleaningHistory.week_end >= for_date
        )
    )
    cleaning_res = await db.execute(cleaning_query)
    cleaning_record = cleaning_res.scalar_one_or_none()
    
    excluded_ids = []
    if cleaning_record:
        if cleaning_record.encargado_id: excluded_ids.append(cleaning_record.encargado_id)
        if cleaning_record.supervisor_id: excluded_ids.append(cleaning_record.supervisor_id)

    # 2. Base query for candidates
    Model = MicrophoneAssignment if assignment_type == "micro" else AttendantAssignment
    attr = "microfonos" if assignment_type == "micro" else "acomodador"
    
    # Subquery for last assignment date
    last_assignment_sub = (
        select(Model.student_id, func.max(Model.date).label("last_date"))
        .group_by(Model.student_id)
        .subquery()
    )

    query = (
        select(Student, last_assignment_sub.c.last_date)
        .outerjoin(last_assignment_sub, Student.id == last_assignment_sub.c.student_id)
        .where(
            getattr(Student, attr) == True,
            Student.status == "Activo",
            Student.id.not_in(excluded_ids) if excluded_ids else True
        )
        .order_by(last_assignment_sub.c.last_date.asc().nullsfirst(), func.random())
    )
    
    result = await db.execute(query)
    return result.all() # returns list of (Student, last_date)

async def generate_weekly_assignments(db: AsyncSession, assignment_type: str, n_weeks: int = 5, start_date: date = None):
    """
    Generates assignments for N weeks, one week at a time.
    """
    Model = MicrophoneAssignment if assignment_type == "micro" else AttendantAssignment
    
    # 1. Find last assignment date
    last_query = select(Model.date).order_by(desc(Model.date)).limit(1)
    last_res = await db.execute(last_query)
    last_date = last_res.scalar_one_or_none()
    
    current_date = start_date or date.today()
    if last_date:
        current_date = last_date + timedelta(days=7)
    else:
        # Snap to Monday of current week if no last date
        current_date = current_date - timedelta(days=current_date.weekday())
    
    generated = []
    for _ in range(n_weeks):
        # Pick 2 students for this specific date
        candidates = await get_available_students(db, assignment_type, current_date)
        
        if len(candidates) < 2:
            # Maybe we don't have enough students, but we pick what we have
            picked = candidates
        else:
            picked = candidates[:2]
            
        for student, _ in picked:
            assignment = Model(student_id=student.id, date=current_date)
            db.add(assignment)
            generated.append(assignment)
            
        current_date += timedelta(days=7)
        
    await db.commit()
    return generated

async def get_assignment_history(db: AsyncSession, assignment_type: str, limit: int = 20):
    Model = MicrophoneAssignment if assignment_type == "micro" else AttendantAssignment
    from sqlalchemy.orm import selectinload
    
    query = (
        select(Model)
        .options(selectinload(Model.student))
        .order_by(desc(Model.date), desc(Model.id))
        .limit(limit)
    )
    result = await db.execute(query)
    records = result.scalars().all()
    
    return [
        {
            "id": r.id,
            "student_name": r.student.name,
            "date": r.date,
            "created_at": r.created_at
        }
        for r in records
    ]
