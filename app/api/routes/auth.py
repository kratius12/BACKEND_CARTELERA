from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta, datetime, timezone
import secrets

from app.core.database import get_db
from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.schemas.user import Token, PasswordRecoveryRequest, PasswordReset
from app.crud.crud_user import get_user_by_email, set_password_reset_token, get_user_by_reset_token, reset_password

router = APIRouter()

@router.post("/login", response_model=Token)
async def login_access_token(
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = await get_user_by_email(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

@router.post("/recover-password")
async def recover_password(
    request: PasswordRecoveryRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Password Recovery. Generates a token (usually emailed to the user).
    For the sake of this system, we merely generate it. In production, an email service would send it.
    """
    user = await get_user_by_email(db, email=request.email)
    if not user:
        # Prevent email enumeration attacks by returning generic success
        return {"msg": "Password recovery email sent"}
    
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    await set_password_reset_token(db, user.id, token, expires_at)
    
    # Normally, this is where you'd send an email. 
    # For testing and demonstration, returning the token to the output.
    return {"msg": "Password recovery email sent", "debug_token": token}

@router.post("/reset-password")
async def reset_password_endpoint(
    request: PasswordReset, db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Reset password via a Recovery Token
    """
    user = await get_user_by_reset_token(db, token=request.token)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired recovery token")
    
    await reset_password(db, user_id=user.id, new_password=request.new_password)
    return {"msg": "Password updated successfully"}
