"""WAY Infrastructure Serializers"""
from rest_framework import serializers
from .models import AuditLog, EventLog, TelemetryMetric, BackupLog, CacheMetadata, StorageObject


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "entity_type", "entity_id", "action", "user_id", "before_state", "after_state", "diff", "severity", "reason", "hash", "previous_hash", "created_at"]
        read_only_fields = ["id", "hash", "previous_hash", "created_at"]


class EventLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventLog
        fields = ["id", "event_type", "payload", "processed", "processed_at", "error", "retry_count", "created_at"]


class TelemetryMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryMetric
        fields = ["id", "metric_type", "value", "unit", "labels", "window", "created_at"]


class BackupLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupLog
        fields = ["id", "backup_type", "status", "size_bytes", "checksum", "storage_path", "restored_at", "restore_valid", "created_at"]
        read_only_fields = ["id", "checksum", "created_at"]


class CacheMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = CacheMetadata
        fields = ["id", "cache_key", "cache_type", "entity_id", "ttl", "size_bytes", "access_count", "last_accessed", "compressed"]


class StorageObjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = StorageObject
        fields = ["id", "path", "backend", "size_bytes", "mime_type", "encrypted", "checksum", "metadata", "access_count", "created_at"]
        read_only_fields = ["id", "checksum", "created_at"]
