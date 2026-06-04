"""WAY Skills Serializers"""
from rest_framework import serializers
from .models import Skill, Provider, SkillExecution, PricingRule, SkillInstall, MarketplaceReview


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "owner_id", "name", "description", "skill_type", "lifecycle", "version", "manifest", "price_per_use", "currency", "is_public", "is_approved", "rating_avg", "rating_count", "usage_count", "sandbox_config", "required_permissions", "created_at"]
        read_only_fields = ["id", "code_hash", "usage_count", "rating_avg", "rating_count", "created_at"]


class SkillCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    skill_type = serializers.CharField(default="custom")
    manifest = serializers.JSONField()
    code = serializers.CharField(required=False, allow_blank=True)
    price_per_use = serializers.DecimalField(max_digits=20, decimal_places=2, default=0)
    is_public = serializers.BooleanField(default=False)


class SkillInstallSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source="skill.name", read_only=True)

    class Meta:
        model = SkillInstall
        fields = ["id", "skill", "skill_name", "installed_at", "last_used", "usage_count", "config", "is_active"]


class ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Provider
        fields = ["id", "name", "display_name", "status", "priority", "cost_per_1k_tokens", "cost_per_request", "latency_ms", "success_rate", "quota_remaining", "capabilities", "models_available"]
        read_only_fields = ["id", "latency_ms", "success_rate"]


class SkillExecutionSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source="skill.name", read_only=True)
    provider_name = serializers.CharField(source="provider.name", read_only=True)
    duration_ms = serializers.IntegerField(read_only=True)

    class Meta:
        model = SkillExecution
        fields = ["id", "skill", "skill_name", "provider", "provider_name", "status", "input_data", "output_data", "error_message", "tokens_used", "cost", "latency_ms", "duration_ms", "cache_hit", "started_at", "completed_at", "created_at"]
        read_only_fields = ["id", "output_data", "error_message", "tokens_used", "cost", "latency_ms", "started_at", "completed_at", "created_at"]


class ExecutionCreateSerializer(serializers.Serializer):
    skill_id = serializers.UUIDField()
    input_data = serializers.JSONField(default=dict)


class PricingRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricingRule
        fields = ["id", "name", "rule_type", "skill", "provider", "base_price", "multiplier", "conditions", "is_active", "priority"]


class MarketplaceReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketplaceReview
        fields = ["id", "skill", "user_id", "rating", "review", "is_verified", "created_at"]
        read_only_fields = ["id", "is_verified", "created_at"]


class CostEstimateSerializer(serializers.Serializer):
    skill_id = serializers.UUIDField()
    input_tokens = serializers.IntegerField(default=0)
    output_tokens = serializers.IntegerField(default=0)


class ManifestValidationSerializer(serializers.Serializer):
    manifest = serializers.JSONField()
