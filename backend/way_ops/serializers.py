"""WAY Operations Serializers"""
from rest_framework import serializers
from .models import Notification, AdminAction, CurrencyRate


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "notification_type", "title", "body", "payload", "read", "read_at", "sent_via", "priority", "created_at"]
        read_only_fields = ["id", "created_at"]


class AdminActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminAction
        fields = ["id", "admin_id", "action", "target_type", "target_id", "reason", "metadata", "reverted", "reverted_at", "created_at"]
        read_only_fields = ["id", "created_at"]


class CurrencyRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrencyRate
        fields = ["id", "from_currency", "to_currency", "rate", "source", "last_updated"]


class ConvertSerializer(serializers.Serializer):
    amount = serializers.FloatField()
    from_currency = serializers.CharField(max_length=3)
    to_currency = serializers.CharField(max_length=3)
