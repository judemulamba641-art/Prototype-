"""WAY User Views - Enterprise Grade"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.core.cache import cache
from django.utils import timezone
import structlog

from .models import (
    UserPreference,
    UserDashboardConfig,
    UserWidgetConfig,
    UserNotificationPreference,
    UserThemePreference,
)
from .serializers import (
    UserPreferenceSerializer,
    UserDashboardConfigSerializer,
    UserWidgetConfigSerializer,
    UserNotificationPreferenceSerializer,
    UserThemePreferenceSerializer,
)
from .services import (
    DashboardService,
    ProfileService,
    WalletService,
    CreditsService,
    SkillService,
    MarketplaceService,
    NotificationService,
    RuntimeService,
    MonitoringService,
    AnalyticsService,
)
from .navigation.navigation import NavigationConfig

logger = structlog.get_logger("way_user.views")


class DashboardViewSet(viewsets.ViewSet):
    """Dashboard aggregation endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user dashboard."""
        dashboard_type = request.query_params.get("type", "user")
        data = DashboardService.get_dashboard(str(request.user.id), dashboard_type)
        return Response(data)

    @action(detail=False, methods=["get"])
    def developer(self, request):
        """Get developer dashboard."""
        data = DashboardService.get_dashboard(str(request.user.id), "developer")
        return Response(data)

    @action(detail=False, methods=["get"])
    def admin(self, request):
        """Get admin dashboard."""
        if not request.user.is_staff:
            return Response({"error": "Admin only"}, status=status.HTTP_403_FORBIDDEN)
        data = DashboardService.get_dashboard(str(request.user.id), "admin")
        return Response(data)

    @action(detail=False, methods=["get"])
    def ops(self, request):
        """Get ops dashboard."""
        if not request.user.is_staff:
            return Response({"error": "Admin only"}, status=status.HTTP_403_FORBIDDEN)
        data = DashboardService.get_dashboard(str(request.user.id), "ops")
        return Response(data)

    @action(detail=False, methods=["get"])
    def auditor(self, request):
        """Get auditor dashboard."""
        data = DashboardService.get_dashboard(str(request.user.id), "auditor")
        return Response(data)

    @action(detail=False, methods=["get"])
    def investor(self, request):
        """Get investor dashboard."""
        data = DashboardService.get_dashboard(str(request.user.id), "investor")
        return Response(data)

    @action(detail=False, methods=["post"])
    def save_layout(self, request):
        """Save dashboard layout."""
        dashboard_type = request.data.get("type", "user")
        layout = request.data.get("layout", {})
        result = DashboardService.save_layout(
            str(request.user.id), dashboard_type, layout
        )
        return Response(result)

    @action(detail=False, methods=["get"])
    def widgets(self, request):
        """Get available widgets for dashboard type."""
        dashboard_type = request.query_params.get("type", "user")
        widgets = DashboardService._get_widgets_for_type(dashboard_type, str(request.user.id))
        return Response({"widgets": widgets})


class ProfileViewSet(viewsets.ViewSet):
    """User profile endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user profile."""
        data = ProfileService.get_profile(str(request.user.id))
        return Response(data)

    @action(detail=False, methods=["patch"])
    def update_me(self, request):
        """Update current user profile."""
        result = ProfileService.update_profile(str(request.user.id), request.data)
        return Response(result)

    @action(detail=False, methods=["get"])
    def preferences(self, request):
        """Get user preferences."""
        try:
            prefs = UserPreference.objects.get(user_id=request.user.id)
            return Response(UserPreferenceSerializer(prefs).data)
        except UserPreference.DoesNotExist:
            return Response({})

    @action(detail=False, methods=["post"])
    def update_preferences(self, request):
        """Update user preferences."""
        prefs, _ = UserPreference.objects.update_or_create(
            user_id=request.user.id,
            defaults=request.data
        )
        return Response(UserPreferenceSerializer(prefs).data)

    @action(detail=False, methods=["get"])
    def theme(self, request):
        """Get user theme."""
        try:
            theme = UserThemePreference.objects.get(user_id=request.user.id)
            return Response(UserThemePreferenceSerializer(theme).data)
        except UserThemePreference.DoesNotExist:
            return Response({})

    @action(detail=False, methods=["post"])
    def update_theme(self, request):
        """Update user theme."""
        theme, _ = UserThemePreference.objects.update_or_create(
            user_id=request.user.id,
            defaults=request.data
        )
        return Response(UserThemePreferenceSerializer(theme).data)

    @action(detail=False, methods=["get"])
    def activity(self, request):
        """Get user activity."""
        days = int(request.query_params.get("days", 30))
        data = ProfileService.get_activity(str(request.user.id), days)
        return Response(data)

    @action(detail=False, methods=["get"])
    def security(self, request):
        """Get security settings."""
        data = ProfileService.get_security_settings(str(request.user.id))
        return Response(data)

    @action(detail=False, methods=["get"])
    def devices(self, request):
        """Get user devices."""
        data = ProfileService.get_devices(str(request.user.id))
        return Response(data)

    @action(detail=True, methods=["post"])
    def revoke_device(self, request, pk=None):
        """Revoke a device."""
        result = ProfileService.revoke_device(str(request.user.id), pk)
        return Response(result)


class WalletViewSet(viewsets.ViewSet):
    """Wallet aggregation endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user wallet."""
        data = WalletService.get_wallet(str(request.user.id))
        return Response(data)

    @action(detail=False, methods=["get"])
    def transactions(self, request):
        """Get wallet transactions."""
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
        data = WalletService.get_transactions(str(request.user.id), limit, offset)
        return Response(data)

    @action(detail=False, methods=["get"])
    def payments(self, request):
        """Get payment history."""
        limit = int(request.query_params.get("limit", 20))
        status = request.query_params.get("status")
        data = WalletService.get_payments(str(request.user.id), limit, status)
        return Response(data)

    @action(detail=False, methods=["get"])
    def transfers(self, request):
        """Get credit transfers."""
        limit = int(request.query_params.get("limit", 20))
        data = WalletService.get_transfers(str(request.user.id), limit)
        return Response(data)

    @action(detail=False, methods=["get"])
    def billing(self, request):
        """Get billing reports."""
        year = request.query_params.get("year")
        month = request.query_params.get("month")
        data = WalletService.get_billing_reports(
            str(request.user.id),
            int(year) if year else None,
            int(month) if month else None
        )
        return Response(data)


class CreditsViewSet(viewsets.ViewSet):
    """Credits aggregation endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get credits summary."""
        data = CreditsService.get_credits_summary(str(request.user.id))
        return Response(data)

    @action(detail=False, methods=["get"])
    def ledger(self, request):
        """Get credit ledger."""
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))
        tx_type = request.query_params.get("type")
        data = CreditsService.get_ledger(str(request.user.id), limit, offset, tx_type)
        return Response(data)

    @action(detail=False, methods=["get"])
    def reserve(self, request):
        """Get reserve status."""
        data = CreditsService.get_reserve_status()
        return Response(data)

    @action(detail=False, methods=["get"])
    def transfers(self, request):
        """Get transfer history."""
        limit = int(request.query_params.get("limit", 50))
        data = CreditsService.get_transfer_history(str(request.user.id), limit)
        return Response(data)


class SkillsViewSet(viewsets.ViewSet):
    """Skills aggregation endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get user skills."""
        data = SkillService.get_user_skills(str(request.user.id))
        return Response(data)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get skills summary."""
        data = SkillService.get_user_skills_summary(str(request.user.id))
        return Response(data)

    @action(detail=False, methods=["get"])
    def installed(self, request):
        """Get installed skills."""
        data = SkillService.get_installed_skills(str(request.user.id))
        return Response(data)

    @action(detail=False, methods=["get"])
    def executions(self, request):
        """Get execution history."""
        limit = int(request.query_params.get("limit", 20))
        status = request.query_params.get("status")
        data = SkillService.get_executions(str(request.user.id), limit, status)
        return Response(data)

    @action(detail=True, methods=["get"])
    def detail(self, request, pk=None):
        """Get skill detail."""
        data = SkillService.get_skill_detail(pk, str(request.user.id))
        return Response(data)

    @action(detail=False, methods=["get"])
    def developer_stats(self, request):
        """Get developer stats."""
        data = SkillService.get_developer_stats(str(request.user.id))
        return Response(data)


