from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class WeekendAssignment(Base):
    """Reunión del fin de semana: presidente y lector del estudio de La Atalaya.

    Una fila por sábado. El nombre se guarda junto al estudiante para que el
    historial siga mostrando quién fue aunque el estudiante se borre, y para las
    semanas importadas cuyo nombre no coincidió con ningún estudiante.
    """
    __tablename__ = "weekend_assignments"
    __table_args__ = (
        CheckConstraint("EXTRACT(ISODOW FROM date) = 6", name="ck_weekend_assignments_sabado"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)
    president_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    reader_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    president_name = Column(String(150), nullable=True)
    reader_name = Column(String(150), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    president = relationship("Student", foreign_keys=[president_id])
    reader = relationship("Student", foreign_keys=[reader_id])
