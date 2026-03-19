from fastapi import APIRouter, Depends
from app.api.routes import health, public, admin, auth, users
from app.api.dependencies import get_current_admin_user

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(public.router, prefix="/programs", tags=["programs"])
api_router.include_router(
    admin.router, 
    prefix="/admin/programs", 
    tags=["admin"],
    dependencies=[Depends(get_current_admin_user)]
)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
