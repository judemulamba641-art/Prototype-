"""
WAY Infrastructure Middleware - RequestID, RateLimit, Audit, WebSocket JWT Auth
"""
import uuid
import time
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from rest_framework import status
import structlog

from .services import AuditService, TelemetryService
from way_identity.auth import JWTAuthentication

logger = structlog.get_logger("way.middleware")


class RequestIDMiddleware:
    """Add request ID and timing."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.id = str(uuid.uuid4())
        request.start_time = time.time()
        response = self.get_response(request)
        duration = time.time() - request.start_time
        response["X-Request-ID"] = request.id
        response["X-Response-Time"] = f"{duration:.3f}s"
        logger.info("request", method=request.method, path=request.path, status=response.status_code, duration=duration, request_id=request.id)
        return response


class RateLimitMiddleware:
    """Rate limiting: 50 req/min per user/IP/skill/provider."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/health") or request.path.startswith("/api/docs"):
            return self.get_response(request)

        key = self._get_rate_limit_key(request)
        limit = settings.WAY_CONFIG["RATE_LIMIT"]
        window = settings.WAY_CONFIG["RATE_LIMIT_WINDOW"]

        current = cache.get(key, 0)
        if current >= limit:
            logger.warning("rate_limit.exceeded", key=key, path=request.path)
            return JsonResponse({"error": "Rate limit exceeded", "retry_after": window}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        cache.set(key, current + 1, window)
        response = self.get_response(request)
        response["X-RateLimit-Limit"] = str(limit)
        response["X-RateLimit-Remaining"] = str(max(0, limit - current - 1))
        response["X-RateLimit-Reset"] = str(window)
        return response

    def _get_rate_limit_key(self, request):
        if hasattr(request, 'user') and request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated:
            return f"ratelimit:user:{request.user.id}:{request.path}"
        ip = self._get_client_ip(request)
        return f"ratelimit:ip:{ip}:{request.path}"

    def _get_client_ip(self, request):
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded:
            return x_forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


class AuditMiddleware:
    """Audit critical operations."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Telemetry (pas d'audit ici pour éviter l'erreur request.user)
        TelemetryService.record("requests", 1, "count", {"method": request.method, "path": request.path, "status": response.status_code})
        if response.status_code >= 400:
            TelemetryService.record("errors", 1, "count", {"status": response.status_code, "path": request.path})

        return response

    def _get_client_ip(self, request):
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded:
            return x_forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


class WebSocketJWTAuthMiddleware:
    """JWT authentication for WebSocket connections."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        from urllib.parse import parse_qs
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]

        if token:
            try:
                import jwt
                payload = jwt.decode(token, settings.WAY_CONFIG["JWT_SECRET"], algorithms=["HS256"])
                scope["user_id"] = payload.get("user_id")
                scope["auth_scope"] = payload.get("scope", "full")
            except jwt.InvalidTokenError:
                scope["user_id"] = None
        else:
            scope["user_id"] = None

        return await self.app(scope, receive, send)
