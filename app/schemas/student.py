from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class StudentBase(BaseModel):
    name: str
    status: str = "Activo"
    infoadd: Optional[str] = None
    telefono: Optional[str] = None
    gender: Optional[int] = None
    created_at: Optional[datetime] = None

class StudentCreate(StudentBase):
    pass

class StudentUpdate(StudentBase):
    name: Optional[str] = None
    status: Optional[str] = None

class StudentResponse(StudentBase):
    id: int

    class Config:
        from_attributes = True
