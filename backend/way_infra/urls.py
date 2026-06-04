"""WAY Infrastructure URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AuditViewSet, EventViewSet, TelemetryViewSet, BackupViewSet, CacheViewSet, StorageViewSet

router = DefaultRouter()
router.register(r"audit", AuditViewSet, basename="audit")
router.register(r"events", EventViewSet, basename="events")
router.register(r"telemetry", TelemetryViewSet, basename="telemetry")
router.register(r"backups", BackupViewSet, basename="backups")
router.register(r"cache", CacheViewSet, basename="cache")
router.register(r"storage", StorageViewSet, basename="storage")

urlpatterns = [
    path("", include(router.urls)),
]
