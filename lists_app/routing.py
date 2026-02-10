"""
WebSocket URL routing for lists_app.
"""

from django.urls import re_path

from lists_app.consumers import ListConsumer

websocket_urlpatterns = [
    re_path(r"ws/list/(?P<list_id>[0-9a-f-]+)/$", ListConsumer.as_asgi()),
]
