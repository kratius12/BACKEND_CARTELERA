from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from app.core.database import Base

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True)
    status = Column(String(50), default="Activo", nullable=False)
    infoadd = Column(String(255), nullable=True)
    telefono = Column(String(50), nullable=True)
    gender = Column(Integer, nullable=True)
    aseo = Column(Boolean, default=False)
    acomodador = Column(Boolean, default=False)
    microfonos = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
