"""
Shared LLM client for OpenAI-compatible APIs. Reads all config from Django settings.
"""

import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def call_llm(
    prompt: str,
    *,
    max_tokens: int = 256,
    timeout: int | None = None,
) -> str | None:
    """
    Call the configured LLM with a single user message. Returns the assistant content or None.
    Reads LLM_API_KEY, LLM_API_URL, LLM_MODEL, LLM_TIMEOUT from settings.
    """
    api_key = getattr(settings, "LLM_API_KEY", "") or ""
    if not api_key:
        return None
    api_url = getattr(
        settings,
        "LLM_API_URL",
        "https://api.openai.com/v1/chat/completions",
    )
    model = getattr(settings, "LLM_MODEL", "Meta-Llama-3_3-70B-Instruct")
    default_timeout = getattr(settings, "LLM_TIMEOUT", 30)
    timeout = timeout if timeout is not None else default_timeout
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(api_url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return None
        content = (choices[0].get("message") or {}).get("content") or ""
        return content
    except (requests.RequestException, json.JSONDecodeError, KeyError) as e:
        logger.warning("LLM call failed: %s", e)
        return None
