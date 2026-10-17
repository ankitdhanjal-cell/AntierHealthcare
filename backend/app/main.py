from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import admin, auth, cases, feedback, misc, public

app = FastAPI(title="Antier Healthcare Suite API", version=settings.app_version)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for r in (auth, admin, feedback, cases, misc, public):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": settings.app_version}
