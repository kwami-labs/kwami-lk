"""Bootstrap telephony sessions from backend-provided kwami config."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .utils.logging import get_logger

logger = get_logger("runtime_bootstrap")

API_BASE_URL = os.environ.get("KWAMI_API_URL", "http://localhost:8080")
KWAMI_API_KEY = os.environ.get("KWAMI_API_KEY", "")


def _api_timeout_seconds() -> float:
    raw = os.environ.get("KWAMI_API_TIMEOUT", "30.0")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 30.0


def _parse_json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def resolve_kwami_id(ctx) -> str | None:
    """Resolve the kwami id from job metadata or SIP participant metadata/attributes."""
    metadata = _parse_json_dict(getattr(ctx.job, "metadata", None))
    if metadata.get("kwami_id"):
        return str(metadata["kwami_id"])

    for participant in ctx.room.remote_participants.values():
        raw_metadata = _parse_json_dict(getattr(participant, "metadata", None))
        if raw_metadata.get("kwami_id"):
            return str(raw_metadata["kwami_id"])

        attributes = getattr(participant, "attributes", None) or {}
        if isinstance(attributes, dict) and attributes.get("kwami_id"):
            return str(attributes["kwami_id"])

    return None


async def fetch_runtime_config(kwami_id: str) -> dict[str, Any] | None:
    if not KWAMI_API_KEY:
        logger.warning("KWAMI_API_KEY not set; telephony bootstrap is disabled")
        return None

    url = f"{API_BASE_URL.rstrip('/')}/internal/kwamis/{kwami_id}/runtime"
    timeout = _api_timeout_seconds()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers={"X-Kwami-API-Key": KWAMI_API_KEY})
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else None
    except httpx.HTTPStatusError as exc:
        body = (exc.response.text[:300] + "...") if exc.response and exc.response.text else ""
        logger.warning(
            "Kwami API returned %s for runtime config: %s",
            exc.response.status_code if exc.response else "?",
            body,
        )
        return None
    except httpx.RequestError as exc:
        logger.warning(
            "Kwami API unreachable for runtime config (%s: %s). "
            "KWAMI_API_URL=%r — if the agent runs in Docker/Kubernetes, localhost is the container, not your laptop; "
            "use the host LAN IP, host.docker.internal, or a public/tunnel URL.",
            type(exc).__name__,
            exc,
            API_BASE_URL,
        )
        return None
