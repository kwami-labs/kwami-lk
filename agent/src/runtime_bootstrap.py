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
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers={"X-Kwami-API-Key": KWAMI_API_KEY})
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
