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
