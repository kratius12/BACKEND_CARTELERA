from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
import os
import shutil
import tempfile
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.dependencies import get_db
from app.schemas.program import ProgramCreate, ProgramUpdate, ProgramListResponse, ProgramResponse
from app.crud import program as crud_program
from app.services.pdf_parser import parse_mwb_pdf

router = APIRouter()

@router.get("/staging", response_model=List[ProgramListResponse])
async def list_staging_programs(db: AsyncSession = Depends(get_db)):
    programs = await crud_program.get_staging_programs(db)
    return programs

@router.get("/staging/{prog_id}", response_model=ProgramResponse)
async def get_staging_program_by_id(prog_id: int, db: AsyncSession = Depends(get_db)):
    program = await crud_program.get_staging_program(db, prog_id)
    if not program:
        raise HTTPException(status_code=404, detail="No encontrado en staging")
    return program

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_program_in_staging(program: ProgramCreate, db: AsyncSession = Depends(get_db)):
    db_prog = await crud_program.create_staging_program(db, program)
    return {"id": db_prog.id, "message": "Guardado en staging"}

@router.post("/upload-pdf", status_code=status.HTTP_201_CREATED)
async def upload_pdf_program(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")
    
    # Save temporarily
    fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
            
        # Parse the pdf
        parsed_programs = parse_mwb_pdf(temp_path, file.filename)
        
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
            
            db_prog = await crud_program.create_staging_program(db, p_create)
            created_ids.append(db_prog.id)
            
        return {"message": f"Se extrajeron {len(created_ids)} programas", "ids": created_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        os.close(fd)
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.put("/staging/{prog_id}")
async def update_program_in_staging(prog_id: int, program: ProgramUpdate, db: AsyncSession = Depends(get_db)):
    updated_id = await crud_program.update_staging_program(db, prog_id, program)
    if not updated_id:
        raise HTTPException(status_code=404, detail="Programa no encontrado en staging")
    return {"id": updated_id, "message": "Staging actualizado"}

@router.delete("/staging/{prog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staging_prog(prog_id: int, db: AsyncSession = Depends(get_db)):
    success = await crud_program.delete_staging_program(db, prog_id)
    if not success:
        raise HTTPException(status_code=404, detail="Programa no encontrado en staging")
    return None

@router.post("/{prog_id}/publish")
async def publish_program(prog_id: int, db: AsyncSession = Depends(get_db)):
    db_prog = await crud_program.publish_program(db, prog_id)
    if not db_prog:
        raise HTTPException(status_code=404, detail="Programa no encontrado en staging")
    return {"id": db_prog.id, "message": "Publicado exitosamente"}

@router.put("/{prog_id}")
async def update_published_program(prog_id: int, program: ProgramUpdate, db: AsyncSession = Depends(get_db)):
    updated_id = await crud_program.update_program(db, prog_id, program)
    if not updated_id:
        raise HTTPException(status_code=404, detail="Programa publicado no encontrado")
    return {"id": updated_id, "message": "Programa actualizado"}

@router.delete("/{prog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_published_prog(prog_id: int, db: AsyncSession = Depends(get_db)):
    success = await crud_program.delete_program(db, prog_id)
    if not success:
        raise HTTPException(status_code=404, detail="Programa publicado no encontrado")
    return None
