"""WAY WebSocket Routing"""
from django.urls import re_path, path
from .consumers import NotificationConsumer, WalletUpdateConsumer

websocket_urlpatterns = [
    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
    re_path(r"ws/wallet/$", WalletUpdateConsumer.as_asgi()),
]

# Pour Django URL resolver (non-WebSocket)
urlpatterns = []
