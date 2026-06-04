"""WAY Core URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegistryViewSet, RuntimeViewSet, SDKViewSet, ConfigViewSet

router = DefaultRouter()
router.register(r"registry", RegistryViewSet, basename="registry")
router.register(r"runtime", RuntimeViewSet, basename="runtime")
router.register(r"sdk", SDKViewSet, basename="sdk")
router.register(r"config", ConfigViewSet, basename="config")

urlpatterns = [
    path("", include(router.urls)),
]
