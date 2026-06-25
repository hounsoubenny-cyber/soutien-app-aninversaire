#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main FastAPI — App de planning/objectifs/focus.
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from backend.utils.limiter import limiter
from backend.core.router import router
from backend.core.ai_router import ai_router
from backend.api.api_config import IP, PORT, ALLOWED_ORIGINS
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
app = FastAPI(title="Soutien App API", version="1.0.0")

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(router)
app.include_router(ai_router)

FRONTEND_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    "..",
    "frontend",
    "build"
))
INDEX_FILE = os.path.join(FRONTEND_PATH, "index.html")
app.mount("/static/build", StaticFiles(directory=FRONTEND_PATH), "/frontend_build")

@app.get("/")
async def root():
    if os.path.exists(INDEX_FILE):
        return FileResponse(INDEX_FILE)
    return {"status": "ok", "app": "Soutien App API"}

@app.get("/{full_path:path}")
async def catch_all(full_path: str):
    """
    Capture toutes les routes pour React Router (SPA).

    Args:
        full_path (str): Chemin demandé

    Returns:
        FileResponse or HTTPException: Fichier React ou erreur 404
    """
    excluded_prefixes = ["api/", "docs", "redoc", "openapi.json"]

    print(full_path)
    if any(full_path.startswith(prefix) for prefix in excluded_prefixes):
        raise HTTPException(404, detail="Route non trouvée")

    if full_path.startswith("static/"):
        return FileResponse(os.path.join(FRONTEND_PATH, full_path))

    if os.path.exists(INDEX_FILE):
        return FileResponse(INDEX_FILE)

    raise HTTPException(status_code=404, detail="Route non trouvée")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=IP, port=PORT, reload=True)
