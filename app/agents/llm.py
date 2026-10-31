"""Chat-model factory for the native OpenRouter HTTP API."""
from __future__ import annotations

import logging
from typing import Any

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def get_llm(settings: Settings | None = None) -> Any | None:
    """Build the native OpenRouter chat model, or None when no key is configured."""
    settings = settings or get_settings()
    if not settings.llm_configured:
        return None
    from app.agents.openrouter import OpenRouterChatModel
    headers = {"X-Title": settings.openrouter_app_name}
    if settings.openrouter_site_url.strip():
        headers["HTTP-Referer"] = settings.openrouter_site_url.strip()
    return OpenRouterChatModel(
        model=settings.llm_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url.strip(),
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        headers=headers,
    )
