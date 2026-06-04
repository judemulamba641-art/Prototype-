"""
WAY Core Services - Registry, Runtime, Sandbox, Health
"""
import time
import asyncio
from typing import Optional, Dict, Any, List
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
import structlog

from .models import RegistryEntry, RuntimeSession, HeartbeatLog, SystemConfig

logger = structlog.get_logger("way.core")


class RegistryService:
    """Global registry management."""

    @staticmethod
    def register(entity_type, entity_id, name, config=None, version="1.0.0"):
        entry, created = RegistryEntry.objects.update_or_create(
            entity_type=entity_type,
            entity_id=entity_id,
            defaults={"name": name, "config": config or {}, "version": version, "status": "active", "last_heartbeat": timezone.now()}
        )
        cache_key = f"registry:{entity_type}:{entity_id}"
        cache.set(cache_key, {"name": name, "status": "active", "version": version}, 300)
        logger.info("registry.registered", entity_type=entity_type, entity_id=entity_id, created=created)
        return entry

    @staticmethod
    def unregister(entity_type, entity_id):
        deleted, _ = RegistryEntry.objects.filter(entity_type=entity_type, entity_id=entity_id).delete()
        cache_key = f"registry:{entity_type}:{entity_id}"
        cache.delete(cache_key)
        logger.info("registry.unregistered", entity_type=entity_type, entity_id=entity_id)
        return deleted > 0

    @staticmethod
    def heartbeat(entity_type, entity_id, metrics=None):
        from uuid import UUID
        if isinstance(entity_id, str):
            entity_id = UUID(entity_id)
        try:
            entry = RegistryEntry.objects.get(entity_type=entity_type, entity_id=entity_id)
            entry.last_heartbeat = timezone.now()
            entry.health = metrics or {}
            entry.save(update_fields=["last_heartbeat", "health"])
            HeartbeatLog.objects.create(registry_entry=entry, metrics=metrics or {})
            cache_key = f"registry:{entity_type}:{entity_id}"
            cache.set(cache_key, {"name": entry.name, "status": entry.status, "health": metrics}, 300)
            return True
        except RegistryEntry.DoesNotExist:
            return False

    @staticmethod
    def get_status(entity_type, entity_id):
        from uuid import UUID
        if isinstance(entity_id, str):
            entity_id = UUID(entity_id)
        cache_key = f"registry:{entity_type}:{entity_id}"
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            entry = RegistryEntry.objects.get(entity_type=entity_type, entity_id=entity_id)
            data = {"name": entry.name, "status": entry.status, "health": entry.health, "version": entry.version}
            cache.set(cache_key, data, 300)
            return data
        except RegistryEntry.DoesNotExist:
            return None

    @staticmethod
    def list_by_type(entity_type: str, status: str = None) -> List[RegistryEntry]:
        qs = RegistryEntry.objects.filter(entity_type=entity_type)
        if status:
            qs = qs.filter(status=status)
        return list(qs)


