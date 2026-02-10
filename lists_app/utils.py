"""
Shared utilities for lists_app (UUID parsing, request JSON).
"""

import json
import logging
import uuid

from django.http import JsonResponse

logger = logging.getLogger(__name__)


def parse_uuid(value):
    """Return uuid.UUID or None. Accepts None, uuid.UUID, or str."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def get_request_json(request, default=None):
    """
    Parse request body as JSON. Returns (body_dict, error_response).
    On success: (body, None). On decode error: (default or {}, JsonResponse 400).
    """
    try:
        raw = request.body.decode("utf-8") or "{}"
        body = json.loads(raw)
        if not isinstance(body, dict):
            body = default if default is not None else {}
        return (body, None)
    except Exception as e:
        logger.warning("get_request_json invalid body: %s", e)
        return (
            default if default is not None else {},
            JsonResponse({"error": "Invalid JSON"}, status=400),
        )
