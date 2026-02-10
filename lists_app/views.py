"""
Views for lists_app: SPA shell and API (API views in separate module or below).
"""

import logging

from django.views.generic import TemplateView

logger = logging.getLogger(__name__)


class SPATemplateView(TemplateView):
    template_name = "lists_app/index.html"

    def get(self, request, *args, **kwargs):
        logger.debug("spa view request path=%s", request.path)
        return super().get(request, *args, **kwargs)


spa_view = SPATemplateView.as_view()
