"""
WAY User Monitoring Service - Enterprise Grade
Full integration with way_infra monitoring
"""
from typing import Dict, Any, List
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Sum, Count
import structlog

from way_infra.models import AuditLog, EventLog, TelemetryMetric, BackupLog, CacheMetadata
from way_infra.services import TelemetryService, AuditService, BackupService, CacheService
from way_skills.models import Provider
from way_finance.models import Wallet, Payment
from django.contrib.auth import get_user_model

logger = structlog.get_logger("way_user.monitoring")


class MonitoringService:
    """Enterprise-grade monitoring aggregation service."""

    @staticmethod
    def get_dashboard_data() -> Dict[str, Any]:
        """Get comprehensive monitoring dashboard."""
        cache_key = "monitoring:dashboard:v2"
        cached = cache.get(cache_key)
        if cached:
            return cached

        User = get_user_model()
        now = timezone.now()
        today = now.date()
        hour_ago = now - timedelta(hours=1)

        # System metrics
        metrics = TelemetryService.get_dashboard_data()

        # Provider health
        providers = Provider.objects.all()

        # User stats
        user_stats = {
            "total": User.objects.count(),
            "active": User.objects.filter(is_active=True).count(),
            "new_today": User.objects.filter(date_joined__date=today).count(),
            "active_today": User.objects.filter(last_login__date=today).count(),
            "locked": User.objects.filter(
                locked_until__isnull=False, locked_until__gt=now
            ).count(),
        }

        # Wallet stats
        wallet_stats = {
            "total": Wallet.objects.count(),
            "active": Wallet.objects.filter(is_active=True).count(),
            "frozen": Wallet.objects.filter(frozen=True).count(),
            "total_balance": str(Wallet.objects.aggregate(total=Sum("balance"))["total__sum"] or 0),
        }

        # Payment stats
        payment_stats = {
            "pending": Payment.objects.filter(status="pending").count(),
            "completed_today": Payment.objects.filter(status="completed", processed_at__date=today).count(),
            "failed_today": Payment.objects.filter(status="failed", created_at__date=today).count(),
            "total_volume_today": str(Payment.objects.filter(
                status="completed", processed_at__date=today
            ).aggregate(total=Sum("amount"))["total__sum"] or 0),
        }

        # Audit stats
        audit_stats = {
            "total_logs": AuditLog.objects.count(),
            "today_logs": AuditLog.objects.filter(created_at__date=today).count(),
            "critical_events": AuditLog.objects.filter(severity="critical").count(),
            "chain_valid": AuditService.verify_chain()[0],
        }

        # Event stats
        event_stats = {
            "pending": EventLog.objects.filter(processed=False).count(),
            "failed": EventLog.objects.filter(processed=False, retry_count__gte=5).count(),
            "processed_today": EventLog.objects.filter(processed=True, processed_at__date=today).count(),
        }

        # Cache stats
        cache_stats = CacheService.get_stats()

        result = {
            "timestamp": now.isoformat(),
            "system": metrics,
            "providers": {
                p.name: {
                    "status": p.status,
                    "latency_ms": p.latency_ms,
                    "success_rate": p.success_rate,
                    "quota_remaining": p.quota_remaining,
                }
                for p in providers
            },
            "users": user_stats,
            "wallets": wallet_stats,
            "payments": payment_stats,
            "audit": audit_stats,
            "events": event_stats,
            "cache": cache_stats,
        }

        cache.set(cache_key, result, 30)
        return result

    @staticmethod
    def get_metrics(
        metric_type: str = None,
        window: str = "1m",
        limit: int = 100,
        start_time: str = None,
        end_time: str = None
    ) -> List[Dict[str, Any]]:
        """Get telemetry metrics with time range filtering."""
        qs = TelemetryMetric.objects.filter(window=window)

        if metric_type:
            qs = qs.filter(metric_type=metric_type)

        if start_time:
            qs = qs.filter(created_at__gte=start_time)
        if end_time:
            qs = qs.filter(created_at__lte=end_time)

        metrics = qs.order_by("-created_at")[:limit]

        return [{
            "id": str(m.id),
            "metric_type": m.metric_type,
            "value": m.value,
            "unit": m.unit,
            "labels": m.labels,
            "window": m.window,
            "created_at": m.created_at.isoformat(),
        } for m in metrics]

    @staticmethod
    def get_audit_logs(
        entity_type: str = None,
        action: str = None,
        severity: str = None,
        user_id: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get paginated audit logs with filtering."""
        qs = AuditLog.objects.all()

        if entity_type:
            qs = qs.filter(entity_type=entity_type)
        if action:
            qs = qs.filter(action=action)
        if severity:
            qs = qs.filter(severity=severity)
        if user_id:
            qs = qs.filter(user_id=user_id)

        total = qs.count()
        logs = qs.order_by("-created_at")[offset:offset + limit]

        return {
            "items": [{
                "id": str(l.id),
                "entity_type": l.entity_type,
                "entity_id": str(l.entity_id),
                "action": l.action,
                "user_id": str(l.user_id) if l.user_id else None,
                "before_state": l.before_state,
                "after_state": l.after_state,
                "diff": l.diff,
                "severity": l.severity,
                "ip_address": str(l.ip_address) if l.ip_address else None,
                "hash": l.hash[:30] + "..." if l.hash else None,
                "previous_hash": l.previous_hash[:30] + "..." if l.previous_hash else None,
                "created_at": l.created_at.isoformat(),
            } for l in logs],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    @staticmethod
    def get_events(
        event_type: str = None,
        processed: bool = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get paginated events with filtering."""
        qs = EventLog.objects.all()

        if event_type:
            qs = qs.filter(event_type=event_type)
        if processed is not None:
            qs = qs.filter(processed=processed)

        total = qs.count()
        events = qs.order_by("-created_at")[offset:offset + limit]

        return {
            "items": [{
                "id": str(e.id),
                "type": e.event_type,
                "payload": e.payload,
                "processed": e.processed,
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
                "retry_count": e.retry_count,
                "error": e.error[:100] if e.error else None,
                "created_at": e.created_at.isoformat(),
            } for e in events],
            "total": total,
            "pending": qs.filter(processed=False).count(),
            "failed": qs.filter(processed=False, retry_count__gte=5).count(),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    @staticmethod
    def verify_audit_chain(entity_type: str = None) -> Dict[str, Any]:
        """Verify audit chain integrity."""
        valid, errors = AuditService.verify_chain(entity_type)

        return {
            "valid": valid,
            "errors": errors,
            "entity_type": entity_type,
            "checked_at": timezone.now().isoformat(),
            "total_checked": AuditLog.objects.filter(
                entity_type=entity_type
            ).count() if entity_type else AuditLog.objects.count(),
        }
