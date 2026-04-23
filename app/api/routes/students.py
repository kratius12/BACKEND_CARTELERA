from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.api.dependencies import get_db, get_current_admin_user
from app.schemas.student import StudentCreate, StudentUpdate, StudentResponse
from app.crud import student as crud_student

router = APIRouter()

@router.get("", response_model=List[StudentResponse])
async def list_students(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    return await crud_student.get_students(db)

@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student: StudentCreate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    try:
        return await crud_student.create_student(db, student)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Error nativo: {str(e)}")

@router.put("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: int,
    student: StudentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    try:
        db_student = await crud_student.update_student(db, student_id, student)
        if not db_student:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")
        return db_student
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error nativo actualizando: {str(e)}")

@router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_admin_user)
):
    success = await crud_student.delete_student(db, student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Estudiante no encontrado")
    return None
