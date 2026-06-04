"""WAY Identity Admin"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Device, Permission, RefreshToken, Group, GroupMembership

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "username", "display_name", "is_active", "is_staff", "date_joined", "last_login"]
    list_filter = ["is_active", "is_staff", "two_factor_enabled", "date_joined"]
    search_fields = ["email", "username", "display_name"]
    fieldsets = [
        (None, {"fields": ["email", "username", "password"]}),
        ("Profile", {"fields": ["display_name", "avatar_url", "bio", "phone", "country"]}),
        ("Security", {"fields": ["is_active", "is_staff", "is_superuser", "two_factor_enabled", "locked_until"]}),
        ("Settings", {"fields": ["settings", "language", "timezone"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "username", "password1", "password2"]}),
    ]
    ordering = ["-date_joined"]

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ["user", "name", "device_type", "trust_level", "is_approved", "last_used"]
    list_filter = ["device_type", "trust_level", "is_approved"]
    search_fields = ["user__email", "name", "fingerprint"]

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ["user", "scope", "permission_type", "granted", "revoked", "expires_at"]
    list_filter = ["scope", "permission_type", "granted", "revoked"]
    search_fields = ["user__email"]

@admin.register(RefreshToken)
class RefreshTokenAdmin(admin.ModelAdmin):
    list_display = ["user", "revoked", "expires_at", "issued_at"]
    list_filter = ["revoked"]

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "created_at"]
    search_fields = ["name", "owner__email"]
