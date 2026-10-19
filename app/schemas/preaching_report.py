from typing import List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field

PublisherType = Literal["publicador", "auxiliar", "regular"]
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"  # "YYYY-MM"


class PreachingReportIn(BaseModel):
    student_id: int
    publisher_type: PublisherType = "publicador"
    participated: Optional[bool] = None
    hours: Optional[int] = Field(None, ge=0, le=999)
    bible_studies: Optional[int] = Field(None, ge=0, le=99)
    sacred_service_hours: Optional[int] = Field(None, ge=0, le=999)
    observations: Optional[str] = Field(None, max_length=255)
    # Solo desde el panel del admin: precursorado de la persona en este mes. Regular,
    # indefinido o None (publicador) también se guardan en Estudiantes; "aux_camp" queda
    # solo en este mes. Si no se envía, no se toca.
    pioneer_status: Optional[Literal["regular", "aux_ind", "aux_camp"]] = None


class PreachingReportsSave(BaseModel):
    month: str = Field(..., pattern=MONTH_PATTERN)
    reports: List[PreachingReportIn]


class PreachingReportRow(BaseModel):
    student_id: int
    name: str
    publisher_type: PublisherType
    participated: Optional[bool] = None
    hours: Optional[int] = None
    bible_studies: Optional[int] = None
    sacred_service_hours: Optional[int] = None
    observations: Optional[str] = None
    # True si ya hay un informe guardado para este mes
    saved: bool = False
    # Precursorado de la persona en este mes: "regular", "aux_ind", "aux_camp" o None.
    # Con informe guardado es el de ese informe; sin informe, el fijo de Estudiantes.
    pioneer_status: Optional[Literal["regular", "aux_ind", "aux_camp"]] = None


class PreachingReportGroup(BaseModel):
    id: UUID
    name: str
    rows: List[PreachingReportRow]


class PreachingReportsMonth(BaseModel):
    month: str
    groups: List[PreachingReportGroup]


class GroupReportMonth(BaseModel):
    """Lo que ve el encargado con el link de su grupo."""
    month: str
    group: PreachingReportGroup


PioneerStatus = Literal["regular", "aux_ind", "aux_camp"]


class PioneerMonth(BaseModel):
    """Un mes del año de servicio de una persona."""
    month: str
    # Precursorado ese mes (del informe guardado o, si no hay, el fijo de Estudiantes)
    status: Optional[PioneerStatus] = None
    saved: bool = False
    hours: Optional[int] = None
    sacred_service_hours: Optional[int] = None


class PioneerPerson(BaseModel):
    student_id: int
    name: str
    group_name: str
    months: List[PioneerMonth]


class PioneerYear(BaseModel):
    """Precursores del año de servicio, mes a mes, para seguir sus metas."""
    service_year: int
    until: str
    months: List[str]
    people: List[PioneerPerson]


class GroupLinkOut(BaseModel):
    group_id: UUID
    name: str
    token: str
    members: int
