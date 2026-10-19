from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

# Tipos de publicador que se pueden seleccionar en el informe
PUBLISHER_TYPES = ("publicador", "auxiliar", "regular")


class PreachingReport(Base):
    """Informe mensual de predicación: una fila por persona y por mes."""

    __tablename__ = "preaching_reports"
    __table_args__ = (
        UniqueConstraint("student_id", "month", name="uq_preaching_reports_student_month"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    # Siempre el día 1 del mes informado (ej. 2026-09-01 = septiembre 2026)
    month = Column(Date, nullable=False, index=True)
    # publicador | auxiliar | regular
    publisher_type = Column(String(20), nullable=False, default="publicador", server_default="publicador")
    # Precursorado de ese mes: regular | aux_ind | aux_camp | None (publicador).
    # La campaña solo existe aquí: es del mes en que se asigna, no queda en Estudiantes.
    pioneer_status = Column(String(10), nullable=True)
    # SP (True) / NP (False) para publicadores; None = todavía sin informe
    participated = Column(Boolean, nullable=True)
    hours = Column(Integer, nullable=True)
    bible_studies = Column(Integer, nullable=True)
    sacred_service_hours = Column(Integer, nullable=True)
    observations = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    student = relationship("Student")


class GroupReportLink(Base):
    """Link secreto de cada grupo para que el encargado vea y llene los informes sin iniciar sesión."""

    __tablename__ = "group_report_links"

    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    token = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
