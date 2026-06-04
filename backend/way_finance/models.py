"""
WAY Finance Models - Unified: Credits + Wallets + Payments + Billing + Transfers
"""
import uuid
from decimal import Decimal
from django.db import models, transaction
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.conf import settings

from way_core.models import BaseModel


class Wallet(BaseModel):
    """User wallet with Ed25519 keys and encrypted backup."""
    user_id = models.UUIDField(db_index=True, unique=True)
    public_key = models.TextField()  # Ed25519 public key
    private_key_encrypted = models.TextField()  # AES-256 encrypted private key
    backup_encrypted = models.TextField(blank=True)  # Encrypted backup phrase
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    reserved = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="USD")
    is_active = models.BooleanField(default=True)
    frozen = models.BooleanField(default=False)
    frozen_reason = models.TextField(blank=True)
    frozen_at = models.DateTimeField(null=True, blank=True)
    last_transaction = models.DateTimeField(null=True, blank=True)
    nonce = models.BigIntegerField(default=0)  # For replay protection

    class Meta:
        indexes = [
            models.Index(fields=["user_id", "is_active"]),
            models.Index(fields=["frozen", "balance"]),
        ]

    def __str__(self):
        return f"Wallet({self.user_id})"

    @property
    def available(self):
        return self.balance - self.reserved

    def freeze(self, reason: str = ""):
        self.frozen = True
        self.frozen_reason = reason
        self.frozen_at = timezone.now()
        self.save(update_fields=["frozen", "frozen_reason", "frozen_at"])

    def unfreeze(self):
        self.frozen = False
        self.frozen_reason = ""
        self.frozen_at = None
        self.save(update_fields=["frozen", "frozen_reason", "frozen_at"])


class CreditReserve(BaseModel):
    """Reserve backing credits (1 USD = 100 WAY credits)."""
    total_reserve = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_credits_minted = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_credits_burned = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=3, default="USD")
    rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("100.00"))  # 1 USD = 100 credits
    last_audit = models.DateTimeField(null=True, blank=True)
    audit_hash = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["currency"], name="unique_reserve_currency")]


class CreditLedger(BaseModel):
    """Immutable credit ledger (append-only)."""
    TX_TYPES = [
        ("mint", "Mint"), ("burn", "Burn"), ("transfer", "Transfer"),
        ("deposit", "Deposit"), ("withdraw", "Withdraw"), ("fee", "Fee"),
        ("refund", "Refund"), ("skill_usage", "Skill Usage"),
    ]
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="ledger_entries")
    tx_type = models.CharField(max_length=20, choices=TX_TYPES, db_index=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    balance_after = models.DecimalField(max_digits=20, decimal_places=2)
    reference_id = models.UUIDField(null=True, blank=True, db_index=True)  # Payment or skill execution ID
    description = models.TextField(blank=True)
    signature = models.TextField(blank=True)  # Ed25519 signature of transaction
    nonce = models.BigIntegerField()
    previous_hash = models.CharField(max_length=255, blank=True)  # Blockchain-style chain
    current_hash = models.CharField(max_length=255, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["wallet", "tx_type", "created_at"]),
            models.Index(fields=["reference_id"]),
            models.Index(fields=["current_hash"]),
        ]

    def __str__(self):
        return f"{self.tx_type}:{self.amount} -> {self.wallet.user_id}"


class Payment(BaseModel):
    """Payment transactions (fiat and crypto)."""
    STATUS_CHOICES = [
        ("pending", "Pending"), ("processing", "Processing"), ("completed", "Completed"),
        ("failed", "Failed"), ("refunded", "Refunded"), ("cancelled", "Cancelled"),
    ]
    PROVIDERS = [
        ("stripe", "Stripe"), ("mpesa", "M-Pesa"), ("airtel", "Airtel Money"),
        ("orange", "Orange Money"), ("crypto", "Crypto"), ("bank", "Bank Transfer"),
    ]
    DIRECTIONS = [("deposit", "Deposit"), ("withdraw", "Withdraw")]

    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=20, choices=PROVIDERS, db_index=True)
    direction = models.CharField(max_length=10, choices=DIRECTIONS, db_index=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD")
    credits_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    provider_tx_id = models.CharField(max_length=255, blank=True, db_index=True)
    provider_data = models.JSONField(default=dict, blank=True)  # Webhook payload, raw response
    fee = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    metadata = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    webhook_received = models.BooleanField(default=False)
    webhook_data = models.JSONField(default=dict, blank=True)
    fraud_score = models.FloatField(default=0.0)  # 0-100
    fraud_flags = models.JSONField(default=list, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["wallet", "status", "created_at"]),
            models.Index(fields=["provider", "provider_tx_id"]),
            models.Index(fields=["fraud_score", "status"]),
        ]


class CreditTransfer(BaseModel):
    """User-to-user credit transfers."""
    STATUS_CHOICES = [
        ("pending", "Pending"), ("completed", "Completed"), ("failed", "Failed"), ("cancelled", "Cancelled"),
    ]
    from_wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="transfers_sent")
    to_wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="transfers_received")
    amount = models.DecimalField(max_digits=20, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    signature = models.TextField()  # Ed25519 signature
    nonce = models.BigIntegerField()
    description = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["from_wallet", "status"]),
            models.Index(fields=["to_wallet", "status"]),
        ]


class BillingReport(BaseModel):
    """Monthly billing reports."""
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="billing_reports")
    period_start = models.DateField()
    period_end = models.DateField()
    total_deposits = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_withdrawals = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_fees = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    total_skill_usage = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0.00"))
    provider_costs = models.JSONField(default=dict, blank=True)  # {openai: 10.50, anthropic: 5.20}
    report_data = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["wallet", "period_start"]]
        ordering = ["-period_start"]
