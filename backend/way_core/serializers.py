"""WAY Core Serializers"""
from rest_framework import serializers
from .models import RegistryEntry, RuntimeSession, SDKManifest, SystemConfig, HeartbeatLog


class RegistryEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistryEntry
        fields = ["id", "entity_type", "entity_id", "name", "status", "version", "health", "config", "last_heartbeat", "created_at"]
        read_only_fields = ["id", "created_at"]


class RuntimeSessionSerializer(serializers.ModelSerializer):
    duration = serializers.SerializerMethodField()

    class Meta:
        model = RuntimeSession
        fields = ["id", "user_id", "skill_id", "status", "sandbox_config", "resource_usage", "started_at", "ended_at", "duration", "exit_code", "logs"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_duration(self, obj):
        if obj.started_at and obj.ended_at:
            return (obj.ended_at - obj.started_at).total_seconds()
        return None


class SDKManifestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SDKManifest
        fields = "__all__"


class SystemConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfig
        fields = ["id", "key", "value", "encrypted", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.CharField()
    version = serializers.CharField()
    uptime = serializers.FloatField()
    services = serializers.DictField()
    timestamp = serializers.DateTimeField()
