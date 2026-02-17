"""
Views for lists_app: SPA shell, gate (secret URL), auth-required page, API (in api_views).
"""

import logging

from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from lists_app.models import AccessToken

logger = logging.getLogger(__name__)

SESSION_ACCESS_TOKEN_ID_KEY = "secret_url_token_id"


class SPATemplateView(TemplateView):
    template_name = "lists_app/index.html"

    def get(self, request, *args, **kwargs):
        logger.debug("spa view request path=%s", request.path)
        return super().get(request, *args, **kwargs)


def gate_view(request, token):
    """Validate secret URL token and create session; redirect to / or /auth/required/."""
    try:
        access_token = AccessToken.objects.get(token=token)
    except AccessToken.DoesNotExist:
        return redirect("/auth/required/?revoked=1")
    if access_token.revoked:
        return redirect("/auth/required/?revoked=1")
    request.session[SESSION_ACCESS_TOKEN_ID_KEY] = access_token.id
    request.session.save()
    logger.info("Secret URL used token_id=%s", access_token.id)
    return redirect("/")


def auth_required_view(request):
    """Show 'access required' or 'link revoked' message."""
    revoked = request.GET.get("revoked") == "1"
    return render(request, "lists_app/auth_required.html", {"revoked": revoked})


spa_view = SPATemplateView.as_view()
