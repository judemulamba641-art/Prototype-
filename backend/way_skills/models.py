"""
WAY Skills Models - Unified: Skills + Marketplace + Providers + Pricing + Router
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
from django.conf import settings

from way_core.models import BaseModel


class Skill(BaseModel):
    """Skill with embedded manifest, version, and permissions."""
    LIFECYCLE = [
        ("draft", "Draft"), ("testing", "Testing"), ("review", "Review"),
        ("production", "Production"), ("suspended", "Suspended"),
    ]
    SKILL_TYPES = [
        ("creation", "Creation"), ("style", "Style"), ("pay", "Pay"),
        ("vision", "Vision"), ("translation", "Translation"), ("custom", "Custom"),
    ]

    owner_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True)
    skill_type = models.CharField(max_length=20, choices=SKILL_TYPES, default="custom")
    lifecycle = models.CharField(max_length=20, choices=LIFECYCLE, default="draft", db_index=True)
    version = models.CharField(max_length=20, default="1.0.0")
    manifest = models.JSONField(default=dict)  # {entrypoint: "main.py", dependencies: [], permissions: [], sandbox: {}}
    code = models.TextField(blank=True)  # Skill code or URL to storage
    code_hash = models.CharField(max_length=255, blank=True)  # SHA-256 of code for integrity
    icon_url = models.URLField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    is_public = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.UUIDField(null=True, blank=True)
    price_per_use = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="USD")
    usage_count = models.PositiveIntegerField(default=0)
    rating_avg = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(5)])
    rating_count = models.PositiveIntegerField(default=0)
    sandbox_config = models.JSONField(default=dict)  # {ram: 256, cpu: 2, disk: 100, timeout: 15, network: "restricted"}
    required_permissions = models.JSONField(default=list, blank=True)  # ["camera", "storage"]
    dependencies = models.JSONField(default=list, blank=True)  # Other skill IDs

    class Meta:
        indexes = [
            models.Index(fields=["owner_id", "lifecycle"]),
            models.Index(fields=["skill_type", "is_public", "is_approved"]),
            models.Index(fields=["name", "lifecycle"]),
            models.Index(fields=["rating_avg", "usage_count"]),
        ]

    def __str__(self):
        return f"{self.name} v{self.version}"

    def approve(self, approver_id: str):
        self.is_approved = True
        self.approved_at = timezone.now()
        self.approved_by = approver_id
        self.lifecycle = "production"
        self.save(update_fields=["is_approved", "approved_at", "approved_by", "lifecycle"])

    def suspend(self):
        self.lifecycle = "suspended"
        self.save(update_fields=["lifecycle"])


class SkillInstall(BaseModel):
    """Skill installations by users."""
    user_id = models.UUIDField(db_index=True)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="installs")
    installed_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.PositiveIntegerField(default=0)
    config = models.JSONField(default=dict, blank=True)  # User-specific config
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = [["user_id", "skill"]]
        indexes = [models.Index(fields=["user_id", "is_active"])]


class Provider(BaseModel):
    """AI model providers with health and pricing."""
    STATUS_CHOICES = [
        ("active", "Active"), ("degraded", "Degraded"), ("down", "Down"), ("maintenance", "Maintenance"),
    ]
    PROVIDER_TYPES = [
        ("openai", "OpenAI"), ("anthropic", "Anthropic"), ("google", "Google"),
        ("deepseek", "DeepSeek"), ("glm", "GLM"), ("grok", "Grok"),
    ]

    name = models.CharField(max_length=50, choices=PROVIDER_TYPES, unique=True)
    display_name = models.CharField(max_length=100)
    api_key_encrypted = models.TextField(blank=True)
    base_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)
    priority = models.PositiveIntegerField(default=1)  # Lower = higher priority
    cost_per_1k_tokens = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal("0.00"))
    cost_per_request = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal("0.00"))
    latency_ms = models.PositiveIntegerField(default=0)
    success_rate = models.FloatField(default=100.0)
    quota_remaining = models.PositiveIntegerField(default=0)
    quota_total = models.PositiveIntegerField(default=0)
    health = models.JSONField(default=dict)  # {last_check: "", errors: []}
    models_available = models.JSONField(default=list)  # ["gpt-4", "gpt-3.5-turbo"]
    capabilities = models.JSONField(default=dict)  # {completion: true, vision: true, embedding: true, audio: true}
    failover_target = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["priority", "name"]

    def __str__(self):
        return self.display_name


class SkillExecution(BaseModel):
    """Skill execution records with provider routing."""
    STATUS_CHOICES = [
        ("queued", "Queued"), ("running", "Running"), ("completed", "Completed"),
        ("failed", "Failed"), ("cancelled", "Cancelled"),
    ]
    user_id = models.UUIDField(db_index=True)
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT, related_name="executions")
    provider = models.ForeignKey(Provider, on_delete=models.SET_NULL, null=True, blank=True, related_name="executions")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued", db_index=True)
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    tokens_used = models.PositiveIntegerField(default=0)
    cost = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0.00"))
    latency_ms = models.PositiveIntegerField(default=0)
    cache_hit = models.BooleanField(default=False)
    sandbox_logs = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    credit_charge_id = models.UUIDField(null=True, blank=True)  # Reference to ledger entry

    class Meta:
        indexes = [
            models.Index(fields=["user_id", "status", "created_at"]),
            models.Index(fields=["skill", "status"]),
            models.Index(fields=["provider", "status"]),
        ]

    @property
    def duration_ms(self):
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return None


class PricingRule(BaseModel):
    """Dynamic pricing rules."""
    RULE_TYPES = [
        ("provider_cost", "Provider Cost"), ("cache_hit", "Cache Hit"),
        ("compute", "Compute"), ("storage", "Storage"), ("bandwidth", "Bandwidth"),
    ]
    name = models.CharField(max_length=100)
    rule_type = models.CharField(max_length=20, choices=RULE_TYPES)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, null=True, blank=True, related_name="pricing_rules")
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, null=True, blank=True, related_name="pricing_rules")
    base_price = models.DecimalField(max_digits=20, decimal_places=6, default=Decimal("0.00"))
    multiplier = models.FloatField(default=1.0)
    conditions = models.JSONField(default=dict, blank=True)  # {tokens: {min: 0, max: 1000}, cache: true}
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["priority", "rule_type"]


class MarketplaceReview(BaseModel):
    """Skill marketplace reviews."""
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="reviews")
    user_id = models.UUIDField(db_index=True)
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)  # Verified purchase

    class Meta:
        unique_together = [["skill", "user_id"]]
