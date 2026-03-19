from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from contextlib import asynccontextmanager

from app.api.api import api_router
from app.core.config import settings

# Path absolute to the built React directory
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "FRONTEND_CARTELERA", "dist")

app = FastAPI(title="Cartelera API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas de la API (Backend real)
app.include_router(api_router, prefix="/api")

# ======== SERVICIO DEL FRONTEND ESTÁTICO (REACT) ========

# Solo montamos la carpeta estática si existe (por ejemplo en producción o después de un build)
if os.path.isdir(FRONTEND_DIST):
    # Sirve los recursos estáticos como .js, .css y activos
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")
    
    # Catch-all route para React Router. Cualquier cosa no encontrada por la API de arriba, asume que es una vista de React.
    @app.get("/{full_path:path}")
    async def serve_react_app(request: Request, full_path: str):
        # Si la petición busca explícitamente contenido en /api/ y cayó aquí, es un 404 real.
        if full_path.startswith("api/"):
            return {"detail": "Not Found"}
            
        index_file = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return {"detail": "El frontend no ha sido compilado en 'FRONTEND_CARTELERA/dist' aún."}
else:
    @app.get("/")
    async def root():
        return {"message": "Cartelera API Running. (Frontend 'dist' no encontrado)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
