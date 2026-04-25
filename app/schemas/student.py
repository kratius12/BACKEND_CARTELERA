from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

class StudentBase(BaseModel):
    name: str
    status: str = "Activo"
    infoadd: Optional[str] = None
    telefono: Optional[str] = None
    gender: Optional[int] = None
    aseo: bool = False
    acomodador: bool = False
    microfonos: bool = False
    created_at: Optional[datetime] = None

    @field_validator('aseo', 'acomodador', 'microfonos', mode='before')
    @classmethod
    def set_false_if_none(cls, v):
        return v if v is not None else False

class StudentCreate(StudentBase):
    pass

class StudentUpdate(StudentBase):
    name: Optional[str] = None
    status: Optional[str] = None

class StudentResponse(StudentBase):
    id: int
    group_info: Optional[dict] = None

    class Config:
        from_attributes = True
