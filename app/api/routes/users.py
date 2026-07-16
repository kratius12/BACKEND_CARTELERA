from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy.future import select

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.crud.crud_user import get_user_by_email, create_user, get_users, update_user, delete_user
from app.api.dependencies import get_current_admin_user

router = APIRouter()

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_new_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
) -> UserResponse:
    """
    Create a new user. Only admins can create new users.
    """
    user = get_user_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(status_code=400, detail="The user with this email already exists in the system.")
    
    new_user = create_user(db, user_in=user_in)
    return new_user

@router.get("/", response_model=List[UserResponse])
def list_all_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
) -> List[UserResponse]:
    """Retrieve all users. Admin only."""
    users = get_users(db, skip=skip, limit=limit)
    return users

@router.put("/{user_id}", response_model=UserResponse)
def update_existing_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
) -> UserResponse:
    """Update a user's details or change password. Admin only."""
    query = select(User).where(User.id == user_id)
    result = db.execute(query)
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user_in.email and user_in.email != user.email:
        existing = get_user_by_email(db, email=user_in.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
            
    updated = update_user(db, db_user=user, user_in=user_in)
    return updated

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_existing_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """Delete a user. Admin Only."""
    # Prevent admin from deleting themselves
    if user_id == current_admin.id:
         raise HTTPException(status_code=400, detail="Cannot delete your own admin account.")
         
    success = delete_user(db, id=user_id)
    if not success:
         raise HTTPException(status_code=404, detail="User not found")
    return None
