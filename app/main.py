from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.api.api import api_router
from app.core.config import settings

FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "FRONTEND_CARTELERA", "dist"
)

app = FastAPI(title="Cartelera API", version="1.0.0")

@app.get("/ping")
def ping():
    return {"ok": True}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_react_app(request: Request, full_path: str):
        if full_path.startswith("api/"):
            return {"detail": "Not Found"}
        index_file = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return {"detail": "Frontend dist not built yet."}
else:
    @app.get("/")
    def root():
        return {"message": "Cartelera API Running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
