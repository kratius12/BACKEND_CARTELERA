from sqlalchemy import Column, Integer, String, DateTime, Boolean, CheckConstraint, false
from datetime import datetime
from app.core.database import Base

class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        # Una persona solo puede tener un tipo de precursorado a la vez
        CheckConstraint(
            "(es_precursor_aux_camp::int + es_precursor_aux_ind::int + es_precursor_reg::int) <= 1",
            name="ck_students_un_solo_precursorado",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True)
    status = Column(String(50), default="Activo", nullable=False)
    infoadd = Column(String(255), nullable=True)
    telefono = Column(String(50), nullable=True)
    gender = Column(Integer, nullable=True)
    aseo = Column(Boolean, default=False)
    acomodador = Column(Boolean, default=False)
    microfonos = Column(Boolean, default=False)
    es_anciano = Column(Boolean, default=False, nullable=False)
    es_siervo = Column(Boolean, default=False, nullable=False)
    # Precursorado (como mucho uno en True)
    es_precursor_aux_camp = Column(Boolean, default=False, server_default=false(), nullable=False)  # auxiliar en campaña
    es_precursor_aux_ind = Column(Boolean, default=False, server_default=false(), nullable=False)   # auxiliar indefinido
    es_precursor_reg = Column(Boolean, default=False, server_default=false(), nullable=False)       # regular
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
