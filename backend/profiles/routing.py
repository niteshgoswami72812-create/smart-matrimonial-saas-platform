from django.urls import re_path

from .consumers import (
    CallConsumer,
    PresenceConsumer,
    ChatConsumer,
)

websocket_urlpatterns = [
    re_path(
        r"^ws/call/(?P<profile_id>\d+)/$",
        CallConsumer.as_asgi(),
    ),
    re_path(
        r"^ws/presence/$",
        PresenceConsumer.as_asgi(),
    ),
    re_path(
        r"^ws/chat/(?P<profile_id>\d+)/$",
        ChatConsumer.as_asgi(),
    ),
]