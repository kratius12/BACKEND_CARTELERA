from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Body
import os
import shutil
import tempfile
from sqlalchemy.orm import Session
from typing import List, Any

from app.api.dependencies import get_db
from app.schemas.program import ProgramCreate, ProgramUpdate, ProgramListResponse, ProgramResponse
from app.crud import program as crud_program
from app.services.pdf_parser import parse_mwb_pdf
from app.services.mwb_scraper import parse_mwb_from_url

router = APIRouter()

@router.post("/generate-proposal")
def generate_proposal_endpoint(data: dict = Body(...), db: Session = Depends(get_db)):
    items = data.get("items", [])
    from app.services.assigner import generate_proposal
    new_items = generate_proposal(db, items)
    return {"items": new_items}

@router.post("/validate")
def validate_program_endpoint(data: dict = Body(...), db: Session = Depends(get_db)):
    payload = data.get("payload", {})
    prog_id = data.get("prog_id")
    from app.services.validator import validate_program_payload
    warnings = validate_program_payload(db, payload, prog_id)
    return {"warnings": warnings}

@router.get("/staging", response_model=List[ProgramListResponse])
def list_staging_programs(db: Session = Depends(get_db)):
    programs = crud_program.get_staging_programs(db)
    return programs

@router.get("/staging/{prog_id}", response_model=ProgramResponse)
def get_staging_program_by_id(prog_id: int, db: Session = Depends(get_db)):
    program = crud_program.get_staging_program(db, prog_id)
    if not program:
        raise HTTPException(status_code=404, detail="No encontrado en staging")
    return program

@router.post("", status_code=status.HTTP_201_CREATED)
def create_program_in_staging(program: ProgramCreate, db: Session = Depends(get_db)):
    db_prog = crud_program.create_staging_program(db, program)
    return {"id": db_prog.id, "message": "Guardado en staging"}

@router.post("/upload-pdf", status_code=status.HTTP_201_CREATED)
def upload_pdf_program(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")
    
    # Save temporarily
    fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        # Parse the pdf
        parsed_programs = parse_mwb_pdf(temp_path, file.filename)
        if not parsed_programs:
            raise HTTPException(
                status_code=400,
                detail="El PDF se procesó correctamente, pero no se pudo extraer ningún programa. Revisa el formato de la guía."
            )

        # Save each parsed program to staging
        created_ids = []
        for program_data in parsed_programs:
            # We need to construct a proper ProgramCreate schema
            # ProgramCreate expects week_start, week_end, and payload
            # The payload will contain everything except week_start/week_end
            
            p_week_start = program_data.pop("week_start")
            p_week_end = program_data.pop("week_end")
            
            p_create = ProgramCreate(
                week_start=p_week_start,
                week_end=p_week_end,
                payload=program_data
            )
            
            db_prog = crud_program.create_staging_program(db, p_create)
            created_ids.append(db_prog.id)
            
        return {"message": f"Se extrajeron {len(created_ids)} programas", "ids": created_ids}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        try:
            os.close(fd)
        except Exception:
            pass
    if not updated_id:
        raise HTTPException(status_code=404, detail="Programa no encontrado en staging")
    return {"id": updated_id, "message": "Staging actualizado"}


@router.post("/import-url", status_code=status.HTTP_201_CREATED)
def import_mwb_from_url(data: dict = Body(...), db: Session = Depends(get_db)):
    url = data.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="Se requiere el campo 'url'")

    try:
        parsed_programs = parse_mwb_from_url(url)
        if not parsed_programs:
            raise HTTPException(status_code=400, detail="No se extrajeron programas desde la URL proporcionada")

        created_ids = []
        for program_data in parsed_programs:
            p_week_start = program_data.pop("week_start")
            p_week_end = program_data.pop("week_end")

            p_create = ProgramCreate(
                week_start=p_week_start,
                week_end=p_week_end,
                payload=program_data
            )

            db_prog = crud_program.create_staging_program(db, p_create)
            created_ids.append(db_prog.id)

        return {"message": f"Se extrajeron {len(created_ids)} programas desde la URL", "ids": created_ids}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/staging/{prog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_staging_prog(prog_id: int, db: Session = Depends(get_db)):
    success = crud_program.delete_staging_program(db, prog_id)
    if not success:
        raise HTTPException(status_code=404, detail="Programa no encontrado en staging")
    return None

@router.post("/{prog_id}/publish")
def publish_program(prog_id: int, db: Session = Depends(get_db)):
    db_prog = crud_program.publish_program(db, prog_id)
    if not db_prog:
        raise HTTPException(status_code=404, detail="Programa no encontrado en staging")
    return {"id": db_prog.id, "message": "Publicado exitosamente"}

@router.put("/{prog_id}")
def update_published_program(prog_id: int, program: ProgramUpdate, db: Session = Depends(get_db)):
    updated_id = crud_program.update_program(db, prog_id, program)
    if not updated_id:
        raise HTTPException(status_code=404, detail="Programa publicado no encontrado")
    return {"id": updated_id, "message": "Programa actualizado"}

@router.delete("/{prog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_published_prog(prog_id: int, db: Session = Depends(get_db)):
    success = crud_program.delete_program(db, prog_id)
    if not success:
        raise HTTPException(status_code=404, detail="Programa publicado no encontrado")
    return None
