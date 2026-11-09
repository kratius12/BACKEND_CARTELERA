"""Panel: Sonido (audio y video, micrófonos y Zoom)."""
from app.api.saturday_router import build_router
from app.services.sound import schedule

router = build_router(schedule, "Sound")
