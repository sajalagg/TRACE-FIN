from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_auth import router as auth_router
from app.api.routes_evaluation import router as evaluation_router
from app.api.routes_health import router as health_router
from app.api.routes_incidents import router as incidents_router
from app.api.routes_preferences import router as preferences_router
from app.api.routes_transactions import router as transactions_router
from app.api.routes_verification import router as verification_router
from app.core.database import init_db

app = FastAPI(
    title="TRACE-Fin API",
    description=(
        "Educational prototype for Evidence-Aware Financial Transaction "
        "Verification and Incident Response (synthetic data only)."
    ),
    version="1.0.0",
)

# Enable CORS so any frontend (React, Vite, Next.js, or Streamlit) can call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(preferences_router)
app.include_router(verification_router)
app.include_router(incidents_router)
app.include_router(evaluation_router)


@app.on_event("startup")
def _apply_database_migrations() -> None:
    """Bring existing databases up to the current schema (idempotent) before serving requests."""
    init_db()
