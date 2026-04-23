from sqlalchemy import Column, Integer, DateTime, Date
from sqlalchemy.sql import func
from app.core.database import Base

class CleaningHistory(Base):
    __tablename__ = "historial_emparejamientos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    grupo1 = Column(Integer, nullable=False)
    grupo2 = Column(Integer, nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
