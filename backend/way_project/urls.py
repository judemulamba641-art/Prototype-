"""WAY URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from way_infra.views import HealthView, MetricsView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", HealthView.as_view(), name="health"),
    path("api/metrics/", MetricsView.as_view(), name="metrics"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/auth/", include("way_identity.urls")),
    path("api/core/", include("way_core.urls")),
    path("api/finance/", include("way_finance.urls")),
    path("api/skills/", include("way_skills.urls")),
    path("api/ops/", include("way_ops.urls")),
    path("api/infra/", include("way_infra.urls")),
]
