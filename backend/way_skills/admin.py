"""WAY Skills Admin"""
from django.contrib import admin
from .models import Skill, Provider, SkillExecution, PricingRule, SkillInstall, MarketplaceReview

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ["name", "skill_type", "lifecycle", "version", "owner_id", "price_per_use", "is_public", "is_approved", "usage_count"]
    list_filter = ["skill_type", "lifecycle", "is_public", "is_approved"]
    search_fields = ["name", "description"]
    readonly_fields = ["code_hash", "usage_count", "rating_avg", "rating_count"]

@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ["name", "display_name", "status", "priority", "latency_ms", "success_rate", "quota_remaining"]
    list_filter = ["status"]
    list_editable = ["priority", "status"]

@admin.register(SkillExecution)
class ExecutionAdmin(admin.ModelAdmin):
    list_display = ["skill", "user_id", "provider", "status", "cost", "latency_ms", "cache_hit", "created_at"]
    list_filter = ["status", "cache_hit"]
    readonly_fields = ["duration_ms"]

@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "rule_type", "skill", "provider", "base_price", "multiplier", "is_active"]
    list_filter = ["rule_type", "is_active"]

@admin.register(SkillInstall)
class InstallAdmin(admin.ModelAdmin):
    list_display = ["user_id", "skill", "installed_at", "last_used", "usage_count", "is_active"]

@admin.register(MarketplaceReview)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["skill", "user_id", "rating", "is_verified"]
