from sqlalchemy import Column, Integer, Date, JSON, DateTime, func
from app.core.database import Base

class MeetingProgram(Base):
    __tablename__ = "meeting_programs"

    id = Column(Integer, primary_key=True, index=True)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=func.now())

class MeetingProgramStaging(Base):
    __tablename__ = "meeting_programs_staging"

    id = Column(Integer, primary_key=True, index=True)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    payload = Column(JSON, nullable=False)

from sqlalchemy import ForeignKey, String

class AssignmentHistory(Base):
    __tablename__ = "assignment_history"

    id = Column(Integer, primary_key=True, index=True)
    program_id = Column(Integer, ForeignKey("meeting_programs.id", ondelete="CASCADE"), nullable=False)
    week_start = Column(Date, nullable=False)
    student_name = Column(String(150), nullable=False)
    assistant_name = Column(String(150), nullable=True)
    part_type = Column(String(50), nullable=False) # e.g. "demostracion", "discurso", "lectura"
