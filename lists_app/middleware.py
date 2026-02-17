"""
Middleware: require valid secret-URL token for app and API (except admin, static, enter, auth/required).
"""

import logging

from django.conf import settings
from django.shortcuts import redirect

from lists_app.models import AccessToken
from lists_app.views import SESSION_ACCESS_TOKEN_ID_KEY

logger = logging.getLogger(__name__)

SKIP_PREFIXES = ("/admin/", "/static/", "/enter/", "/auth/required/")
SKIP_PATHS = ("/favicon.ico",)


def _should_skip(path):
    if path in SKIP_PATHS:
        return True
    return any(path.startswith(p) for p in SKIP_PREFIXES)


class SecretURLRequiredMiddleware:
    """Redirect to /auth/required/ if no valid secret-URL token in session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, "SECRET_URL_AUTH_REQUIRED", True):
            return self.get_response(request)
        path = request.path
        if _should_skip(path):
            return self.get_response(request)

        token_id = request.session.get(SESSION_ACCESS_TOKEN_ID_KEY)
        if not token_id:
            return redirect("/auth/required/")

        try:
            access_token = AccessToken.objects.get(pk=token_id)
        except AccessToken.DoesNotExist:
            request.session.flush()
            logger.info("Session had invalid token_id=%s, flushed", token_id)
            return redirect("/auth/required/?revoked=1")

        if access_token.revoked:
            request.session.flush()
            logger.info("Session token_id=%s revoked, flushed", token_id)
            return redirect("/auth/required/?revoked=1")

        return self.get_response(request)
