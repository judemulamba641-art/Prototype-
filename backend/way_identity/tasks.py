"""WAY Identity Tasks"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import structlog
from .models import RefreshToken, Device

logger = structlog.get_logger("way.identity.tasks")

@shared_task
def cleanup_sessions():
    """Clean expired refresh tokens."""
    expired = RefreshToken.objects.filter(expires_at__lt=timezone.now(), revoked=False)
    count = expired.update(revoked=True, revoked_at=timezone.now())
    logger.info("cleanup.expired_tokens", count=count)
    return count

@shared_task
def cleanup_inactive_devices():
    """Remove inactive devices."""
    stale = Device.objects.filter(
        last_used__lt=timezone.now() - timedelta(days=90),
        trust_level="untrusted"
    )
    count = stale.count()
    stale.delete()
    logger.info("cleanup.inactive_devices", count=count)
    return count
