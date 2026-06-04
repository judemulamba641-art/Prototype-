"""WAY Infrastructure Permissions"""
from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """Admin can write, everyone can read."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class IsOwner(permissions.BasePermission):
    """Only owner can access."""
    def has_object_permission(self, request, view, obj):
        return hasattr(obj, "user_id") and str(obj.user_id) == str(request.user.id)


class IsOwnerOrAdmin(permissions.BasePermission):
    """Owner or admin can access."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if hasattr(obj, "owner_id"):
            return str(obj.owner_id) == str(request.user.id)
        if hasattr(obj, "user_id"):
            return str(obj.user_id) == str(request.user.id)
        return False


class IsSystem(permissions.BasePermission):
    """Only system/internal services."""
    def has_permission(self, request, view):
        return request.user and request.user.is_staff and request.META.get("HTTP_X_INTERNAL", "") == "way-internal"
