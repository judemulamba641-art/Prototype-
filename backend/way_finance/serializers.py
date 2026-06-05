"""WAY Finance Serializers"""
from decimal import Decimal
from rest_framework import serializers
from .models import Wallet, CreditReserve, CreditLedger, Payment, CreditTransfer, BillingReport


class WalletSerializer(serializers.ModelSerializer):
    available = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    class Meta:
        model = Wallet
        fields = ["id", "user_id", "public_key", "balance", "reserved", "available", "currency", "is_active", "frozen", "frozen_reason", "last_transaction", "created_at"]
        read_only_fields = ["id", "balance", "reserved", "available", "created_at"]


class WalletCreateSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    public_key = serializers.CharField(required=False, allow_blank=True)
    private_key_encrypted = serializers.CharField(required=False, allow_blank=True)


class CreditLedgerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditLedger
        fields = ["id", "tx_type", "amount", "balance_after", "reference_id", "description", "nonce", "current_hash", "created_at"]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "provider", "direction", "amount", "currency", "credits_amount", "status", "provider_tx_id", "fee", "fraud_score", "fraud_flags", "processed_at", "created_at"]
        read_only_fields = ["id", "status", "fraud_score", "fraud_flags", "processed_at", "created_at"]


class PaymentCreateSerializer(serializers.Serializer):
    wallet_id = serializers.UUIDField()
    provider = serializers.CharField()
    direction = serializers.CharField()
    amount = serializers.DecimalField(max_digits=20, decimal_places=2)
    currency = serializers.CharField(default="USD")


class CreditTransferSerializer(serializers.ModelSerializer):
    from_user = serializers.CharField(source="from_wallet.user_id", read_only=True)
    to_user = serializers.CharField(source="to_wallet.user_id", read_only=True)

    class Meta:
        model = CreditTransfer
        fields = ["id", "from_wallet", "to_wallet", "from_user", "to_user", "amount", "status", "signature", "description", "processed_at", "created_at"]
        read_only_fields = ["id", "status", "processed_at", "created_at"]


class TransferCreateSerializer(serializers.Serializer):
    from_wallet_id = serializers.UUIDField()
    to_wallet_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, min_value=Decimal("0.01"))
    signature = serializers.CharField()
    description = serializers.CharField(required=False, allow_blank=True)


class BillingReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingReport
        fields = ["id", "period_start", "period_end", "total_deposits", "total_withdrawals", "total_fees", "total_skill_usage", "provider_costs", "report_data", "generated_at"]


class ReserveSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditReserve
        fields = ["id", "currency", "total_reserve", "total_credits_minted", "total_credits_burned", "rate", "last_audit", "created_at"]
        read_only_fields = ["id", "created_at"]


class WebhookSerializer(serializers.Serializer):
    payment_id = serializers.UUIDField()
    provider = serializers.CharField()
    status = serializers.CharField()
    transaction_id = serializers.CharField(required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=20, decimal_places=2, required=False)
    error = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)
