"""
API URL configuration for lists_app.
REST-style: same path for different methods where applicable.
"""

from django.urls import path

from lists_app import api_views

urlpatterns = [
    path("lists/", api_views.api_lists),
    path("lists/<uuid:list_id>/", api_views.api_list_detail),
    path("lists/<uuid:list_id>/parse-import/", api_views.api_parse_import),
    path("lists/<uuid:list_id>/deduplicate/", api_views.api_deduplicate),
    path("lists/<uuid:list_id>/items/", api_views.api_create_item),
    path("lists/<uuid:list_id>/items/<uuid:item_id>/", api_views.api_item_detail),
    path("lists/<uuid:list_id>/reorder/", api_views.api_reorder),
]
