from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_admin_user, get_db
from app.schemas.groups import GroupCreate, StudentGroupCreate, StudentGroupRead, GroupRead, StudentGroupUpdate
from app.services.group_service import (
    get_groups,
    create_group,
    add_student_to_group,
    remove_student_from_group,
)

router = APIRouter()

@router.get("/", response_model=list)
async def list_groups(db: AsyncSession = Depends(get_db), _: dict = Depends(get_current_admin_user)):
    """Return all groups with their assigned students."""
    return await get_groups(db)

@router.post("/", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
async def create_new_group(payload: GroupCreate, db: AsyncSession = Depends(get_db), _: dict = Depends(get_current_admin_user)):
    """Create a new group."""
    return await create_group(db, payload)

@router.post("/{group_id}/students", response_model=StudentGroupRead, status_code=status.HTTP_201_CREATED)
async def assign_student(
    group_id: UUID,
    payload: StudentGroupCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin_user),
):
    """Assign a student to a group."""
    return await add_student_to_group(db, group_id, payload)

@router.delete("/{group_id}/students/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_student(
    group_id: UUID,
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin_user),
):
    """Remove a student from a group."""
    await remove_student_from_group(db, group_id, student_id)
    return None

@router.patch("/{group_id}/students/{student_id}", response_model=StudentGroupRead)
async def update_assignment(
    group_id: UUID,
    student_id: int,
    payload: StudentGroupUpdate, 
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_admin_user),
):
    """Update student role/info in a group."""
    from app.services.group_service import update_student_role
    return await update_student_role(db, group_id, student_id, payload.info_add)
