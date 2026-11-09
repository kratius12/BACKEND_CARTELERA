from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class SoundAssignment(Base):
    """Sonido: audio y video, micrófonos y Zoom. Una fila por semana, desde la reunión
    del sábado (date) hasta la de entre semana siguiente (midweek_date).

    El nombre se guarda junto al estudiante para que el historial siga mostrando
    quién fue aunque el estudiante se borre.
    """
    __tablename__ = "sound_assignments"
    __table_args__ = (
        CheckConstraint("EXTRACT(ISODOW FROM date) = 6", name="ck_sound_assignments_sabado"),
        CheckConstraint(
            "midweek_date > date AND midweek_date <= date + 6",
            name="ck_sound_assignments_entre_semana",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)
    midweek_date = Column(Date, nullable=False)
    audio_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    audio_name = Column(String(150), nullable=True)
    micro_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    micro_name = Column(String(150), nullable=True)
    zoom_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    zoom_name = Column(String(150), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    audio = relationship("Student", foreign_keys=[audio_id])
    micro = relationship("Student", foreign_keys=[micro_id])
    zoom = relationship("Student", foreign_keys=[zoom_id])
