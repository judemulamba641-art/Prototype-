"""
WAY Infrastructure Models - Unified: Cache + Storage + Events + Telemetry + Audit + Backup
"""
import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings

from way_core.models import BaseModel


class AuditLog(BaseModel):
    """Immutable audit trail (append-only)."""
    AUDIT_TYPES = [
        ("credit", "Credit"), ("wallet", "Wallet"), ("admin", "Admin"),
        ("skill", "Skill"), ("payment", "Payment"), ("auth", "Auth"),
        ("permission", "Permission"), ("system", "System"),
    ]
    SEVERITY = [("info", "Info"), ("warning", "Warning"), ("critical", "Critical")]

    entity_type = models.CharField(max_length=20, choices=AUDIT_TYPES, db_index=True)
    entity_id = models.UUIDField(db_index=True)
    action = models.CharField(max_length=50, db_index=True)  # create, update, delete, execute, transfer
    user_id = models.UUIDField(null=True, blank=True, db_index=True)
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    diff = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    severity = models.CharField(max_length=20, choices=SEVERITY, default="info")
    reason = models.TextField(blank=True)
    hash = models.CharField(max_length=255, db_index=True)  # Chain hash for immutability
    previous_hash = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id", "created_at"]),
            models.Index(fields=["user_id", "action", "created_at"]),
            models.Index(fields=["severity", "created_at"]),
        ]

    def __str__(self):
        return f"{self.entity_type}:{self.action} -> {self.entity_id}"


class EventLog(BaseModel):
    """Event bus log."""
    EVENT_TYPES = [
        ("skill_installed", "Skill Installed"), ("skill_created", "Skill Created"),
        ("payment_success", "Payment Success"), ("payment_failed", "Payment Failed"),
        ("credits_minted", "Credits Minted"), ("credits_burned", "Credits Burned"),
        ("credits_transferred", "Credits Transferred"),
        ("wallet_updated", "Wallet Updated"), ("provider_failover", "Provider Failover"),
        ("cache_invalidated", "Cache Invalidated"), ("notification", "Notification"),
        ("audit_event", "Audit Event"), ("fraud_detected", "Fraud Detected"),
        ("execution_queued", "Execution Queued"), ("execution_completed", "Execution Completed"),
        ("execution_failed", "Execution Failed"),
    ]
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES, db_index=True)
    payload = models.JSONField(default=dict)
    processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "processed", "created_at"]),
            models.Index(fields=["processed", "retry_count"]),
        ]


class TelemetryMetric(BaseModel):
    """System telemetry metrics."""
    METRIC_TYPES = [
        ("cpu", "CPU"), ("ram", "RAM"), ("disk", "Disk"), ("network", "Network"),
        ("latency", "Latency"), ("requests", "Requests"), ("errors", "Errors"),
        ("cache_hit", "Cache Hit"), ("cache_miss", "Cache Miss"),
    ]
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES, db_index=True)
    value = models.FloatField()
    unit = models.CharField(max_length=20, default="")  # %, ms, MB, count
    labels = models.JSONField(default=dict, blank=True)  # {endpoint: "/api/skills", method: "GET"}
    window = models.CharField(max_length=20, default="1m")  # 1m, 5m, 1h, 1d

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["metric_type", "window", "created_at"])]


class BackupLog(BaseModel):
    """Backup and disaster recovery log."""
    BACKUP_TYPES = [
        ("postgres", "PostgreSQL"), ("redis", "Redis"), ("minio", "MinIO"),
        ("wallets", "Wallets"), ("audit", "Audit Logs"), ("reserve", "Reserve Snapshots"),
    ]
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES, db_index=True)
    status = models.CharField(max_length=20, choices=[("pending", "Pending"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], default="pending")
    size_bytes = models.PositiveBigIntegerField(default=0)
    checksum = models.CharField(max_length=255, blank=True)
    encryption_key_id = models.CharField(max_length=255, blank=True)
    storage_path = models.CharField(max_length=500, blank=True)
    restored_at = models.DateTimeField(null=True, blank=True)
    restore_valid = models.BooleanField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]


class CacheMetadata(BaseModel):
    """Cache metadata tracking."""
    cache_key = models.CharField(max_length=255, db_index=True)
    cache_type = models.CharField(max_length=20, choices=[("user", "User"), ("dev", "Dev"), ("group", "Group"), ("global", "Global")], default="global")
    entity_id = models.UUIDField(null=True, blank=True)
    ttl = models.PositiveIntegerField(default=300)
    size_bytes = models.PositiveIntegerField(default=0)
    access_count = models.PositiveIntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)
    compressed = models.BooleanField(default=False)
    compression_ratio = models.FloatField(default=1.0)

    class Meta:
        indexes = [models.Index(fields=["cache_type", "entity_id", "last_accessed"])]


class StorageObject(BaseModel):
    """Storage object tracking."""
    STORAGE_BACKENDS = [
        ("local", "Local"), ("s3", "S3"), ("minio", "MinIO"), ("postgres", "PostgreSQL"),
    ]
    owner_id = models.UUIDField(db_index=True)
    path = models.CharField(max_length=500)
    backend = models.CharField(max_length=20, choices=STORAGE_BACKENDS, default="local")
    size_bytes = models.PositiveBigIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    encrypted = models.BooleanField(default=False)
    encryption_key_id = models.CharField(max_length=255, blank=True)
    checksum = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    access_count = models.PositiveIntegerField(default=0)
    last_accessed = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["owner_id", "backend", "created_at"])]
