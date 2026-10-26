# TRACE-Fin API Guide

This document explains every HTTP endpoint in the TRACE-Fin backend so you can understand and present how the Streamlit UI communicates with FastAPI.

Interactive OpenAPI/Swagger documentation is also automatically available at `http://127.0.0.1:8000/docs` whenever the FastAPI server is running.

---

## HTTP Client Choice: Why `httpx`?
We chose **HTTPX** (`httpx`) for frontend-to-backend HTTP requests because:
1. FastAPI's built-in `TestClient` uses `httpx` under the hood, meaning one library covers both our test suite and our Streamlit API client.
2. It provides a clean, `requests`-compatible API with strict default timeouts and connection pooling.

---

## Endpoints

### 1. Health Check — `GET /health`
- **Method & Path:** `GET /health`
- **What it does:** Confirms that the FastAPI backend server is online and responding to requests.
- **Parameters / Request Body:** None.
- **Service Called:** Handled directly by [`get_health`](app/api/routes_health.py) (no database or domain service needed).
- **Reads/Writes Data:** Neither (stateless check).
- **Plain-Language Explanation:** Before the Streamlit UI tries to load transactions or calculate risk scores, we need a simple way to verify the API server is awake. Calling `GET /health` asks the server "Are you running?" and receives a tiny JSON receipt confirming that `TRACE-Fin` is `"ok"`.

#### Example Request
```bash
curl -X GET http://127.0.0.1:8000/health
```

#### Example Success Response (`200 OK`)
```json
{
  "status": "ok",
  "service": "TRACE-Fin"
}
```
- `status`: Always `"ok"` when the backend process is healthy.
- `service`: Identifies the application responding (`"TRACE-Fin"`).

#### Important Error Responses
- Connection refused / timeout if the `uvicorn` server is not running.
