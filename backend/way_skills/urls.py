"""WAY Skills URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SkillViewSet, ProviderViewSet, ExecutionViewSet, InstallViewSet, ReviewViewSet, PricingViewSet

router = DefaultRouter()
router.register(r"skills", SkillViewSet, basename="skills")
router.register(r"providers", ProviderViewSet, basename="providers")
router.register(r"executions", ExecutionViewSet, basename="executions")
router.register(r"installs", InstallViewSet, basename="installs")
router.register(r"reviews", ReviewViewSet, basename="reviews")
router.register(r"pricing", PricingViewSet, basename="pricing")

urlpatterns = [
    path("", include(router.urls)),
]
