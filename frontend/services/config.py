"""
TRACE-Fin Frontend Configuration Module.
Connects exclusively to the live FastAPI + SQLite backend.
"""

from __future__ import annotations

import os

# FastAPI Backend URL (no mock mode)
API_BASE_URL = os.getenv("TRACEFIN_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API_TIMEOUT_SECONDS = float(os.getenv("TRACEFIN_API_TIMEOUT", "10.0"))

# Application Metadata
APP_NAME = "TRACE-Fin"
APP_FULL_TITLE = "TRACE-Fin: Evidence-Aware Financial Transaction Verification"
APP_EXPANSION = "Transaction Risk Analysis, Correlation, and Escalation for Finance"
APP_VERSION = "v1.0.0 · FastAPI + SQLite Forensics Engine"
ENVIRONMENT_TAG = "SYNTHETIC RESEARCH PROTOTYPE · LIVE FASTAPI + SQLITE BACKEND"
DEFAULT_EVALUATION_SAMPLE_SIZE = 500
