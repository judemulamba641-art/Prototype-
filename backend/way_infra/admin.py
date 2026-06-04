"""WAY Infrastructure Admin"""
from django.contrib import admin
from .models import AuditLog, EventLog, TelemetryMetric, BackupLog, CacheMetadata, StorageObject

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["entity_type", "entity_id", "action", "user_id", "severity", "created_at"]
    list_filter = ["entity_type", "action", "severity"]
    readonly_fields = ["hash", "previous_hash", "diff"]
    search_fields = ["entity_id", "user_id"]
    date_hierarchy = "created_at"

@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ["event_type", "processed", "retry_count", "created_at"]
    list_filter = ["event_type", "processed"]
    actions = ["mark_processed"]

    def mark_processed(self, request, queryset):
        queryset.update(processed=True, processed_at=timezone.now())
    mark_processed.short_description = "Mark selected events as processed"

@admin.register(TelemetryMetric)
class TelemetryMetricAdmin(admin.ModelAdmin):
    list_display = ["metric_type", "value", "unit", "window", "created_at"]
    list_filter = ["metric_type", "window"]

@admin.register(BackupLog)
class BackupLogAdmin(admin.ModelAdmin):
    list_display = ["backup_type", "status", "size_bytes", "created_at"]
    list_filter = ["backup_type", "status"]

@admin.register(CacheMetadata)
class CacheMetadataAdmin(admin.ModelAdmin):
    list_display = ["cache_key", "cache_type", "size_bytes", "access_count", "last_accessed"]
    list_filter = ["cache_type"]

@admin.register(StorageObject)
class StorageObjectAdmin(admin.ModelAdmin):
    list_display = ["owner_id", "path", "backend", "size_bytes", "encrypted", "created_at"]
    list_filter = ["backend", "encrypted"]
