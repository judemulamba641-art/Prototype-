"""
WAY Skills Services - Skill Runtime, Provider Router, Pricing, Marketplace
"""
import hashlib
import json
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
import structlog
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import Skill, Provider, SkillExecution, PricingRule, SkillInstall, MarketplaceReview
from way_finance.services import CreditService
from way_infra.services import EventBus
from way_infra.services import CacheService

logger = structlog.get_logger("way.skills")


class SkillService:
    """Skill lifecycle management."""

    @staticmethod
    def create_skill(owner_id: str, name: str, skill_type: str, manifest: Dict, code: str = "", price: Decimal = Decimal("0")) -> Skill:
        code_hash = hashlib.sha256(code.encode()).hexdigest() if code else ""
        skill = Skill.objects.create(
            owner_id=owner_id,
            name=name,
            skill_type=skill_type,
            manifest=manifest,
            code=code,
            code_hash=code_hash,
            price_per_use=price,
            sandbox_config=manifest.get("sandbox", {}),
            required_permissions=manifest.get("permissions", []),
        )
        EventBus.publish("skill_created", {"skill_id": str(skill.id), "owner_id": owner_id, "name": name})
        return skill

    @staticmethod
    def install_skill(user_id: str, skill_id: str, config: Dict = None) -> SkillInstall:
        skill = Skill.objects.get(id=skill_id)
        install, _ = SkillInstall.objects.update_or_create(
            user_id=user_id,
            skill=skill,
            defaults={"config": config or {}, "is_active": True}
        )
        EventBus.publish("skill_installed", {"skill_id": str(skill_id), "user_id": user_id})
        return install

    @staticmethod
    def validate_manifest(manifest: Dict) -> Tuple[bool, List[str]]:
        """Validate skill manifest."""
        errors = []
        required = ["entrypoint", "runtime"]
        for field in required:
            if field not in manifest:
                errors.append(f"Missing required field: {field}")
        if "sandbox" in manifest:
            sandbox = manifest["sandbox"]
            if sandbox.get("ram", 0) > 1024:
                errors.append("RAM limit exceeds 1024MB")
            if sandbox.get("timeout", 0) > 60:
                errors.append("Timeout exceeds 60 seconds")
        return len(errors) == 0, errors

    @staticmethod
    def scan_malware(code: str) -> Tuple[bool, List[str]]:
        """Basic malware scan."""
        threats = []
        dangerous_patterns = [
            "os.system", "subprocess.call", "eval(", "exec(",
            "__import__", "import os", "import subprocess",
            "socket.socket", "urllib.request", "requests.get",
        ]
        for pattern in dangerous_patterns:
            if pattern in code:
                threats.append(f"Suspicious pattern: {pattern}")
        return len(threats) == 0, threats


