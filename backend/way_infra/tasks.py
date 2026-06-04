"""WAY Infrastructure Tasks"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import structlog
from .services import EventBus, BackupService, TelemetryService
from .models import EventLog, CacheMetadata

logger = structlog.get_logger("way.infra.tasks")

@shared_task
def process_events():
    """Process pending events."""
    count = EventBus.process_events(batch_size=500)
    logger.info("events.processed", count=count)
    return count

@shared_task
def cleanup_old_events():
    """Archive old events."""
    old = EventLog.objects.filter(created_at__lt=timezone.now() - timedelta(days=30), processed=True)
    count = old.count()
    old.delete()
    logger.info("events.cleaned", count=count)
    return count

@shared_task
def cleanup_stale_cache():
    """Remove stale cache metadata."""
    stale = CacheMetadata.objects.filter(last_accessed__lt=timezone.now() - timedelta(days=7))
    count = stale.count()
    stale.delete()
    logger.info("cache.cleaned", count=count)
    return count

@shared_task
def collect_system_metrics():
    """Collect system metrics."""
    import psutil
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    TelemetryService.record("cpu", cpu, "%")
    TelemetryService.record("ram", ram, "%")
    TelemetryService.record("disk", disk, "%")
    logger.info("metrics.collected", cpu=cpu, ram=ram, disk=disk)
    return {"cpu": cpu, "ram": ram, "disk": disk}

@shared_task
def daily_backup():
    """Run daily backups."""
    for backup_type in ["postgres", "redis", "wallets", "audit"]:
        BackupService.create_backup(backup_type)
    logger.info("backup.daily_completed")
    return True
