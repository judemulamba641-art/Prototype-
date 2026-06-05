"""
WAY User Marketplace Service - Enterprise Grade
Full integration with way_skills marketplace
"""
from typing import Dict, Any, List, Optional
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Avg, Count
import structlog

from way_skills.models import Skill, Provider, SkillExecution, MarketplaceReview
from way_skills.services import MarketplaceService as CoreMarketplaceService, ProviderRouter, PricingEngine
from way_finance.models import Wallet

logger = structlog.get_logger("way_user.marketplace")


class MarketplaceService:
    """Enterprise-grade marketplace aggregation service."""

    @staticmethod
    def list_skills(
        skill_type: str = None,
        search: str = None,
        sort_by: str = "rating",
        min_price: float = None,
        max_price: float = None,
        min_rating: float = None,
        tags: List[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Advanced marketplace listing with filtering and sorting."""
        cache_key = f"marketplace:v2:{skill_type}:{search}:{sort_by}:{min_price}:{max_price}:{min_rating}:{','.join(tags or [])}:{limit}:{offset}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        qs = CoreMarketplaceService.list_skills(
            skill_type=skill_type,
            approved_only=True,
            public_only=True
        )

        # Search
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(description__icontains=search)

        # Price filter
        if min_price is not None:
            qs = qs.filter(price_per_use__gte=min_price)
        if max_price is not None:
            qs = qs.filter(price_per_use__lte=max_price)

        # Rating filter
        if min_rating is not None:
            qs = qs.filter(rating_avg__gte=min_rating)

        # Tags filter
        if tags:
            for tag in tags:
                qs = qs.filter(tags__contains=[tag])

        # Sorting
        sort_options = {
            "rating": "-rating_avg",
            "usage": "-usage_count",
            "newest": "-created_at",
            "price_asc": "price_per_use",
            "price_desc": "-price_per_use",
            "name": "name",
        }
        qs = qs.order_by(sort_options.get(sort_by, "-rating_avg"))

        total = qs.count()
        skills = qs[offset:offset + limit]

        result = {
            "items": [{
                "id": str(s.id),
                "name": s.name,
                "description": s.description[:200] + "..." if len(s.description) > 200 else s.description,
                "skill_type": s.skill_type,
                "price_per_use": str(s.price_per_use),
                "currency": s.currency,
                "rating_avg": s.rating_avg,
                "rating_count": s.rating_count,
                "usage_count": s.usage_count,
                "tags": s.tags[:5],
                "owner_id": str(s.owner_id),
                "is_approved": s.is_approved,
                "version": s.version,
                "created_at": s.created_at.isoformat(),
            } for s in skills],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
            "filters": {
                "skill_type": skill_type,
                "search": search,
                "sort_by": sort_by,
                "min_price": min_price,
                "max_price": max_price,
                "min_rating": min_rating,
                "tags": tags,
            },
        }

        cache.set(cache_key, result, 60)
        return result

    @staticmethod
    def get_skill_reviews(skill_id: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """Get paginated reviews with stats."""
        reviews = MarketplaceReview.objects.filter(
            skill_id=skill_id
        ).select_related("skill").order_by("-created_at")

        total = reviews.count()
        items = reviews[offset:offset + limit]

        # Rating distribution
        distribution = reviews.values("rating").annotate(count=Count("id"))

        return {
            "items": [{
                "id": str(r.id),
                "user_id": str(r.user_id),
                "rating": r.rating,
                "review": r.review,
                "is_verified": r.is_verified,
                "created_at": r.created_at.isoformat(),
            } for r in items],
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total,
            "rating_distribution": {
                d["rating"]: d["count"] for d in distribution
            },
            "average_rating": reviews.aggregate(avg=Avg("rating"))["avg"] or 0,
        }

    @staticmethod
    def get_categories() -> List[Dict[str, Any]]:
        """Get skill categories with counts."""
        from way_skills.models import Skill

        categories = Skill.objects.filter(
            lifecycle="production", is_public=True
        ).values("skill_type").annotate(
            count=Count("id"),
            avg_price=Avg("price_per_use"),
            avg_rating=Avg("rating_avg"),
        ).order_by("-count")

        return [{
            "type": c["skill_type"],
            "count": c["count"],
            "avg_price": str(c["avg_price"] or 0),
            "avg_rating": c["avg_rating"] or 0,
            "skills": Skill.objects.filter(
                skill_type=c["skill_type"], lifecycle="production", is_public=True
            ).order_by("-rating_avg").values_list("name", flat=True)[:3],
        } for c in categories]

    @staticmethod
    def get_trending(limit: int = 10) -> List[Dict[str, Any]]:
        """Get trending skills with trend score."""
        from way_skills.models import Skill

        week_ago = timezone.now() - timezone.timedelta(days=7)

        skills = Skill.objects.filter(
            lifecycle="production", is_public=True
        ).order_by("-usage_count")[:limit]

        return [{
            "id": str(s.id),
            "name": s.name,
            "skill_type": s.skill_type,
            "usage_count": s.usage_count,
            "rating_avg": s.rating_avg,
            "rating_count": s.rating_count,
            "price_per_use": str(s.price_per_use),
            "trend_score": s.usage_count * (s.rating_avg or 1),  # Simple trend score
            "tags": s.tags[:3],
        } for s in skills]

    @staticmethod
    def get_featured(limit: int = 6) -> List[Dict[str, Any]]:
        """Get featured skills (high rating + high usage)."""
        skills = Skill.objects.filter(
            lifecycle="production", is_public=True,
            rating_avg__gte=4.0, usage_count__gte=10
        ).order_by("-rating_avg", "-usage_count")[:limit]

        return [{
            "id": str(s.id),
            "name": s.name,
            "description": s.description[:150] + "..." if len(s.description) > 150 else s.description,
            "skill_type": s.skill_type,
            "price_per_use": str(s.price_per_use),
            "rating_avg": s.rating_avg,
            "usage_count": s.usage_count,
            "tags": s.tags[:3],
        } for s in skills]
