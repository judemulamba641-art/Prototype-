"""
WAY User Runtime Service - Enterprise Grade
Full integration with way_core runtime
"""
from typing import Dict, Any, List
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import structlog

from way_core.models import RuntimeSession, RegistryEntry, SystemConfig
from way_core.services import RuntimeService as CoreRuntimeService, HealthService, RegistryService
from way_skills.models import Provider, SkillExecution
from way_skills.services import ProviderRouter

logger = structlog.get_logger("way_user.runtime")


class RuntimeService:
    """Enterprise-grade runtime aggregation service."""

    @staticmethod
    def get_active_sessions(user_id: str) -> List[Dict[str, Any]]:
        """Get active runtime sessions."""
        sessions = RuntimeSession.objects.filter(
            user_id=user_id,
            status__in=["pending", "running"]
        ).select_related("skill").order_by("-created_at")

        return [{
            "id": str(s.id),
            "skill_id": str(s.skill_id) if s.skill_id else None,
            "status": s.status,
            "sandbox_config": s.sandbox_config,
            "resource_usage": s.resource_usage,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "elapsed_seconds": (timezone.now() - s.started_at).total_seconds() if s.started_at and s.status == "running" else 0,
            "created_at": s.created_at.isoformat(),
        } for s in sessions]

    @staticmethod
    def get_session_history(user_id: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """Get paginated session history."""
        qs = RuntimeSession.objects.filter(user_id=user_id)
        total = qs.count()
        sessions = qs.order_by("-created_at")[offset:offset + limit]

        return {
            "items": [{
                "id": str(s.id),
                "skill_id": str(s.skill_id) if s.skill_id else None,
                "status": s.status,
                "exit_code": s.exit_code,
                "logs": s.logs[:500] if s.logs else "",
                "sandbox_config": s.sandbox_config,
                "resource_usage": s.resource_usage,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "duration_seconds": (s.ended_at - s.started_at).total_seconds() if s.ended_at and s.started_at else None,
                "created_at": s.created_at.isoformat(),
            } for s in sessions],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
        }

    @staticmethod
    def get_system_status() -> Dict[str, Any]:
        """Get comprehensive system status."""
        health = HealthService.check()
        providers = Provider.objects.all()

        # Runtime stats
        runtime_stats = {
            "running": RuntimeSession.objects.filter(status="running").count(),
            "pending": RuntimeSession.objects.filter(status="pending").count(),
            "completed_today": RuntimeSession.objects.filter(
                status="completed", ended_at__date=timezone.now().date()
            ).count(),
            "killed_today": RuntimeSession.objects.filter(
                status="killed", ended_at__date=timezone.now().date()
            ).count(),
        }

        # Execution stats
        execution_stats = {
            "queued": SkillExecution.objects.filter(status="queued").count(),
            "running": SkillExecution.objects.filter(status="running").count(),
            "completed_today": SkillExecution.objects.filter(
                status="completed", completed_at__date=timezone.now().date()
            ).count(),
            "failed_today": SkillExecution.objects.filter(
                status="failed", created_at__date=timezone.now().date()
            ).count(),
        }

        return {
            "overall": health.get("status", "unknown"),
            "version": health.get("version", "2.4.0"),
            "uptime_seconds": health.get("uptime", 0),
            "services": health.get("services", {}),
            "providers": {
                p.name: {
                    "status": p.status,
                    "latency_ms": p.latency_ms,
                    "success_rate": p.success_rate,
                    "quota_remaining": p.quota_remaining,
                    "quota_total": p.quota_total,
                    "models_available": p.models_available[:5],
                }
                for p in providers
            },
            "runtime": runtime_stats,
            "executions": execution_stats,
            "timestamp": timezone.now().isoformat(),
        }

    @staticmethod
    def get_sandbox_stats() -> Dict[str, Any]:
        """Get sandbox statistics."""
        sessions = RuntimeSession.objects.all()

        # Resource usage
        total_cpu = sum(
            (s.resource_usage or {}).get("cpu_peak", 0)
            for s in sessions.filter(status="completed")
        )
        total_ram = sum(
            (s.resource_usage or {}).get("ram_peak", 0)
            for s in sessions.filter(status="completed")
        )

        completed = sessions.filter(status="completed").count()

        return {
            "running": sessions.filter(status="running").count(),
            "completed": sessions.filter(status="completed").count(),
            "killed": sessions.filter(status="killed").count(),
            "failed": sessions.filter(status="failed").count(),
            "total": sessions.count(),
            "avg_cpu_peak": total_cpu / completed if completed > 0 else 0,
            "avg_ram_peak": total_ram / completed if completed > 0 else 0,
            "timeout_kills": sessions.filter(
                status="killed", logs__contains="timeout"
            ).count(),
            "resource_limit_kills": sessions.filter(
                status="killed", logs__contains="ram_limit"
            ).count(),
        }

    @staticmethod
    def get_registry_status() -> Dict[str, Any]:
        """Get registry status."""
        entries = RegistryEntry.objects.all()

        # Stale entries
        stale_threshold = timezone.now() - timedelta(minutes=10)
        stale = entries.filter(status="active", last_heartbeat__lt=stale_threshold)

        return {
            "total": entries.count(),
            "by_type": {
                entity_type: entries.filter(entity_type=entity_type).count()
                for entity_type in entries.values_list("entity_type", flat=True).distinct()
            },
            "active": entries.filter(status="active").count(),
            "inactive": entries.filter(status="inactive").count(),
            "stale": stale.count(),
            "health": {
                "healthy": entries.filter(status="active", last_heartbeat__gte=stale_threshold).count(),
                "warning": stale.count(),
            },
        }