class MarketplaceViewSet(viewsets.ViewSet):
    """Marketplace aggregation endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def skills(self, request):
        """List marketplace skills."""
        skill_type = request.query_params.get("type")
        search = request.query_params.get("search")
        sort_by = request.query_params.get("sort_by", "rating")
        min_price = float(request.query_params.get("min_price")) if request.query_params.get("min_price") else None
        max_price = float(request.query_params.get("max_price")) if request.query_params.get("max_price") else None
        min_rating = float(request.query_params.get("min_rating")) if request.query_params.get("min_rating") else None
        tags = request.query_params.get("tags", "").split(",") if request.query_params.get("tags") else None
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))

        data = MarketplaceService.list_skills(
            skill_type, search, sort_by, min_price, max_price, min_rating, tags, limit, offset
        )
        return Response(data)

    @action(detail=True, methods=["get"])
    def reviews(self, request, pk=None):
        """Get skill reviews."""
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
        data = MarketplaceService.get_skill_reviews(pk, limit, offset)
        return Response(data)

    @action(detail=False, methods=["get"])
    def categories(self, request):
        """Get skill categories."""
        data = MarketplaceService.get_categories()
        return Response(data)

    @action(detail=False, methods=["get"])
    def trending(self, request):
        """Get trending skills."""
        limit = int(request.query_params.get("limit", 10))
        data = MarketplaceService.get_trending(limit)
        return Response(data)

    @action(detail=False, methods=["get"])
    def featured(self, request):
        """Get featured skills."""
        limit = int(request.query_params.get("limit", 6))
        data = MarketplaceService.get_featured(limit)
        return Response(data)


class NotificationsViewSet(viewsets.ViewSet):
    """Notifications aggregation endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get user notifications."""
        unread_only = request.query_params.get("unread", "false").lower() == "true"
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))
        notification_type = request.query_params.get("type")

        data = NotificationService.get_notifications(
            str(request.user.id), unread_only, limit, offset, notification_type
        )
        return Response(data)

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Get unread notification count."""
        count = NotificationService.get_unread_count(str(request.user.id))
        return Response({"count": count})

    @action(detail=False, methods=["post"])
    def mark_read(self, request):
        """Mark notifications as read."""
        notification_id = request.data.get("notification_id")
        success = NotificationService.mark_read(str(request.user.id), notification_id)
        return Response({"success": success})

    @action(detail=False, methods=["get"])
    def preferences(self, request):
        """Get notification preferences."""
        data = NotificationService.get_preferences(str(request.user.id))
        return Response(data)

    @action(detail=False, methods=["post"])
    def update_preference(self, request):
        """Update notification preference."""
        notification_type = request.data.get("notification_type")
        channel = request.data.get("channel")
        enabled = request.data.get("enabled", True)

        success = NotificationService.update_preference(
            str(request.user.id), notification_type, channel, enabled
        )
        return Response({"success": success})

    @action(detail=False, methods=["get"])
    def alerts(self, request):
        """Get recent high-priority alerts."""
        limit = int(request.query_params.get("limit", 5))
        data = NotificationService.get_recent_alerts(str(request.user.id), limit)
        return Response(data)


