from __future__ import annotations

from fastapi import FastAPI

from app.api.routes_health import router as health_router
from app.api.routes_transactions import router as transactions_router

app = FastAPI(
    title="TRACE-Fin API",
    description=(
        "Educational prototype for Evidence-Aware Financial Transaction "
        "Verification and Incident Response (synthetic data only)."
    ),
    version="0.3.0",
)

app.include_router(health_router)
app.include_router(transactions_router)
