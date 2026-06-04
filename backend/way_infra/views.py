"""WAY Infrastructure Views"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.core.cache import cache

from .models import AuditLog, EventLog, TelemetryMetric, BackupLog, CacheMetadata, StorageObject
from .serializers import (
    AuditLogSerializer, EventLogSerializer, TelemetryMetricSerializer, BackupLogSerializer,
    CacheMetadataSerializer, StorageObjectSerializer
)
from .services import EventBus, CacheService, StorageService, AuditService, TelemetryService, BackupService
from way_infra.permissions import IsAdminOrReadOnly
from way_core.services import HealthService


from rest_framework.views import APIView

class HealthView(APIView):
    """System health check endpoint."""
    permission_classes = [AllowAny]
    def get(self, request):
        health = HealthService.check()
        status_code = status.HTTP_200_OK if health["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(health, status=status_code)


class MetricsView(APIView):
    """Prometheus-compatible metrics endpoint."""
    permission_classes = [AllowAny]
    def get(self, request):
        data = TelemetryService.get_dashboard_data()
        # Format as Prometheus text
        lines = ["# WAY Metrics"]
        for provider in data["providers"]:
            lines.append(f'way_provider_latency{{name="{provider["name"]}"}} {provider["latency_ms"]}')
            lines.append(f'way_provider_success_rate{{name="{provider["name"]}"}} {provider["success_rate"]}')
        lines.append(f"way_requests_total {data['metrics']['requests']}")
        lines.append(f"way_errors_total {data['metrics']['errors']}")
        lines.append(f"way_cache_keys {data['cache']['total_keys']}")
        return Response("\n".join(lines), content_type="text/plain")


class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    """Audit log (immutable, append-only)."""
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["entity_type", "action", "severity", "user_id"]

    @action(detail=False, methods=["get"])
    def verify(self, request):
        entity_type = request.query_params.get("entity_type")
        valid, errors = AuditService.verify_chain(entity_type)
        return Response({"valid": valid, "errors": errors, "checked_at": __import__("django.utils.timezone").now().isoformat()})


class EventViewSet(viewsets.ModelViewSet):
    """Event log management."""
    queryset = EventLog.objects.all()
    serializer_class = EventLogSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["event_type", "processed"]

    @action(detail=False, methods=["post"])
    def process(self, request):
        batch_size = request.data.get("batch_size", 100)
        count = EventBus.process_events(batch_size)
        return Response({"processed": count})


class TelemetryViewSet(viewsets.ReadOnlyModelViewSet):
    """Telemetry metrics."""
    queryset = TelemetryMetric.objects.all()
    serializer_class = TelemetryMetricSerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_fields = ["metric_type", "window"]

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        data = TelemetryService.get_dashboard_data()
        return Response(data)

    @action(detail=False, methods=["post"])
    def record(self, request):
        metric_type = request.data.get("metric_type")
        value = request.data.get("value")
        unit = request.data.get("unit", "")
        labels = request.data.get("labels", {})
        TelemetryService.record(metric_type, value, unit, labels)
        return Response({"success": True})


class BackupViewSet(viewsets.ModelViewSet):
    """Backup management."""
    queryset = BackupLog.objects.all()
    serializer_class = BackupLogSerializer
    permission_classes = [IsAdminOrReadOnly]

    @action(detail=False, methods=["post"])
    def create_backup(self, request):
        backup_type = request.data.get("backup_type", "postgres")
        backup = BackupService.create_backup(backup_type)
        return Response(BackupLogSerializer(backup).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        success = BackupService.restore_backup(pk)
        return Response({"success": success})


class CacheViewSet(viewsets.ReadOnlyModelViewSet):
    """Cache metadata."""
    queryset = CacheMetadata.objects.all()
    serializer_class = CacheMetadataSerializer
    permission_classes = [IsAdminOrReadOnly]

    @action(detail=False, methods=["get"])
    def stats(self, request):
        return Response(CacheService.get_stats())

    @action(detail=False, methods=["post"])
    def invalidate(self, request):
        pattern = request.data.get("pattern", "*")
        CacheService.invalidate_pattern(pattern)
        return Response({"success": True, "pattern": pattern})


class StorageViewSet(viewsets.ModelViewSet):
    """Storage object management."""
    queryset = StorageObject.objects.all()
    serializer_class = StorageObjectSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return StorageObject.objects.all()
        return StorageObject.objects.filter(owner_id=self.request.user.id)
