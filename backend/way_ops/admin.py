"""WAY Operations Admin"""
from django.contrib import admin
from .models import Notification, AdminAction, CurrencyRate

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["user_id", "notification_type", "title", "read", "priority", "created_at"]
    list_filter = ["notification_type", "read", "priority"]

@admin.register(AdminAction)
class AdminActionAdmin(admin.ModelAdmin):
    list_display = ["admin_id", "action", "target_type", "target_id", "reverted", "created_at"]
    list_filter = ["action", "reverted"]

@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ["from_currency", "to_currency", "rate", "source", "last_updated"]
    list_editable = ["rate"]
