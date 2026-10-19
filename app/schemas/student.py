from pydantic import BaseModel, field_validator, model_validator
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
    es_anciano: bool = False
    es_siervo: bool = False
    # Precursorado: como mucho uno en True
    es_precursor_aux_camp: bool = False
    es_precursor_aux_ind: bool = False
    es_precursor_reg: bool = False
    created_at: Optional[datetime] = None

    @field_validator(
        'aseo', 'acomodador', 'microfonos', 'es_anciano', 'es_siervo',
        'es_precursor_aux_camp', 'es_precursor_aux_ind', 'es_precursor_reg',
        mode='before',
    )
    @classmethod
    def set_false_if_none(cls, v):
        return v if v is not None else False

    @model_validator(mode='after')
    def un_solo_precursorado(self):
        marcados = [self.es_precursor_aux_camp, self.es_precursor_aux_ind, self.es_precursor_reg]
        if sum(bool(m) for m in marcados) > 1:
            raise ValueError("Solo se puede marcar un tipo de precursorado (auxiliar en campaña, auxiliar indefinido o regular).")
        return self

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
