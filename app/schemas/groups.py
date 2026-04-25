from typing import List, Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class GroupBase(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "Grupo A"})

class GroupCreate(GroupBase):
    pass

class GroupRead(GroupBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
    students: List["StudentResponse"] = []

class StudentGroupBase(BaseModel):
    info_add: Optional[dict] = None

class StudentGroupCreate(StudentGroupBase):
    student_id: int

class StudentGroupUpdate(StudentGroupBase):
    pass

class StudentGroupRead(StudentGroupBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    student_id: int
    created_at: datetime
    updated_at: datetime

# Forward reference for StudentResponse
from app.schemas.student import StudentResponse
GroupRead.model_rebuild()
