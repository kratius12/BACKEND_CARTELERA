"""Panel: Conferencias (conferenciantes que vienen y que van)."""
from datetime import date as Date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.services import talks as svc

router = APIRouter()


class TalkIn(BaseModel):
    direction: Literal["incoming", "outgoing"]
    date: Date
    congregation: str
    # Vienen
    speaker_name: Optional[str] = None
    outline_number: Optional[int] = None
    title: Optional[str] = None
    has_images: bool = False
    song: Optional[int] = None
    # Van
    student_id: Optional[int] = None
    outline_id: Optional[int] = None
    # Ambos
    phone: Optional[str] = None


class TalkUpdate(BaseModel):
    direction: Optional[Literal["incoming", "outgoing"]] = None
    date: Optional[Date] = None
    congregation: Optional[str] = None
    speaker_name: Optional[str] = None
    outline_number: Optional[int] = None
    title: Optional[str] = None
    has_images: Optional[bool] = None
    song: Optional[int] = None
    student_id: Optional[int] = None
    outline_id: Optional[int] = None
    phone: Optional[str] = None


class SpeakerIn(BaseModel):
    student_id: int
    phone: Optional[str] = None


class SpeakerUpdate(BaseModel):
    phone: Optional[str] = None


class OutlineIn(BaseModel):
    number: int
    title: str
    has_images: bool = False
    song: Optional[int] = None


def _fail(error: svc.TalkError):
    raise HTTPException(status_code=error.status_code, detail={"code": error.code, "message": error.message})


def _run(fn, *args):
    try:
        return fn(*args)
    except svc.TalkError as error:
        _fail(error)


@router.get("")
def list_talks(
    month: str = Query(..., description="Mes (AAAA-MM)"),
    direction: Optional[Literal["incoming", "outgoing"]] = None,
    db: Session = Depends(get_db),
):
    return [svc.serialize_talk(t) for t in _run(svc.list_talks, db, month, direction)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_talk(payload: TalkIn, db: Session = Depends(get_db)):
    return _run(svc.create_talk, db, payload.model_dump())


@router.put("/{talk_id}")
def update_talk(talk_id: int, payload: TalkUpdate, db: Session = Depends(get_db)):
    return _run(svc.update_talk, db, talk_id, payload.model_dump(exclude_unset=True))


@router.delete("/{talk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_talk(talk_id: int, db: Session = Depends(get_db)):
    _run(svc.delete_talk, db, talk_id)
    return None


@router.get("/speakers")
def list_speakers(db: Session = Depends(get_db)):
    return svc.list_speakers(db)


@router.get("/speakers/eligible")
def eligible_students(db: Session = Depends(get_db)):
    return svc.eligible_students(db)


@router.post("/speakers", status_code=status.HTTP_201_CREATED)
def add_speaker(payload: SpeakerIn, db: Session = Depends(get_db)):
    return _run(svc.add_speaker, db, payload.student_id, payload.phone)


@router.put("/speakers/{student_id}")
def update_speaker(student_id: int, payload: SpeakerUpdate, db: Session = Depends(get_db)):
    return _run(svc.update_speaker, db, student_id, payload.phone)


@router.delete("/speakers/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_speaker(student_id: int, db: Session = Depends(get_db)):
    _run(svc.remove_speaker, db, student_id)
    return None


@router.post("/speakers/{student_id}/outlines", status_code=status.HTTP_201_CREATED)
def add_outline(student_id: int, payload: OutlineIn, db: Session = Depends(get_db)):
    return _run(svc.add_outline, db, student_id, payload.number, payload.title, payload.has_images, payload.song)


@router.put("/speakers/{student_id}/outlines/{outline_id}")
def update_outline(student_id: int, outline_id: int, payload: OutlineIn, db: Session = Depends(get_db)):
    return _run(
        svc.update_outline, db, student_id, outline_id, payload.number, payload.title, payload.has_images, payload.song,
    )


@router.delete("/speakers/{student_id}/outlines/{outline_id}")
def delete_outline(student_id: int, outline_id: int, db: Session = Depends(get_db)):
    return _run(svc.delete_outline, db, student_id, outline_id)


@router.get("/outlines")
def outline_catalog(db: Session = Depends(get_db)):
    return svc.outline_catalog(db)


@router.get("/visitors")
def visitors(db: Session = Depends(get_db)):
    return svc.visitors(db)
