"""
WAY Core Models - Unified: Core + Runtime + SDK + Registry + Sandbox
"""
import uuid
import json
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class BaseModel(models.Model):
    """Abstract base model with UUID, timestamps, soft delete."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at"])

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class RegistryEntry(BaseModel):
    """Global registry for skills, providers, nodes, sessions, devices."""
    ENTITY_TYPES = [
        ("skill", "Skill"), ("wallet", "Wallet"), ("provider", "Provider"),
        ("node", "Node"), ("session", "Session"), ("device", "Device"),
    ]
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES, db_index=True)
    entity_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, default="active", db_index=True)
    version = models.CharField(max_length=20, default="1.0.0")
    health = models.JSONField(default=dict)  # {cpu: 45, ram: 60, latency: 120}
    config = models.JSONField(default=dict)
    last_heartbeat = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [["entity_type", "entity_id"]]
        indexes = [models.Index(fields=["entity_type", "status", "last_heartbeat"])]

    def __str__(self):
        return f"{self.entity_type}:{self.name}"


class HeartbeatLog(BaseModel):
    """Heartbeat tracking for all registered entities."""
    registry_entry = models.ForeignKey(RegistryEntry, on_delete=models.CASCADE, related_name="heartbeats")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    metrics = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default="healthy")

    class Meta:
        ordering = ["-timestamp"]


class RuntimeSession(BaseModel):
    """Active runtime sessions with sandbox configuration."""
    STATUS_CHOICES = [
        ("pending", "Pending"), ("running", "Running"), ("completed", "Completed"),
        ("failed", "Failed"), ("timeout", "Timeout"), ("killed", "Killed"),
    ]
    user_id = models.UUIDField(db_index=True)
    skill_id = models.UUIDField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    sandbox_config = models.JSONField(default=dict)  # {ram: 256, cpu: 2, disk: 100, timeout: 15, network: "restricted"}
    resource_usage = models.JSONField(default=dict)  # {cpu_peak: 80, ram_peak: 200, disk_used: 50}
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    exit_code = models.IntegerField(null=True, blank=True)
    logs = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["user_id", "status", "started_at"])]


class SDKManifest(BaseModel):
    """SDK compatibility and manifest tracking."""
    sdk_version = models.CharField(max_length=20, db_index=True)
    runtime_version = models.CharField(max_length=20, db_index=True)
    compatibility = models.CharField(max_length=20, choices=[("compatible", "Compatible"), ("blocked", "Blocked"), ("migration", "Migration Needed")])
    features = models.JSONField(default=list)
    deprecated = models.BooleanField(default=False)

    class Meta:
        unique_together = [["sdk_version", "runtime_version"]]


class SystemConfig(BaseModel):
    """Centralized system configuration."""
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.JSONField()
    encrypted = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.key