class RuntimeViewSet(viewsets.ViewSet):
    """Runtime aggregation endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def sessions(self, request):
        """Get active sessions."""
        data = RuntimeService.get_active_sessions(str(request.user.id))
        return Response(data)

    @action(detail=False, methods=["get"])
    def history(self, request):
        """Get session history."""
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))
        data = RuntimeService.get_session_history(str(request.user.id), limit, offset)
        return Response(data)

    @action(detail=False, methods=["get"])
    def system(self, request):
        """Get system status."""
        data = RuntimeService.get_system_status()
        return Response(data)

    @action(detail=False, methods=["get"])
    def sandbox(self, request):
        """Get sandbox stats."""
        data = RuntimeService.get_sandbox_stats()
        return Response(data)

    @action(detail=False, methods=["get"])
    def registry(self, request):
        """Get registry status."""
        data = RuntimeService.get_registry_status()
        return Response(data)


class MonitoringViewSet(viewsets.ViewSet):
    """Monitoring aggregation endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def dashboard(self, request):
        """Get monitoring dashboard."""
        if not request.user.is_staff:
            return Response({"error": "Admin only"}, status=status.HTTP_403_FORBIDDEN)
        data = MonitoringService.get_dashboard_data()
        return Response(data)

    @action(detail=False, methods=["get"])
    def metrics(self, request):
        """Get telemetry metrics."""
        if not request.user.is_staff:
            return Response({"error": "Admin only"}, status=status.HTTP_403_FORBIDDEN)

        metric_type = request.query_params.get("type")
        window = request.query_params.get("window", "1m")
        limit = int(request.query_params.get("limit", 100))
        start_time = request.query_params.get("start_time")
        end_time = request.query_params.get("end_time")

        data = MonitoringService.get_metrics(metric_type, window, limit, start_time, end_time)
        return Response(data)

    @action(detail=False, methods=["get"])
    def audit(self, request):
        """Get audit logs."""
        if not request.user.is_staff:
            return Response({"error": "Admin only"}, status=status.HTTP_403_FORBIDDEN)

        entity_type = request.query_params.get("entity_type")
        action = request.query_params.get("action")
        severity = request.query_params.get("severity")
        user_id = request.query_params.get("user_id")
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))

        data = MonitoringService.get_audit_logs(
            entity_type, action, severity, user_id, limit, offset
        )
        return Response(data)

    @action(detail=False, methods=["get"])
    def events(self, request):
        """Get events."""
        if not request.user.is_staff:
            return Response({"error": "Admin only"}, status=status.HTTP_403_FORBIDDEN)

        event_type = request.query_params.get("type")
        processed = request.query_params.get("processed")
        if processed is not None:
            processed = processed.lower() == "true"
        limit = int(request.query_params.get("limit", 50))
        offset = int(request.query_params.get("offset", 0))

        data = MonitoringService.get_events(event_type, processed, limit, offset)
        return Response(data)

    @action(detail=False, methods=["get"])
    def verify_chain(self, request):
        """Verify audit chain."""
        if not request.user.is_staff:
            return Response({"error": "Admin only"}, status=status.HTTP_403_FORBIDDEN)

        entity_type = request.query_params.get("entity_type")
        data = MonitoringService.verify_audit_chain(entity_type)
        return Response(data)


