"""Health endpoints.

`/healthz` — liveness. Always 200 if the process is up.
`/readyz`  — readiness. 200 only when downstream deps respond.

Cloud Run uses `/healthz` for the container HEALTHCHECK; Pub/Sub and IAP do
not call these, so neither requires OIDC.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "service": s.APP_NAME,
        "version": s.APP_VERSION,
        "environment": s.ENVIRONMENT,
    }


@router.get("/readyz")
async def readyz() -> dict:
    # TODO(week 1): probe DB + Drive + Vertex AI. For now, ok if up.
    return {"status": "ready"}
