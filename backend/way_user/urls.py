"""WAY User URLs - Enterprise Grade"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DashboardViewSet,
    ProfileViewSet,
    WalletViewSet,
    CreditsViewSet,
    SkillsViewSet,
    MarketplaceViewSet,
    NotificationsViewSet,
    RuntimeViewSet,
    MonitoringViewSet,
    ActivityViewSet,
    SearchViewSet,
    NavigationViewSet,
    AnalyticsViewSet,
)

router = DefaultRouter()

# Dashboard
router.register(r"dashboard", DashboardViewSet, basename="dashboard")
# GET /api/user/dashboard/me/?type=user
# GET /api/user/dashboard/developer/
# GET /api/user/dashboard/admin/
# GET /api/user/dashboard/ops/
# GET /api/user/dashboard/auditor/
# GET /api/user/dashboard/investor/
# POST /api/user/dashboard/save_layout/
# GET /api/user/dashboard/widgets/?type=user

# Profile
router.register(r"profile", ProfileViewSet, basename="profile")
# GET /api/user/profile/me/
# PATCH /api/user/profile/update_me/
# GET /api/user/profile/preferences/
# POST /api/user/profile/update_preferences/
# GET /api/user/profile/theme/
# POST /api/user/profile/update_theme/
# GET /api/user/profile/activity/?days=30
# GET /api/user/profile/security/
# GET /api/user/profile/devices/
# POST /api/user/profile/{device_id}/revoke_device/

# Wallet
router.register(r"wallet", WalletViewSet, basename="wallet")
# GET /api/user/wallet/me/
# GET /api/user/wallet/transactions/?limit=20&offset=0
# GET /api/user/wallet/payments/?limit=20&status=
# GET /api/user/wallet/transfers/?limit=20
# GET /api/user/wallet/billing/?year=2024&month=1

# Credits
router.register(r"credits", CreditsViewSet, basename="credits")
# GET /api/user/credits/me/
# GET /api/user/credits/ledger/?limit=50&offset=0&type=
# GET /api/user/credits/reserve/
# GET /api/user/credits/transfers/?limit=50

# Skills
router.register(r"skills", SkillsViewSet, basename="user-skills")
# GET /api/user/skills/me/
# GET /api/user/skills/summary/
# GET /api/user/skills/installed/
# GET /api/user/skills/executions/?limit=20&status=
# GET /api/user/skills/{id}/detail/
# GET /api/user/skills/developer_stats/

# Marketplace
router.register(r"marketplace", MarketplaceViewSet, basename="marketplace")
# GET /api/user/marketplace/skills/?search=&type=&sort_by=rating&min_price=&max_price=&min_rating=&tags=&limit=50&offset=0
# GET /api/user/marketplace/{id}/reviews/?limit=20&offset=0
# GET /api/user/marketplace/categories/
# GET /api/user/marketplace/trending/?limit=10
# GET /api/user/marketplace/featured/?limit=6

# Notifications
router.register(r"notifications", NotificationsViewSet, basename="user-notifications")
# GET /api/user/notifications/me/?unread=false&limit=50&offset=0&type=
# GET /api/user/notifications/unread_count/
# POST /api/user/notifications/mark_read/
# GET /api/user/notifications/preferences/
# POST /api/user/notifications/update_preference/
# GET /api/user/notifications/alerts/?limit=5

# Runtime
router.register(r"runtime", RuntimeViewSet, basename="runtime")
# GET /api/user/runtime/sessions/
# GET /api/user/runtime/history/?limit=50&offset=0
# GET /api/user/runtime/system/
# GET /api/user/runtime/sandbox/
# GET /api/user/runtime/registry/

# Monitoring
router.register(r"monitoring", MonitoringViewSet, basename="monitoring")
# GET /api/user/monitoring/dashboard/
# GET /api/user/monitoring/metrics/?type=&window=1m&limit=100&start_time=&end_time=
# GET /api/user/monitoring/audit/?entity_type=&action=&severity=&user_id=&limit=50&offset=0
# GET /api/user/monitoring/events/?type=&processed=&limit=50&offset=0
# GET /api/user/monitoring/verify_chain/?entity_type=

# Activity
router.register(r"activity", ActivityViewSet, basename="activity")
# GET /api/user/activity/me/?days=30
# GET /api/user/activity/search_history/?limit=20

# Search
router.register(r"search", SearchViewSet, basename="search")
# GET /api/user/search/all/?q=query

# Navigation
router.register(r"navigation", NavigationViewSet, basename="navigation")
# GET /api/user/navigation/me/

# Analytics
router.register(r"analytics", AnalyticsViewSet, basename="analytics")
# GET /api/user/analytics/global_stats/
# GET /api/user/analytics/user_growth/?days=30
# GET /api/user/analytics/revenue/?days=30

urlpatterns = [
    path("", include(router.urls)),
]
