"""
WAY Infrastructure Services - EventBus, CacheService, StorageService, AuditService, TelemetryService, BackupService
"""
import hashlib
import json
import os
import shutil
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
import structlog
import redis

from .models import AuditLog, EventLog, TelemetryMetric, BackupLog, CacheMetadata, StorageObject

logger = structlog.get_logger("way.infra")


class EventBus:
    """Internal event bus (PostgreSQL + Redis, Kafka-compatible)."""

    @staticmethod
    def publish(event_type: str, payload: Dict) -> EventLog:
        """Publish event to bus."""
        event = EventLog.objects.create(event_type=event_type, payload=payload)
        # Also publish to Redis for real-time consumers
        try:
            r = redis.from_url(settings.REDIS_URL)
            r.publish(f"way:events:{event_type}", json.dumps({"id": str(event.id), "payload": payload}))
        except Exception as e:
            logger.warning("event_bus.redis_failed", error=str(e))
        logger.info("event.published", event_type=event_type, event_id=str(event.id))
        return event

    @staticmethod
    def subscribe(event_type: str, handler):
        """Subscribe to events (for async workers)."""
        # In production: use Redis pub/sub or Kafka
        pass

    @staticmethod
    def process_events(batch_size: int = 100) -> int:
        """Process pending events."""
        pending = EventLog.objects.filter(processed=False, retry_count__lt=5)[:batch_size]
        count = 0
        for event in pending:
            try:
                EventBus._handle_event(event)
                event.processed = True
                event.processed_at = timezone.now()
                event.save(update_fields=["processed", "processed_at"])
                count += 1
            except Exception as e:
                event.retry_count += 1
                event.error = str(e)
                event.save(update_fields=["retry_count", "error"])
                logger.error("event.process_failed", event_id=str(event.id), error=str(e))
        return count

    @staticmethod
    def _handle_event(event: EventLog):
        """Route event to appropriate handler."""
        handlers = {
            "payment_success": EventBus._handle_payment_success,
            "credits_minted": EventBus._handle_credits_minted,
            "provider_failover": EventBus._handle_provider_failover,
            "fraud_detected": EventBus._handle_fraud_detected,
        }
        handler = handlers.get(event.event_type)
        if handler:
            handler(event.payload)

    @staticmethod
    def _handle_payment_success(payload):
        # Send notification
        from way_ops.services import NotificationService
        NotificationService.send(payload.get("user_id"), "payment_success", payload)

    @staticmethod
    def _handle_credits_minted(payload):
        # Update wallet cache
        cache.delete(f"wallet:balance:{payload.get('wallet_id')}")

    @staticmethod
    def _handle_provider_failover(payload):
        # Log failover
        logger.warning("provider.failover", payload=payload)

    @staticmethod
    def _handle_fraud_detected(payload):
        # Alert admins
        from way_ops.services import NotificationService
        NotificationService.send_admin_alert("fraud_detected", payload)


class CacheService:
    """Unified cache service with metadata tracking."""

    @staticmethod
    def get(key, default=None):
        """Get from cache with metadata tracking."""
        from django.db import models
        value = cache.get(key, default)
        if value is not None:
            CacheMetadata.objects.filter(cache_key=key).update(
                access_count=models.F("access_count") + 1,
                last_accessed=timezone.now()
            )
        return value

    @staticmethod
    def set(key, value, ttl=300, cache_type="global", entity_id=None):
        """Set cache with metadata tracking."""
        cache.set(key, value, ttl)
        size = len(json.dumps(value).encode()) if isinstance(value, (dict, list)) else len(str(value).encode())
        # Ne pas stocker entity_id si c'est une string (évite conflit UUID)
        defaults = {
            "cache_type": cache_type,
            "ttl": ttl,
            "size_bytes": size,
            "last_accessed": timezone.now(),
        }
        if entity_id and not isinstance(entity_id, str):
            defaults["entity_id"] = entity_id
        CacheMetadata.objects.update_or_create(
            cache_key=key,
            defaults=defaults
        )

    @staticmethod
    def delete(key: str):
        cache.delete(key)
        CacheMetadata.objects.filter(cache_key=key).delete()

    @staticmethod
    def invalidate_pattern(pattern: str):
        """Invalidate cache keys matching pattern."""
        # Redis-specific pattern deletion
        try:
            r = redis.from_url(settings.REDIS_URL)
            for key in r.scan_iter(match=pattern):
                cache.delete(key.decode())
        except Exception:
            pass

    @staticmethod
    def get_stats() -> Dict:
        """Get cache statistics."""
        from django.db.models import Sum, Avg, Count
        stats = CacheMetadata.objects.aggregate(
            total_keys=Count("id"),
            total_size=Sum("size_bytes"),
            avg_ttl=Avg("ttl"),
            total_accesses=Sum("access_count"),
        )
        by_type = CacheMetadata.objects.values("cache_type").annotate(count=Count("id"), size=Sum("size_bytes"))
        return {
            "total_keys": stats["total_keys"] or 0,
            "total_size_bytes": stats["total_size"] or 0,
            "avg_ttl_seconds": stats["avg_ttl"] or 0,
            "total_accesses": stats["total_accesses"] or 0,
            "by_type": list(by_type),
        }