class ActivityViewSet(viewsets.ViewSet):
    """User activity endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get user activity."""
        days = int(request.query_params.get("days", 30))
        data = AnalyticsService.get_user_activity(str(request.user.id), days)
        return Response(data)

    @action(detail=False, methods=["get"])
    def search_history(self, request):
        """Get search history."""
        limit = int(request.query_params.get("limit", 20))
        data = AnalyticsService.get_search_history(str(request.user.id), limit)
        return Response(data)


class SearchViewSet(viewsets.ViewSet):
    """Unified search endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def all(self, request):
        """Unified search across all entities."""
        query = request.query_params.get("q", "")
        if not query or len(query) < 2:
            return Response({"results": [], "total": 0, "query": query})

        results = []

        # Search skills
        skills = MarketplaceService.list_skills(search=query, limit=10)
        for s in skills.get("items", []):
            results.append({
                "type": "skill",
                "id": s["id"],
                "title": s["name"],
                "subtitle": s["description"][:100] if s.get("description") else "",
                "meta": f"{s['skill_type']} - {s['price_per_use']} {s['currency']}",
            })

        # Search marketplace
        marketplace = MarketplaceService.list_skills(search=query, limit=10)
        for m in marketplace.get("items", []):
            if not any(r["id"] == m["id"] for r in results):
                results.append({
                    "type": "marketplace",
                    "id": m["id"],
                    "title": m["name"],
                    "subtitle": m["description"][:100] if m.get("description") else "",
                    "meta": f"{m['skill_type']} - {m['price_per_use']} {m['currency']}",
                })

        return Response({
            "results": results,
            "total": len(results),
            "query": query,
        })


class NavigationViewSet(viewsets.ViewSet):
    """Navigation endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get navigation for current user."""
        nav = NavigationConfig.get_navigation(request.user)
        role = NavigationConfig.get_user_role(request.user)
        return Response({"navigation": nav, "role": role})


class AnalyticsViewSet(viewsets.ViewSet):
    """Analytics endpoints."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def global_stats(self, request):
        """Get global platform statistics."""
        if not request.user.is_staff:
            return Response({"error": "Admin only"}, status=status.HTTP_403_FORBIDDEN)
        data = AnalyticsService.get_global_stats()
        return Response(data)

    @action(detail=False, methods=["get"])
    def user_growth(self, request):
        """Get user growth data."""
        if not request.user.is_staff:
            return Response({"error": "Admin only"}, status=status.HTTP_403_FORBIDDEN)
        days = int(request.query_params.get("days", 30))
        data = AnalyticsService.get_user_growth(days)
        return Response(data)

    @action(detail=False, methods=["get"])
    def revenue(self, request):
        """Get revenue analytics."""
        if not request.user.is_staff:
            return Response({"error": "Admin only"}, status=status.HTTP_403_FORBIDDEN)
        days = int(request.query_params.get("days", 30))
        data = AnalyticsService.get_revenue_analytics(days)
        return Response(data)
