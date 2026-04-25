from sqlalchemy import Column, Integer, DateTime, Date, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class CleaningHistory(Base):
    __tablename__ = "historial_emparejamientos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    grupo1 = Column(Integer, nullable=False)
    grupo2 = Column(Integer, nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    encargado_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    supervisor_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    encargado = relationship("Student", foreign_keys=[encargado_id])
    supervisor = relationship("Student", foreign_keys=[supervisor_id])