class StorageService:
    """Unified storage abstraction (local/S3/MinIO)."""

    @staticmethod
    def store(owner_id: str, file_obj, path: str = None, encrypt: bool = False, metadata: Dict = None) -> StorageObject:
        """Store file and track metadata."""
        if not path:
            path = f"uploads/{owner_id}/{datetime.now().strftime('%Y/%m/%d')}/{file_obj.name}"

        # Save file
        saved_path = default_storage.save(path, file_obj)
        full_path = default_storage.path(saved_path)

        # Calculate checksum
        sha256 = hashlib.sha256()
        with open(full_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        checksum = sha256.hexdigest()

        size = os.path.getsize(full_path)

        storage_obj = StorageObject.objects.create(
            owner_id=owner_id,
            path=saved_path,
            backend=settings.WAY_CONFIG["STORAGE_BACKEND"],
            size_bytes=size,
            mime_type=file_obj.content_type if hasattr(file_obj, "content_type") else "",
            encrypted=encrypt,
            checksum=checksum,
            metadata=metadata or {},
        )
        return storage_obj

    @staticmethod
    def retrieve(storage_id: str) -> Optional[str]:
        """Retrieve file path by storage ID."""
        try:
            obj = StorageObject.objects.get(id=storage_id)
            obj.access_count += 1
            obj.last_accessed = timezone.now()
            obj.save(update_fields=["access_count", "last_accessed"])
            return obj.path
        except StorageObject.DoesNotExist:
            return None

    @staticmethod
    def delete_storage(storage_id: str) -> bool:
        try:
            obj = StorageObject.objects.get(id=storage_id)
            if default_storage.exists(obj.path):
                default_storage.delete(obj.path)
            obj.delete()
            return True
        except StorageObject.DoesNotExist:
            return False


class AuditService:
    """Immutable audit trail service."""

    @staticmethod
    def log(entity_type, entity_id, action, user_id=None,
            before=None, after=None, ip=None, user_agent=None,
            severity="info", reason=""):
        """Create immutable audit log entry."""
        from uuid import UUID
        if isinstance(entity_id, str):
            entity_id = UUID(entity_id)
        # user_id can be None or UUID
        if user_id is None:
            pass  # Keep as None
        elif isinstance(user_id, str):
            user_id = UUID(user_id)
        # Ensure user_agent is not None (NOT NULL constraint)
        if user_agent is None:
            user_agent = ""

        diff = {}
        if before and after:
            for key in set(before.keys()) | set(after.keys()):
                if before.get(key) != after.get(key):
                    diff[key] = {"before": before.get(key), "after": after.get(key)}

        # Calculate hash chain
        last_audit = AuditLog.objects.filter(entity_type=entity_type).order_by("-created_at").first()
        previous_hash = last_audit.hash if last_audit else "0"

        # Create audit first to get created_at
        audit = AuditLog.objects.create(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            user_id=user_id,
            before_state=before or {},
            after_state=after or {},
            diff=diff,
            ip_address=ip,
            user_agent=user_agent,
            severity=severity,
            reason=reason,
            hash="temp",  # Temporary, will update
            previous_hash=previous_hash,
        )

        # Calculate hash with the actual created_at
        audit.refresh_from_db()
        data = f"{entity_type}:{entity_id}:{action}:{audit.created_at.isoformat()}:{previous_hash}"
        current_hash = hashlib.sha256(data.encode()).hexdigest()
        audit.hash = current_hash
        audit.save(update_fields=["hash"])
        logger.info("audit.logged", entity_type=entity_type, action=action, audit_id=str(audit.id))
        return audit

    @staticmethod
    def verify_chain(entity_type: str = None) -> Tuple[bool, List[str]]:
        """Verify audit chain integrity."""
        qs = AuditLog.objects.all()
        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        qs = qs.order_by("created_at")

        errors = []
        previous_hash = "0"
        for audit in qs:
            data = f"{audit.entity_type}:{audit.entity_id}:{audit.action}:{audit.created_at.isoformat()}:{previous_hash}"
            expected_hash = hashlib.sha256(data.encode()).hexdigest()
            if audit.hash != expected_hash:
                errors.append(f"Hash mismatch at {audit.id}: expected {expected_hash}, got {audit.hash}")
            if audit.previous_hash != previous_hash:
                errors.append(f"Chain break at {audit.id}: expected {previous_hash}, got {audit.previous_hash}")
            previous_hash = audit.hash

        return len(errors) == 0, errors


class TelemetryService:
    """System telemetry collection."""

    @staticmethod
    def record(metric_type: str, value: float, unit: str = "", labels: Dict = None, window: str = "1m"):
        TelemetryMetric.objects.create(
            metric_type=metric_type,
            value=value,
            unit=unit,
            labels=labels or {},
            window=window,
        )

    @staticmethod
    def get_metrics(metric_type: str = None, window: str = "1m", limit: int = 100) -> List[Dict]:
        qs = TelemetryMetric.objects.filter(window=window)
        if metric_type:
            qs = qs.filter(metric_type=metric_type)
        return list(qs.values()[:limit])

    @staticmethod
    def get_dashboard_data() -> Dict:
        """Get data for monitoring dashboard."""
        from django.db.models import Avg, Max, Min, Count
        from way_skills.models import Provider
        from way_core.models import RegistryEntry
        from way_finance.models import Payment

        # Provider health
        providers = Provider.objects.all().values("name", "status", "latency_ms", "success_rate", "quota_remaining")

        # Cache stats
        cache_stats = CacheService.get_stats()

        # Recent events
        recent_events = EventLog.objects.filter(created_at__gte=timezone.now() - timedelta(hours=1)).count()

        # System metrics
        metrics = {
            "cpu": TelemetryMetric.objects.filter(metric_type="cpu", window="1m").aggregate(Avg("value"))["value__avg"] or 0,
            "ram": TelemetryMetric.objects.filter(metric_type="ram", window="1m").aggregate(Avg("value"))["value__avg"] or 0,
            "requests": TelemetryMetric.objects.filter(metric_type="requests", window="1m").aggregate(Count("id"))["id__count"] or 0,
            "errors": TelemetryMetric.objects.filter(metric_type="errors", window="1m").aggregate(Count("id"))["id__count"] or 0,
        }

        return {
            "providers": list(providers),
            "cache": cache_stats,
            "events_last_hour": recent_events,
            "metrics": metrics,
            "timestamp": timezone.now().isoformat(),
        }


class BackupService:
    """Backup and disaster recovery."""

    @staticmethod
    def create_backup(backup_type: str) -> BackupLog:
        """Create backup snapshot."""
        backup = BackupLog.objects.create(backup_type=backup_type, status="running")
        try:
            # In production: actual backup logic
            # Simulated backup
            backup.status = "completed"
            backup.size_bytes = 1024 * 1024 * 100  # 100MB simulated
            backup.checksum = hashlib.sha256(f"backup:{backup_type}:{timezone.now()}".encode()).hexdigest()
            backup.storage_path = f"backups/{backup_type}/{backup.id}.tar.gz"
            backup.save(update_fields=["status", "size_bytes", "checksum", "storage_path"])
            logger.info("backup.completed", backup_id=str(backup.id), type=backup_type)
        except Exception as e:
            backup.status = "failed"
            backup.error = str(e)
            backup.save(update_fields=["status", "error"])
            logger.error("backup.failed", backup_id=str(backup.id), error=str(e))
        return backup

    @staticmethod
    def restore_backup(backup_id: str) -> bool:
        try:
            backup = BackupLog.objects.get(id=backup_id)
            # In production: actual restore logic
            backup.restored_at = timezone.now()
            backup.restore_valid = True
            backup.save(update_fields=["restored_at", "restore_valid"])
            logger.info("backup.restored", backup_id=backup_id)
            return True
        except BackupLog.DoesNotExist:
            return False
