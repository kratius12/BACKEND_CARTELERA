from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint,
    false,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class TalkOutline(Base):
    """Catálogo de bosquejos (número → título). Se arma solo con lo que se va escribiendo."""
    __tablename__ = "talk_outlines"

    number = Column(Integer, primary_key=True, autoincrement=False)
    title = Column(String(200), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class LocalSpeaker(Base):
    """Conferenciante de esta congregación (un estudiante varón) con su teléfono."""
    __tablename__ = "local_speakers"

    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    phone = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    student = relationship("Student")
    outlines = relationship("SpeakerOutline", cascade="all, delete-orphan", order_by="SpeakerOutline.number")


class SpeakerOutline(Base):
    """Bosquejo que puede presentar un conferenciante local."""
    __tablename__ = "speaker_outlines"
    __table_args__ = (
        UniqueConstraint("student_id", "number", name="uq_speaker_outlines_student_number"),
        CheckConstraint("song IS NULL OR song BETWEEN 1 AND 999", name="ck_speaker_outlines_song"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("local_speakers.student_id", ondelete="CASCADE"), nullable=False, index=True)
    number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    has_images = Column(Boolean, nullable=False, default=False, server_default=false())
    song = Column(SmallInteger, nullable=True)  # canción que usa con este bosquejo


class PublicTalk(Base):
    """Una conferencia del mes: un visitante que viene o un hermano local que va.

    El nombre, el teléfono, el bosquejo y la canción se guardan en la fila para que el historial
    no cambie si después se edita el perfil del conferenciante.
    """
    __tablename__ = "public_talks"
    __table_args__ = (
        CheckConstraint("direction IN ('incoming', 'outgoing')", name="ck_public_talks_direction"),
        CheckConstraint("song IS NULL OR song BETWEEN 1 AND 999", name="ck_public_talks_song"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    direction = Column(String(10), nullable=False, index=True)  # incoming = vienen, outgoing = van
    date = Column(Date, nullable=False, index=True)
    congregation = Column(String(120), nullable=False)  # de dónde viene / a dónde va
    student_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    speaker_name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=True)
    outline_number = Column(Integer, nullable=False)
    title = Column(String(200), nullable=False)
    has_images = Column(Boolean, nullable=False, default=False, server_default=false())
    song = Column(SmallInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
