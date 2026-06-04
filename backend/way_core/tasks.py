"""WAY Core Celery Tasks"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import structlog

from .models import RuntimeSession, RegistryEntry
from .services import RuntimeService, HealthService

logger = structlog.get_logger("way.core.tasks")


@shared_task
def health_check():
    """Periodic health check."""
    health = HealthService.check()
    if health["status"] != "healthy":
        logger.warning("health.check_failed", health=health)
    return health


@shared_task
def cleanup_stale_sessions():
    """Kill stale runtime sessions."""
    stale = RuntimeSession.objects.filter(
        status="running",
        started_at__lt=timezone.now() - timedelta(minutes=30)
    )
    count = 0
    for session in stale:
        RuntimeService.kill_session(str(session.id), "stale cleanup")
        count += 1
    logger.info("cleanup.stale_sessions", count=count)
    return count


@shared_task
def cleanup_stale_registry():
    """Mark stale registry entries as inactive."""
    stale = RegistryEntry.objects.filter(
        status="active",
        last_heartbeat__lt=timezone.now() - timedelta(minutes=10)
    )
    count = stale.update(status="inactive")
    logger.info("cleanup.stale_registry", count=count)
    return count
