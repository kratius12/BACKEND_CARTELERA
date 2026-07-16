from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate

def get_students(db: Session):
    result = db.execute(select(Student).order_by(Student.name))
    return result.scalars().all()

def get_student(db: Session, student_id: int):
    result = db.execute(select(Student).filter(Student.id == student_id))
    return result.scalars().first()

from datetime import datetime

def create_student(db: Session, student: StudentCreate):
    student_data = student.dict(exclude_unset=True)
    if not student_data.get("created_at"):
        student_data["created_at"] = datetime.now()
    
    # Defaults based on gender
    if student_data.get("gender") == 0:  # Mujeres
        student_data["aseo"] = student_data.get("aseo", False)
        student_data["acomodador"] = student_data.get("acomodador", False)
        student_data["microfonos"] = student_data.get("microfonos", False)
    elif student_data.get("gender") == 1:  # Hombres
        if student_data.get("status") == "Activo":
            # Set to True if not explicitly provided
            if "aseo" not in student_data: student_data["aseo"] = True
            if "acomodador" not in student_data: student_data["acomodador"] = True
            if "microfonos" not in student_data: student_data["microfonos"] = True
        
    db_student = Student(**student_data)
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student

def update_student(db: Session, student_id: int, student: StudentUpdate):
    db_student = get_student(db, student_id)
    if not db_student:
        return None
    
    update_data = student.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_student, key, value)
        
    db.commit()
    db.refresh(db_student)
    return db_student

def delete_student(db: Session, student_id: int):
    db_student = get_student(db, student_id)
    if not db_student:
        return False
    db.delete(db_student)
    db.commit()
    return True
