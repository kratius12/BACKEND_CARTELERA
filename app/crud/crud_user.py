from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.future import select
from sqlalchemy import update, delete
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash
from datetime import datetime, timezone

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    query = select(User).where(User.email == email)
    result = db.execute(query)
    return result.scalars().first()

def create_user(db: Session, user_in: UserCreate) -> User:
    hashed_password = get_password_hash(user_in.password)
    db_user = User(
        email=user_in.email,
        hashed_password=hashed_password,
        role=user_in.role or "admin"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def set_password_reset_token(db: Session, user_id: int, token: str, expires_at: datetime) -> None:
    query = (
        update(User)
        .where(User.id == user_id)
        .values(reset_token=token, reset_token_expires=expires_at)
    )
    db.execute(query)
    db.commit()

def get_user_by_reset_token(db: Session, token: str) -> Optional[User]:
    # Ensure token is not expired
    now = datetime.now(timezone.utc).replace(tzinfo=None) # Keep naïve or aware depending on DB
    
    query = select(User).where(
        User.reset_token == token,
        User.reset_token_expires > now
    )
    result = db.execute(query)
    return result.scalars().first()

def reset_password(db: Session, user_id: int, new_password: str) -> None:
    hashed_password = get_password_hash(new_password)
    query = (
        update(User)
        .where(User.id == user_id)
        .values(
            hashed_password=hashed_password,
            reset_token=None,
            reset_token_expires=None
        )
    )
    db.execute(query)
    db.commit()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    query = select(User).offset(skip).limit(limit)
    result = db.execute(query)
    return result.scalars().all()

def update_user(db: Session, db_user: User, user_in: UserUpdate) -> User:
    # Use model_dump to exclude unset fields from update
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"]:
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password
    
    for field, value in update_data.items():
        setattr(db_user, field, value)
        
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, id: int) -> bool:
    query = select(User).where(User.id == id)
    result = db.execute(query)
    db_user = result.scalars().first()
    if not db_user:
        return False
    db.delete(db_user)
    db.commit()
    return True
