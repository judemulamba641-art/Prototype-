"""WAY Core Views"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.core.cache import cache

from .models import RegistryEntry, RuntimeSession, SDKManifest, SystemConfig
from .serializers import (
    RegistryEntrySerializer, RuntimeSessionSerializer, 
    SDKManifestSerializer, SystemConfigSerializer, HealthCheckSerializer
)
from .services import RegistryService, RuntimeService, ConfigService, HealthService
from way_infra.permissions import IsAdminOrReadOnly, IsSystem


class RegistryViewSet(viewsets.ModelViewSet):
    """Global registry management."""
    queryset = RegistryEntry.objects.all()
    serializer_class = RegistryEntrySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["entity_type", "status", "version"]
    search_fields = ["name"]

    @action(detail=True, methods=["post"])
    def heartbeat(self, request, pk=None):
        entry = self.get_object()
        metrics = request.data.get("metrics", {})
        success = RegistryService.heartbeat(entry.entity_type, str(entry.entity_id), metrics)
        return Response({"success": success})

    @action(detail=False, methods=["get"])
    def health(self, request):
        entity_type = request.query_params.get("type")
        entries = RegistryService.list_by_type(entity_type) if entity_type else RegistryEntry.objects.all()
        stale = [e for e in entries if e.last_heartbeat and (timezone.now() - e.last_heartbeat).seconds > 300]
        return Response({"total": len(entries), "stale": len(stale), "healthy": len(entries) - len(stale)})


class RuntimeViewSet(viewsets.ModelViewSet):
    """Runtime session management."""
    queryset = RuntimeSession.objects.all()
    serializer_class = RuntimeSessionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["status", "user_id", "skill_id"]

    def create(self, request):
        user_id = request.user.id
        skill_id = request.data.get("skill_id")
        config = request.data.get("config", {})
        session = RuntimeService.create_session(str(user_id), str(skill_id), config)
        return Response(RuntimeSessionSerializer(session).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        success = RuntimeService.start_session(pk)
        return Response({"success": success})

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        exit_code = request.data.get("exit_code", 0)
        logs = request.data.get("logs", "")
        success = RuntimeService.complete_session(pk, exit_code, logs)
        return Response({"success": success})

    @action(detail=True, methods=["post"])
    def kill(self, request, pk=None):
        reason = request.data.get("reason", "manual")
        success = RuntimeService.kill_session(pk, reason)
        return Response({"success": success})

    @action(detail=True, methods=["get"])
    def enforce(self, request, pk=None):
        session = self.get_object()
        actions = RuntimeService.enforce_sandbox(session)
        return Response(actions)


class SDKViewSet(viewsets.ReadOnlyModelViewSet):
    """SDK compatibility matrix."""
    queryset = SDKManifest.objects.all()
    serializer_class = SDKManifestSerializer
    permission_classes = [AllowAny]
    filterset_fields = ["sdk_version", "runtime_version", "compatibility"]

    @action(detail=False, methods=["get"])
    def check(self, request):
        sdk = request.query_params.get("sdk_version")
        runtime = request.query_params.get("runtime_version")
        try:
            manifest = SDKManifest.objects.get(sdk_version=sdk, runtime_version=runtime)
            return Response({"compatible": manifest.compatibility == "compatible", "status": manifest.compatibility})
        except SDKManifest.DoesNotExist:
            return Response({"compatible": False, "status": "unknown"}, status=status.HTTP_404_NOT_FOUND)


class ConfigViewSet(viewsets.ModelViewSet):
    """System configuration."""
    queryset = SystemConfig.objects.all()
    serializer_class = SystemConfigSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "key"

    @action(detail=False, methods=["get"])
    def get_value(self, request):
        key = request.query_params.get("key")
        default = request.query_params.get("default")
        value = ConfigService.get(key, default)
        return Response({"key": key, "value": value})

    @action(detail=False, methods=["post"])
    def set_value(self, request):
        key = request.data.get("key")
        value = request.data.get("value")
        encrypted = request.data.get("encrypted", False)
        ConfigService.set(key, value, encrypted)
        return Response({"success": True})
