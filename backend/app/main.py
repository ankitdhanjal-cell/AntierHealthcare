from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .config import settings
from .routers import (accreditation, actions, admin, analytics, audits, auth, cases, channels, feedback, home, incidents, indicators, misc, public,
                      reports)

app = FastAPI(title="Antier Healthcare Suite API", version=settings.app_version)
app.add_middleware(GZipMiddleware, minimum_size=800)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for r in (auth, admin, feedback, cases, incidents, accreditation, actions, audits, indicators, reports, home, analytics, channels, misc, public):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": settings.app_version}
