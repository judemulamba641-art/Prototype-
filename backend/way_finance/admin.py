"""WAY Finance Admin"""
from django.contrib import admin
from .models import Wallet, CreditReserve, CreditLedger, Payment, CreditTransfer, BillingReport

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["user_id", "balance", "reserved", "available", "currency", "is_active", "frozen", "last_transaction"]
    list_filter = ["is_active", "frozen", "currency"]
    search_fields = ["user_id"]
    readonly_fields = ["balance", "reserved", "nonce"]

@admin.register(CreditReserve)
class CreditReserveAdmin(admin.ModelAdmin):
    list_display = ["currency", "total_reserve", "total_credits_minted", "total_credits_burned", "rate", "last_audit"]
    readonly_fields = ["total_credits_minted", "total_credits_burned"]

@admin.register(CreditLedger)
class CreditLedgerAdmin(admin.ModelAdmin):
    list_display = ["wallet", "tx_type", "amount", "balance_after", "nonce", "created_at"]
    list_filter = ["tx_type"]
    readonly_fields = ["current_hash", "previous_hash", "nonce"]
    search_fields = ["wallet__user_id"]

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["wallet", "provider", "direction", "amount", "status", "fraud_score", "processed_at"]
    list_filter = ["provider", "direction", "status"]
    readonly_fields = ["fraud_score", "fraud_flags"]

@admin.register(CreditTransfer)
class CreditTransferAdmin(admin.ModelAdmin):
    list_display = ["from_wallet", "to_wallet", "amount", "status", "processed_at"]
    list_filter = ["status"]

@admin.register(BillingReport)
class BillingReportAdmin(admin.ModelAdmin):
    list_display = ["wallet", "period_start", "period_end", "total_deposits", "total_withdrawals", "total_fees"]
