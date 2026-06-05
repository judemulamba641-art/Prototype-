"""
WAY Backend Settings - Production Ready
Optimized architecture: 6 apps, unified configuration
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-prod")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
TESTING = "pytest" in sys.argv[0] or os.getenv("TESTING", "False").lower() == "true"

ALLOWED_HOSTS = ["*" if DEBUG else h for h in os.getenv("ALLOWED_HOSTS", "localhost").split(",")]

# Apps
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "channels",
    "way_core",
    "way_identity",
    "way_finance",
    "way_skills",
    "way_infra",
    "way_ops",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "way_infra.middleware.RequestIDMiddleware",
    "way_infra.middleware.RateLimitMiddleware",
    "way_infra.middleware.AuditMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "way_project.urls"
WSGI_APPLICATION = "way_project.wsgi.application"
ASGI_APPLICATION = "way_project.asgi.application"

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
}

# Override for production
if os.getenv("DB_ENGINE") == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "way_db"),
            "USER": os.getenv("DB_USER", "way"),
            "PASSWORD": os.getenv("DB_PASSWORD", "way"),
            "HOST": os.getenv("DB_HOST", "postgres"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": 600,
            "OPTIONS": {
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000",
            },
        }
    }

# Cache & Channels
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Production: Redis
# CACHES = {
#     "default": {
#         "BACKEND": "django_redis.cache.RedisCache",
#         "LOCATION": REDIS_URL,
#         "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
#     }
# }

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}

# Media
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# DRF
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["way_identity.auth.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/min",
        "user": "50/min",
        "wallet": "30/min",
        "skill": "100/min",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "WAY API",
    "DESCRIPTION": "WAY Platform - Backend API v2.4",
    "VERSION": "2.4.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# CORS
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
CORS_ALLOW_CREDENTIALS = True

# Security
SECURE_SSL_REDIRECT = not DEBUG and not TESTING
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = not DEBUG and not TESTING
CSRF_COOKIE_SECURE = not DEBUG and not TESTING

# WAY Configuration
WAY_CONFIG = {
    "JWT_SECRET": os.getenv("JWT_SECRET", SECRET_KEY),
    "JWT_ACCESS_LIFETIME": int(os.getenv("JWT_ACCESS_LIFETIME", "900")),
    "JWT_REFRESH_LIFETIME": int(os.getenv("JWT_REFRESH_LIFETIME", "604800")),
    "ENCRYPTION_KEY": os.getenv("ENCRYPTION_KEY", SECRET_KEY[:32]),
    "RATE_LIMIT": int(os.getenv("RATE_LIMIT", "50")),
    "RATE_LIMIT_WINDOW": int(os.getenv("RATE_LIMIT_WINDOW", "60")),
    "DEFAULT_CURRENCY": os.getenv("DEFAULT_CURRENCY", "USD"),
    "CREDIT_RATE": int(os.getenv("CREDIT_RATE", "100")),
    "SANDBOX_TIMEOUT": 15,
    "SANDBOX_RAM_MB": 256,
    "SANDBOX_CPU_CORES": 2,
    "SANDBOX_DISK_MB": 100,
    "PROVIDERS": {
        "openai": {"api_key": os.getenv("OPENAI_API_KEY"), "model": "gpt-4", "priority": 1},
        "anthropic": {"api_key": os.getenv("ANTHROPIC_API_KEY"), "model": "claude-3", "priority": 2},
        "google": {"api_key": os.getenv("GOOGLE_API_KEY"), "model": "gemini-pro", "priority": 3},
        "deepseek": {"api_key": os.getenv("DEEPSEEK_API_KEY"), "model": "deepseek-chat", "priority": 4},
        "glm": {"api_key": os.getenv("GLM_API_KEY"), "model": "glm-4", "priority": 5},
        "grok": {"api_key": os.getenv("GROK_API_KEY"), "model": "grok-1", "priority": 6},
    },
    "PAYMENTS": {
        "stripe": {"secret_key": os.getenv("STRIPE_SECRET_KEY"), "webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET")},
        "mpesa": {"api_key": os.getenv("MPESA_API_KEY"), "secret": os.getenv("MPESA_SECRET")},
        "airtel": {"api_key": os.getenv("AIRTEL_API_KEY")},
        "orange": {"api_key": os.getenv("ORANGE_API_KEY")},
    },
    "STORAGE_BACKEND": os.getenv("STORAGE_BACKEND", "local"),
    "AWS": {
        "access_key": os.getenv("AWS_ACCESS_KEY_ID"),
        "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "bucket": os.getenv("AWS_STORAGE_BUCKET_NAME"),
        "region": os.getenv("AWS_S3_REGION_NAME", "us-east-1"),
    },
    "SENTRY_DSN": os.getenv("SENTRY_DSN"),
    "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
    "ENABLE_WEBSOCKET": os.getenv("ENABLE_WEBSOCKET", "True").lower() == "true",
    "ENABLE_CELERY": os.getenv("ENABLE_CELERY", "True").lower() == "true",
}

# Logging
import structlog

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(colors=True),
            "foreign_pre_chain": [
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                structlog.processors.TimeStamper(fmt="iso"),
            ],
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": WAY_CONFIG["LOG_LEVEL"]},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "way": {"handlers": ["console"], "level": WAY_CONFIG["LOG_LEVEL"], "propagate": False},
    },
}

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Celery
if WAY_CONFIG["ENABLE_CELERY"] and not DEBUG:
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_ACCEPT_CONTENT = ["json"]
    CELERY_TASK_SERIALIZER = "json"
    CELERY_RESULT_SERIALIZER = "json"
    CELERY_TASK_TIME_LIMIT = 300
    CELERY_TASK_SOFT_TIME_LIMIT = 240
    CELERY_WORKER_CONCURRENCY = 4
    CELERY_BEAT_SCHEDULE = {}  # Disabled for SQLite testing

# Auth
AUTH_USER_MODEL = "way_identity.User"

# Storage
if WAY_CONFIG["STORAGE_BACKEND"] == "s3":
    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_ACCESS_KEY_ID = WAY_CONFIG["AWS"]["access_key"]
    AWS_SECRET_ACCESS_KEY = WAY_CONFIG["AWS"]["secret_key"]
    AWS_STORAGE_BUCKET_NAME = WAY_CONFIG["AWS"]["bucket"]
    AWS_S3_REGION_NAME = WAY_CONFIG["AWS"]["region"]
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = "private"
    AWS_S3_ENCRYPTION = True
