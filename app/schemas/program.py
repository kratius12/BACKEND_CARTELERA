from pydantic import BaseModel, Field
from datetime import date
from typing import Any, Dict, Optional

class ProgramBase(BaseModel):
    week_start: date
    week_end: date
    payload: Dict[str, Any]

class ProgramCreate(ProgramBase):
    pass

class ProgramUpdate(ProgramBase):
    pass

class ProgramResponse(ProgramBase):
    id: int
    title: Optional[str] = None
    
    class Config:
        from_attributes = True

# Used for list responses where payload isn't always fully sent, 
# although in Express we returned: id, week_start, week_end, payload->>'title' AS title
class ProgramListResponse(BaseModel):
    id: int
    week_start: date
    week_end: date
    title: Optional[str] = None

    class Config:
        from_attributes = True
