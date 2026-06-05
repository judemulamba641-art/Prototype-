from rest_framework import serializers

from .models import (
    UserPreference,
    UserDashboardConfig,
    UserWidgetConfig,
    UserNotificationPreference,
    UserThemePreference,
)


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = "__all__"


class UserThemePreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserThemePreference
        fields = "__all__"


class UserNotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotificationPreference
        fields = "__all__"


class UserDashboardConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDashboardConfig
        fields = "__all__"


class UserWidgetConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserWidgetConfig
        fields = "__all__"
