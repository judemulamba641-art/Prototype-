from django.db import models


class UserPreference(models.Model):
    user_id = models.UUIDField()
    theme = models.CharField(max_length=50, default="light")
    accent_color = models.CharField(max_length=20, blank=True, null=True)
    font_size = models.CharField(max_length=10, blank=True, null=True)
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    profile_visible = models.BooleanField(default=True)
    activity_visible = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user_id"], name="unique_user_preference")
        ]


class UserThemePreference(models.Model):
    user_id = models.UUIDField()
    primary_color = models.CharField(max_length=20, default="#0d6efd")
    secondary_color = models.CharField(max_length=20, default="#6c757d")
    background_color = models.CharField(max_length=20, default="#ffffff")
    surface_color = models.CharField(max_length=20, default="#f8f9fa")
    text_color = models.CharField(max_length=20, default="#212529")
    border_radius = models.CharField(max_length=20, default="8px")
    font_family = models.CharField(max_length=100, default="Inter, sans-serif")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user_id"], name="unique_user_theme_preference")
        ]


class UserNotificationPreference(models.Model):
    CHANNEL_EMAIL = "email"
    CHANNEL_PUSH = "push"
    CHANNEL_SMS = "sms"

    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_PUSH, "Push"),
        (CHANNEL_SMS, "SMS"),
    ]

    user_id = models.UUIDField()
    notification_type = models.CharField(max_length=100)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default=CHANNEL_EMAIL)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "notification_type", "channel"],
                name="unique_user_notification_preference",
            )
        ]


class UserDashboardConfig(models.Model):
    user_id = models.UUIDField()
    dashboard_type = models.CharField(max_length=50)
    layout = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "dashboard_type"],
                name="unique_user_dashboard_config",
            )
        ]


class UserWidgetConfig(models.Model):
    user_id = models.UUIDField()
    widget_id = models.CharField(max_length=100)
    settings = models.JSONField(default=dict)
    visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user_id", "widget_id"],
                name="unique_user_widget_config",
            )
        ]
