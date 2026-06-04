"""ASGI config for way_project."""
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from way_infra.middleware import WebSocketJWTAuthMiddleware

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "way_project.settings")

django_asgi_app = get_asgi_application()

from way_infra.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": WebSocketJWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})
