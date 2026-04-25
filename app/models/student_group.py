from sqlalchemy import Column, String, DateTime, ForeignKey, JSON, func, Integer
from sqlalchemy.dialects.postgresql import UUID
import uuid

from ..core.database import Base

class StudentGroup(Base):
    __tablename__ = "student_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("groups.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    info_add = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
