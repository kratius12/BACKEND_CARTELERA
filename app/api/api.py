from fastapi import APIRouter, Depends
from app.api.routes import health, public, admin, auth, users, students, cleaning, groups, assignments, schedule
from app.api.routes import preaching_reports, group_reports
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
api_router.include_router(
    students.router,
    prefix="/admin/students",
    tags=["students"],
    dependencies=[Depends(get_current_admin_user)]
)
api_router.include_router(
    cleaning.router,
    prefix="/admin/cleaning",
    tags=["cleaning"],
    dependencies=[Depends(get_current_admin_user)]
)
api_router.include_router(
    assignments.router,
    prefix="/admin/assignments",
    tags=["assignments"],
    dependencies=[Depends(get_current_admin_user)]
)
api_router.include_router(
    schedule.router,
    prefix="/admin/schedule",
    tags=["schedule"],
    dependencies=[Depends(get_current_admin_user)]
)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])
api_router.include_router(
    preaching_reports.router,
    prefix="/admin/preaching-reports",
    tags=["preaching-reports"],
    dependencies=[Depends(get_current_admin_user)]
)
# Link secreto por grupo: sin login, solo ese grupo
api_router.include_router(group_reports.router, prefix="/group-reports", tags=["group-reports"])
