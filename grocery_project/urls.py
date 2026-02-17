"""
URL configuration for grocery_project.
API under /api/; SPA catch-all for / and /list/<id>/.
Static files served in DEBUG when using Daphne (runserver serves them automatically).
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from lists_app.views import auth_required_view, gate_view, spa_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("lists_app.urls")),
    path("enter/<str:token>/", gate_view),
    path("auth/required/", auth_required_view),
    re_path(r"^list/(?P<list_id>[0-9a-f-]+)/?$", spa_view),
    path("", spa_view),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