class RuntimeService:
    """Skill runtime execution with sandboxing."""

    @staticmethod
    def create_session(user_id: str, skill_id: str, custom_config: Dict = None) -> RuntimeSession:
        config = settings.WAY_CONFIG["SANDBOX_TIMEOUT"]
        default_config = {
            "ram": settings.WAY_CONFIG["SANDBOX_RAM_MB"],
            "cpu": settings.WAY_CONFIG["SANDBOX_CPU_CORES"],
            "disk": settings.WAY_CONFIG["SANDBOX_DISK_MB"],
            "timeout": settings.WAY_CONFIG["SANDBOX_TIMEOUT"],
            "network": "restricted",
        }
        if custom_config:
            default_config.update(custom_config)

        session = RuntimeSession.objects.create(
            user_id=user_id,
            skill_id=skill_id,
            sandbox_config=default_config,
            status="pending",
        )
        logger.info("runtime.session_created", session_id=str(session.id), user_id=user_id, skill_id=skill_id)
        return session

    @staticmethod
    def start_session(session_id: str) -> bool:
        try:
            session = RuntimeSession.objects.get(id=session_id)
            session.status = "running"
            session.started_at = timezone.now()
            session.save(update_fields=["status", "started_at"])
            logger.info("runtime.session_started", session_id=session_id)
            return True
        except RuntimeSession.DoesNotExist:
            return False

    @staticmethod
    def complete_session(session_id: str, exit_code: int = 0, logs: str = "") -> bool:
        try:
            session = RuntimeSession.objects.get(id=session_id)
            session.status = "completed" if exit_code == 0 else "failed"
            session.ended_at = timezone.now()
            session.exit_code = exit_code
            session.logs = logs
            session.save(update_fields=["status", "ended_at", "exit_code", "logs"])
            logger.info("runtime.session_completed", session_id=session_id, exit_code=exit_code)
            return True
        except RuntimeSession.DoesNotExist:
            return False

    @staticmethod
    def kill_session(session_id: str, reason: str = "") -> bool:
        try:
            session = RuntimeSession.objects.get(id=session_id)
            session.status = "killed"
            session.ended_at = timezone.now()
            session.logs += f"\n[KILLED: {reason}]"
            session.save(update_fields=["status", "ended_at", "logs"])
            logger.warning("runtime.session_killed", session_id=session_id, reason=reason)
            return True
        except RuntimeSession.DoesNotExist:
            return False

    @staticmethod
    def enforce_sandbox(session: RuntimeSession) -> Dict[str, Any]:
        """Enforce sandbox limits. Returns enforcement actions taken."""
        config = session.sandbox_config
        actions = {}
        # Check timeout
        if session.started_at:
            elapsed = (timezone.now() - session.started_at).total_seconds()
            if elapsed > config.get("timeout", 15):
                RuntimeService.kill_session(str(session.id), "timeout exceeded")
                actions["timeout"] = True
        # Check resource usage (would be populated by actual monitoring)
        usage = session.resource_usage or {}
        if usage.get("ram_peak", 0) > config.get("ram", 256):
            actions["ram_limit"] = True
        if usage.get("cpu_peak", 0) > 100:
            actions["cpu_throttle"] = True
        return actions


class ConfigService:
    """Centralized configuration management."""

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        cache_key = f"config:{key}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            config = SystemConfig.objects.get(key=key)
            value = config.value
            cache.set(cache_key, value, 3600)
            return value
        except SystemConfig.DoesNotExist:
            return default

    @staticmethod
    def set(key: str, value: Any, encrypted: bool = False, description: str = "") -> SystemConfig:
        config, _ = SystemConfig.objects.update_or_create(
            key=key,
            defaults={"value": value, "encrypted": encrypted, "description": description}
        )
        cache_key = f"config:{key}"
        cache.set(cache_key, value, 3600)
        return config


class HealthService:
    """System health monitoring."""
    _start_time = time.time()

    @classmethod
    def check(cls) -> Dict[str, Any]:
        from django.db import connection
        from django.core.cache import cache
        import redis

        services = {}
        # Database
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                services["database"] = {"status": "healthy", "latency_ms": 0}
        except Exception as e:
            services["database"] = {"status": "unhealthy", "error": str(e)}

        # Cache
        try:
            cache.set("health_check", "ok", 5)
            services["cache"] = {"status": "healthy"}
        except Exception as e:
            services["cache"] = {"status": "unhealthy", "error": str(e)}

        # Redis
        try:
            r = redis.from_url(settings.REDIS_URL)
            r.ping()
            services["redis"] = {"status": "healthy"}
        except Exception as e:
            services["redis"] = {"status": "unhealthy", "error": str(e)}

        # Registry health
        stale = RegistryEntry.objects.filter(
            last_heartbeat__lt=timezone.now() - timezone.timedelta(minutes=5),
            status="active"
        ).count()
        services["registry"] = {"status": "healthy" if stale == 0 else "warning", "stale_count": stale}

        overall = "healthy" if all(s["status"] == "healthy" for s in services.values()) else "degraded"
        if any(s["status"] == "unhealthy" for s in services.values()):
            overall = "unhealthy"

        return {
            "status": overall,
            "version": "2.4.0",
            "uptime": time.time() - cls._start_time,
            "services": services,
            "timestamp": timezone.now().isoformat(),
        }
