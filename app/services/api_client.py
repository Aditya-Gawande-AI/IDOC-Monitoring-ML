from __future__ import annotations

import logging
from typing import Dict

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _auth_headers() -> Dict[str, str]:
    return {
        "Origin": settings.idoc_origin_header,
        "Accept": "application/atom+xml, application/xml, text/xml",
    }


async def fetch_idoc_feed() -> str:
    if not settings.idoc_api_url:
        raise ValueError("IDOC_API_URL is not configured")

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds, verify=settings.verify_tls) as client:
        response = await client.get(
            settings.idoc_api_url,
            auth=(settings.idoc_api_username, settings.idoc_api_password),
            headers=_auth_headers(),
        )
        response.raise_for_status()
        logger.info("Fetched IDoc payload with status=%s", response.status_code)
        return response.text
