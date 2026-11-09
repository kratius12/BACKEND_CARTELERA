"""Panel: Fin de semana (presidente y lector del estudio de La Atalaya)."""
from app.api.saturday_router import build_router
from app.services.weekend import schedule

router = build_router(schedule, "Weekend")