class ProviderRouter:
    """AI provider routing with failover and load balancing."""

    @staticmethod
    def get_available_providers(capability: str = "completion") -> List[Provider]:
        cache_key = f"providers:{capability}"
        cached = cache.get(cache_key)
        if cached:
            return Provider.objects.filter(id__in=cached)

        from django.db import connection
        if connection.vendor == 'sqlite':
            # SQLite doesn't support JSONField contains
            providers = Provider.objects.filter(
                status="active",
                quota_remaining__gt=0,
            ).order_by("priority", "latency_ms")
        else:
            providers = Provider.objects.filter(
                status="active",
                capabilities__contains={capability: True},
                quota_remaining__gt=0,
            ).order_by("priority", "latency_ms")

        provider_ids = list(providers.values_list("id", flat=True))
        cache.set(cache_key, provider_ids, 60)
        return providers

    @staticmethod
    def select_provider(skill: Skill, input_data: Dict = None, prefer_cache: bool = True) -> Optional[Provider]:
        """Select best provider based on skill requirements and health."""
        capability = skill.skill_type if skill.skill_type in ["vision", "translation"] else "completion"
        providers = ProviderRouter.get_available_providers(capability)

        if not providers:
            # Try failover
            logger.warning("provider.no_available", skill_id=str(skill.id))
            return None

        # Check cache first
        if prefer_cache:
            cache_key = f"skill_cache:{skill.id}:{hashlib.sha256(json.dumps(input_data or {}, sort_keys=True).encode()).hexdigest()[:16]}"
            cached = CacheService.get(cache_key)
            if cached:
                return None  # Signal cache hit

        # Select based on pricing and latency
        best = None
        best_score = float("inf")
        for provider in providers:
            score = provider.latency_ms * 0.5 + float(provider.cost_per_1k_tokens) * 1000 * 0.5
            if score < best_score:
                best_score = score
                best = provider

        return best

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def call_provider(provider: Provider, endpoint: str, payload: Dict) -> Dict:
        """Call provider API with retry."""
        headers = {"Authorization": f"Bearer {provider.api_key_encrypted}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{provider.base_url}/{endpoint}", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def update_provider_health(provider_id: str, latency: int, success: bool, error: str = None):
        provider = Provider.objects.get(id=provider_id)
        provider.latency_ms = int((provider.latency_ms * 0.7) + (latency * 0.3))  # EWMA
        if success:
            provider.success_rate = min(100.0, provider.success_rate * 0.95 + 100 * 0.05)
        else:
            provider.success_rate = provider.success_rate * 0.9
            provider.health["last_error"] = error
            provider.health["error_count"] = provider.health.get("error_count", 0) + 1

        # Update status based on health
        if provider.success_rate < 50:
            provider.status = "down"
        elif provider.success_rate < 80:
            provider.status = "degraded"
        else:
            provider.status = "active"

        provider.save(update_fields=["latency_ms", "success_rate", "status", "health"])

        # Trigger failover if down
        if provider.status == "down" and provider.failover_target:
            EventBus.publish("provider_failover", {"from_provider": str(provider.id), "to_provider": str(provider.failover_target_id)})


class PricingEngine:
    """Dynamic pricing calculation."""

    @staticmethod
    def calculate_cost(skill, provider, tokens=0, cache_hit=False, compute_ms=0):
        """Calculate execution cost."""
        from decimal import Decimal
        if cache_hit:
            return Decimal("0.001")  # Minimal cache hit fee

        from decimal import Decimal
        cost = Decimal(str(skill.price_per_use))

        # Provider cost
        if tokens > 0:
            from decimal import Decimal
            cost += Decimal(str(tokens)) / 1000 * Decimal(str(provider.cost_per_1k_tokens))

        # Base request cost
        cost += Decimal(str(provider.cost_per_request))

        # Apply pricing rules
        from django.db import models
        rules = PricingRule.objects.filter(
            models.Q(skill=skill) | models.Q(skill=None),
            models.Q(provider=provider) | models.Q(provider=None),
            is_active=True,
        ).order_by("priority")

        for rule in rules:
            conditions = rule.conditions
            applies = True
            if "tokens" in conditions:
                t = conditions["tokens"]
                if tokens < t.get("min", 0) or tokens > t.get("max", float("inf")):
                    applies = False
            if "cache" in conditions and cache_hit != conditions["cache"]:
                applies = False
            if applies:
                cost = cost * Decimal(str(rule.multiplier)) + rule.base_price

        return cost.quantize(Decimal("0.000001"))

    @staticmethod
    def estimate_cost(skill_id: str, input_tokens: int = 0, output_tokens: int = 0) -> Dict:
        skill = Skill.objects.get(id=skill_id)
        provider = ProviderRouter.select_provider(skill, prefer_cache=False)
        if not provider:
            return {"error": "No provider available"}

        total_tokens = input_tokens + output_tokens
        cost = PricingEngine.calculate_cost(skill, provider, total_tokens)
        return {
            "skill_id": str(skill_id),
            "provider": provider.name,
            "estimated_tokens": total_tokens,
            "estimated_cost": str(cost),
            "currency": skill.currency,
        }


class ExecutionService:
    """Skill execution orchestration."""

    @staticmethod
    def queue_execution(user_id: str, skill_id: str, input_data: Dict) -> SkillExecution:
        skill = Skill.objects.get(id=skill_id)
        execution = SkillExecution.objects.create(
            user_id=user_id,
            skill=skill,
            input_data=input_data,
            status="queued",
        )
        EventBus.publish("execution_queued", {"execution_id": str(execution.id), "skill_id": str(skill_id), "user_id": user_id})
        return execution

    @staticmethod
    @transaction.atomic
    def execute_skill(execution_id: str) -> SkillExecution:
        execution = SkillExecution.objects.select_for_update().get(id=execution_id)
        if execution.status != "queued":
            return execution

        execution.status = "running"
        execution.started_at = timezone.now()
        execution.save(update_fields=["status", "started_at"])

        skill = execution.skill
        user_id = execution.user_id

        # Check permissions
        from way_identity.auth import PermissionService
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
            for perm in skill.required_permissions:
                if not PermissionService.check_permission(user, "skill", perm, str(skill.id)):
                    execution.status = "failed"
                    execution.error_message = f"Missing permission: {perm}"
                    execution.completed_at = timezone.now()
                    execution.save(update_fields=["status", "error_message", "completed_at"])
                    return execution
        except User.DoesNotExist:
            execution.status = "failed"
            execution.error_message = "User not found"
            execution.completed_at = timezone.now()
            execution.save(update_fields=["status", "error_message", "completed_at"])
            return execution

        # Check cache
        cache_key = f"skill_cache:{skill.id}:{hashlib.sha256(json.dumps(execution.input_data, sort_keys=True).encode()).hexdigest()[:16]}"
        cached_result = CacheService.get(cache_key)
        if cached_result:
            execution.status = "completed"
            execution.output_data = cached_result
            execution.cache_hit = True
            execution.completed_at = timezone.now()
            execution.latency_ms = 10
            execution.save(update_fields=["status", "output_data", "cache_hit", "completed_at", "latency_ms"])
            EventBus.publish("execution_completed", {"execution_id": str(execution.id), "cache_hit": True})
            return execution

        # Select provider
        provider = ProviderRouter.select_provider(skill, execution.input_data)
        if not provider:
            execution.status = "failed"
            execution.error_message = "No provider available"
            execution.completed_at = timezone.now()
            execution.save(update_fields=["status", "error_message", "completed_at"])
            return execution

        execution.provider = provider
        execution.save(update_fields=["provider"])

        # Calculate cost
        estimated_tokens = len(json.dumps(execution.input_data)) // 4  # Rough estimate
        cost = PricingEngine.calculate_cost(skill, provider, estimated_tokens)

        # Charge credits
        from way_finance.models import Wallet
        try:
            wallet = Wallet.objects.get(user_id=user_id)
            if wallet.available < cost:
                execution.status = "failed"
                execution.error_message = "Insufficient credits"
                execution.completed_at = timezone.now()
                execution.save(update_fields=["status", "error_message", "completed_at"])
                return execution

            ledger = CreditService.burn_credits(str(wallet.id), cost, f"Skill execution: {skill.name}")
            execution.credit_charge_id = ledger.id
        except Exception as e:
            execution.status = "failed"
            execution.error_message = f"Payment error: {str(e)}"
            execution.completed_at = timezone.now()
            execution.save(update_fields=["status", "error_message", "completed_at"])
            return execution

        # Call provider (async in production, sync for simplicity here)
        try:
            # Simulated provider call
            import asyncio
            # result = asyncio.run(ProviderRouter.call_provider(provider, "v1/completions", execution.input_data))
            result = {"output": "Simulated result", "tokens_used": estimated_tokens}

            execution.status = "completed"
            execution.output_data = result
            execution.tokens_used = result.get("tokens_used", estimated_tokens)
            execution.cost = cost
            execution.completed_at = timezone.now()
            execution.latency_ms = int((execution.completed_at - execution.started_at).total_seconds() * 1000)
            execution.save(update_fields=["status", "output_data", "tokens_used", "cost", "completed_at", "latency_ms"])

            # Cache result
            CacheService.set(cache_key, result, ttl=3600)

            # Update skill stats
            skill.usage_count += 1
            skill.save(update_fields=["usage_count"])

            EventBus.publish("execution_completed", {"execution_id": str(execution.id), "cost": str(cost)})

        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = timezone.now()
            execution.save(update_fields=["status", "error_message", "completed_at"])
            # Refund credits
            if execution.credit_charge_id:
                CreditService.mint_credits(str(wallet.id), cost, str(execution.credit_charge_id), "Refund: execution failed")
            EventBus.publish("execution_failed", {"execution_id": str(execution.id), "error": str(e)})

        return execution


class MarketplaceService:
    """Skill marketplace management."""

    @staticmethod
    def list_skills(skill_type: str = None, public_only: bool = True, approved_only: bool = True) -> List[Skill]:
        qs = Skill.objects.filter(deleted_at__isnull=True)
        if public_only:
            qs = qs.filter(is_public=True)
        if approved_only:
            qs = qs.filter(is_approved=True, lifecycle="production")
        if skill_type:
            qs = qs.filter(skill_type=skill_type)
        return qs.order_by("-rating_avg", "-usage_count")

    @staticmethod
    def add_review(skill_id: str, user_id: str, rating: int, review: str = "") -> MarketplaceReview:
        skill = Skill.objects.get(id=skill_id)
        rev, created = MarketplaceReview.objects.update_or_create(
            skill=skill,
            user_id=user_id,
            defaults={"rating": rating, "review": review}
        )
        # Update skill rating
        reviews = MarketplaceReview.objects.filter(skill=skill)
        avg = sum(r.rating for r in reviews) / reviews.count()
        skill.rating_avg = avg
        skill.rating_count = reviews.count()
        skill.save(update_fields=["rating_avg", "rating_count"])
        return rev
