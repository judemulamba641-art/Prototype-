"""WAY Skills Tasks"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import structlog
from .models import Provider, SkillExecution
from .services import ProviderRouter

logger = structlog.get_logger("way.skills.tasks")

@shared_task
def sync_providers():
    """Sync provider health and quotas."""
    providers = Provider.objects.filter(status__in=["active", "degraded"])
    for provider in providers:
        # In production: actual health check API call
        # Simulated: random health update
        import random
        latency = random.randint(50, 500)
        success = random.random() > 0.1
        ProviderRouter.update_provider_health(str(provider.id), latency, success)
    logger.info("providers.synced", count=providers.count())
    return providers.count()

@shared_task
def cleanup_stale_executions():
    """Kill stale executions."""
    stale = SkillExecution.objects.filter(
        status="running",
        started_at__lt=timezone.now() - timedelta(minutes=30)
    )
    count = stale.update(status="failed", error_message="Timeout: killed by scheduler", completed_at=timezone.now())
    logger.info("executions.cleaned", count=count)
    return count

@shared_task
def update_skill_stats():
    """Update skill usage statistics."""
    from django.db.models import Count, Avg
    from .models import Skill
    for skill in Skill.objects.filter(lifecycle="production"):
        executions = SkillExecution.objects.filter(skill=skill, status="completed")
        skill.usage_count = executions.count()
        avg_latency = executions.aggregate(Avg("latency_ms"))["latency_ms__avg"] or 0
        skill.metadata["avg_latency_ms"] = avg_latency
        skill.save(update_fields=["usage_count", "metadata"])
    logger.info("stats.updated")
