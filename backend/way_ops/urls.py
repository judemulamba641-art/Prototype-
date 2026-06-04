"""WAY Operations URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, AdminActionViewSet, CurrencyViewSet

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notifications")
router.register(r"admin-actions", AdminActionViewSet, basename="admin-actions")
router.register(r"currency", CurrencyViewSet, basename="currency")

urlpatterns = [
    path("", include(router.urls)),
]
