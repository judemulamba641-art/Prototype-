"""
WAY User Skill Service - Enterprise Grade
Full integration with way_skills backend
"""
from typing import Dict, Any, List, Optional
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count, Avg
import structlog

from way_skills.models import Skill, Provider, SkillExecution, PricingRule, SkillInstall, MarketplaceReview
from way_skills.services import SkillService as CoreSkillService, ProviderRouter, PricingEngine, ExecutionService, MarketplaceService
from way_finance.models import Wallet
from way_finance.services import CreditService
from way_infra.services import AuditService, EventBus

logger = structlog.get_logger("way_user.skills")


class SkillService:
    """Enterprise-grade skills aggregation service."""

    @staticmethod
    def get_user_skills(user_id: str) -> List[Dict[str, Any]]:
        """Get complete skills owned by user with stats."""
        skills = Skill.objects.filter(owner_id=user_id).select_related().order_by("-created_at")

        return [{
            "id": str(s.id),
            "name": s.name,
            "description": s.description,
            "skill_type": s.skill_type,
            "lifecycle": s.lifecycle,
            "version": s.version,
            "manifest": s.manifest,
            "code_hash": s.code_hash[:20] + "..." if s.code_hash else None,
            "price_per_use": str(s.price_per_use),
            "currency": s.currency,
            "is_public": s.is_public,
            "is_approved": s.is_approved,
            "approved_at": s.approved_at.isoformat() if s.approved_at else None,
            "approved_by": str(s.approved_by) if s.approved_by else None,
            "usage_count": s.usage_count,
            "rating_avg": s.rating_avg,
            "rating_count": s.rating_count,
            "tags": s.tags,
            "sandbox_config": s.sandbox_config,
            "required_permissions": s.required_permissions,
            "dependencies": s.dependencies,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        } for s in skills]

    @staticmethod
    def get_user_skills_summary(user_id: str) -> Dict[str, Any]:
        """Get skills summary with revenue."""
        skills = Skill.objects.filter(owner_id=user_id)
        skill_ids = [s.id for s in skills]

        # Revenue from executions
        executions = SkillExecution.objects.filter(
            skill_id__in=skill_ids, status="completed"
        )

        # Reviews
        reviews = MarketplaceReview.objects.filter(skill_id__in=skill_ids)

        # Installations
        installs = SkillInstall.objects.filter(skill_id__in=skill_ids)

        return {
            "total": skills.count(),
            "published": skills.filter(lifecycle="production").count(),
            "draft": skills.filter(lifecycle="draft").count(),
            "testing": skills.filter(lifecycle="testing").count(),
            "review": skills.filter(lifecycle="review").count(),
            "suspended": skills.filter(lifecycle="suspended").count(),
            "total_usage": sum(s.usage_count for s in skills),
            "total_revenue": str(sum(float(e.cost) for e in executions)),
            "avg_rating": sum(s.rating_avg for s in skills) / skills.count() if skills.count() > 0 else 0,
            "total_reviews": reviews.count(),
            "total_installs": installs.count(),
            "by_type": {
                skill_type: skills.filter(skill_type=skill_type).count()
                for skill_type in skills.values_list("skill_type", flat=True).distinct()
            },
        }

    @staticmethod
    def get_installed_skills(user_id: str) -> List[Dict[str, Any]]:
        """Get installed skills with full details."""
        installs = SkillInstall.objects.filter(
            user_id=user_id, is_active=True
        ).select_related("skill").order_by("-last_used")

        return [{
            "id": str(i.id),
            "skill_id": str(i.skill.id),
            "skill_name": i.skill.name,
            "skill_type": i.skill.skill_type,
            "skill_version": i.skill.version,
            "price_per_use": str(i.skill.price_per_use),
            "installed_at": i.installed_at.isoformat(),
            "last_used": i.last_used.isoformat() if i.last_used else None,
            "usage_count": i.usage_count,
            "config": i.config,
            "is_active": i.is_active,
        } for i in installs]

    @staticmethod
    def get_executions(user_id: str, limit: int = 20, status: str = None) -> Dict[str, Any]:
        """Get paginated executions with filtering."""
        qs = SkillExecution.objects.filter(user_id=user_id).select_related("skill", "provider")

        if status:
            qs = qs.filter(status=status)

        total = qs.count()
        executions = qs.order_by("-created_at")[:limit]

        return {
            "items": [{
                "id": str(e.id),
                "skill_id": str(e.skill.id) if e.skill else None,
                "skill_name": e.skill.name if e.skill else "Unknown",
                "provider_id": str(e.provider.id) if e.provider else None,
                "provider_name": e.provider.name if e.provider else "Unknown",
                "status": e.status,
                "input_data": e.input_data,
                "output_data": e.output_data,
                "cost": str(e.cost),
                "tokens_used": e.tokens_used,
                "latency_ms": e.latency_ms,
                "cache_hit": e.cache_hit,
                "sandbox_logs": e.sandbox_logs[:200] if e.sandbox_logs else None,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "duration_ms": e.duration_ms,
                "credit_charge_id": str(e.credit_charge_id) if e.credit_charge_id else None,
                "created_at": e.created_at.isoformat(),
            } for e in executions],
            "total": total,
            "limit": limit,
            "by_status": {
                "completed": qs.filter(status="completed").count(),
                "failed": qs.filter(status="failed").count(),
                "queued": qs.filter(status="queued").count(),
                "running": qs.filter(status="running").count(),
            },
        }

    @staticmethod
    def get_developer_stats(user_id: str) -> Dict[str, Any]:
        """Get comprehensive developer statistics."""
        skills = Skill.objects.filter(owner_id=user_id)
        skill_ids = [s.id for s in skills]

        # All executions for user's skills
        executions = SkillExecution.objects.filter(skill_id__in=skill_ids)
        completed = executions.filter(status="completed")

        # Revenue
        total_revenue = sum(float(e.cost) for e in completed)

        # Reviews
        reviews = MarketplaceReview.objects.filter(skill_id__in=skill_ids)

        # Daily usage
        today = timezone.now().date()
        daily_executions = completed.filter(created_at__date=today)

        # Provider breakdown
        provider_stats = completed.values("provider__name").annotate(
            count=Count("id"),
            revenue=Sum("cost"),
            avg_latency=Avg("latency_ms"),
        )

        return {
            "total_skills": skills.count(),
            "published": skills.filter(lifecycle="production").count(),
            "total_executions": executions.count(),
            "completed_executions": completed.count(),
            "failed_executions": executions.filter(status="failed").count(),
            "total_revenue": str(total_revenue),
            "daily_revenue": str(sum(float(e.cost) for e in daily_executions)),
            "daily_executions": daily_executions.count(),
            "avg_rating": sum(s.rating_avg for s in skills) / skills.count() if skills.count() > 0 else 0,
            "total_reviews": reviews.count(),
            "avg_review_rating": sum(r.rating for r in reviews) / reviews.count() if reviews.count() > 0 else 0,
            "provider_breakdown": [{
                "provider": p["provider__name"] or "Unknown",
                "executions": p["count"],
                "revenue": str(p["revenue"] or 0),
                "avg_latency_ms": p["avg_latency"] or 0,
            } for p in provider_stats],
            "top_skills": [{
                "id": str(s.id),
                "name": s.name,
                "usage_count": s.usage_count,
                "rating_avg": s.rating_avg,
                "revenue": str(sum(float(e.cost) for e in completed.filter(skill=s))),
            } for s in skills.order_by("-usage_count")[:5]],
        }

    @staticmethod
    def get_skill_detail(skill_id: str, user_id: str = None) -> Dict[str, Any]:
        """Get detailed skill information with execution history."""
        try:
            skill = Skill.objects.get(id=skill_id)
        except Skill.DoesNotExist:
            return {"error": "Skill not found", "code": "SKILL_NOT_FOUND"}

        # Execution history
        executions = SkillExecution.objects.filter(skill=skill).select_related("provider").order_by("-created_at")[:20]

        # Reviews
        reviews = MarketplaceReview.objects.filter(skill=skill).order_by("-created_at")[:10]

        # Pricing rules
        pricing_rules = PricingRule.objects.filter(skill=skill, is_active=True)

        # Install count
        install_count = SkillInstall.objects.filter(skill=skill, is_active=True).count()

        # Check if user has installed this skill
        user_install = None
        if user_id:
            try:
                install = SkillInstall.objects.get(skill=skill, user_id=user_id)
                user_install = {
                    "installed_at": install.installed_at.isoformat(),
                    "last_used": install.last_used.isoformat() if install.last_used else None,
                    "usage_count": install.usage_count,
                    "config": install.config,
                }
            except SkillInstall.DoesNotExist:
                pass

        # Cost estimate
        provider = ProviderRouter.select_provider(skill, prefer_cache=False)
        estimated_cost = PricingEngine.calculate_cost(skill, provider, tokens=1000) if provider else None

        return {
            "id": str(skill.id),
            "name": skill.name,
            "description": skill.description,
            "skill_type": skill.skill_type,
            "lifecycle": skill.lifecycle,
            "version": skill.version,
            "manifest": skill.manifest,
            "code_hash": skill.code_hash,
            "price_per_use": str(skill.price_per_use),
            "currency": skill.currency,
            "is_public": skill.is_public,
            "is_approved": skill.is_approved,
            "approved_at": skill.approved_at.isoformat() if skill.approved_at else None,
            "approved_by": str(skill.approved_by) if skill.approved_by else None,
            "usage_count": skill.usage_count,
            "rating_avg": skill.rating_avg,
            "rating_count": skill.rating_count,
            "tags": skill.tags,
            "sandbox_config": skill.sandbox_config,
            "required_permissions": skill.required_permissions,
            "dependencies": skill.dependencies,
            "owner_id": str(skill.owner_id),
            "install_count": install_count,
            "user_install": user_install,
            "estimated_cost": str(estimated_cost) if estimated_cost else None,
            "execution_history": [{
                "id": str(e.id),
                "user_id": str(e.user_id),
                "provider_name": e.provider.name if e.provider else "Unknown",
                "status": e.status,
                "cost": str(e.cost),
                "tokens_used": e.tokens_used,
                "latency_ms": e.latency_ms,
                "cache_hit": e.cache_hit,
                "created_at": e.created_at.isoformat(),
            } for e in executions],
            "reviews": [{
                "id": str(r.id),
                "user_id": str(r.user_id),
                "rating": r.rating,
                "review": r.review,
                "is_verified": r.is_verified,
                "created_at": r.created_at.isoformat(),
            } for r in reviews],
            "pricing_rules": [{
                "id": str(p.id),
                "name": p.name,
                "rule_type": p.rule_type,
                "base_price": str(p.base_price),
                "multiplier": p.multiplier,
                "conditions": p.conditions,
            } for p in pricing_rules],
            "created_at": skill.created_at.isoformat(),
            "updated_at": skill.updated_at.isoformat(),
        }
