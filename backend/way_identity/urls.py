"""WAY Identity URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuthViewSet, UserViewSet, DeviceViewSet, PermissionViewSet, GroupViewSet

router = DefaultRouter()
router.register(r"auth", AuthViewSet, basename="auth")
# Actions personnalisées:
# POST /api/auth/register/ -> register
# POST /api/auth/login/ -> login
# POST /api/auth/wallet_login/ -> wallet_login
# POST /api/auth/refresh/ -> refresh
# POST /api/auth/logout/ -> logout
router.register(r"users", UserViewSet, basename="users")
router.register(r"devices", DeviceViewSet, basename="devices")
router.register(r"permissions", PermissionViewSet, basename="permissions")
router.register(r"groups", GroupViewSet, basename="groups")

urlpatterns = [
    path("", include(router.urls)),
]
