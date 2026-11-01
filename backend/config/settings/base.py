"""
Base settings for FineFit E-Commerce backend.
"""

from pathlib import Path
import sys
from datetime import timedelta

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Add apps directory to sys.path so apps can be referenced directly or via apps.<app_name>
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "apps"))

# Initialize environment parser
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, ""),
    ALLOWED_HOSTS=(list, ["127.0.0.1", "localhost"]),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173", "http://127.0.0.1:5173"]),
    CSRF_TRUSTED_ORIGINS=(list, ["http://localhost:5173", "http://127.0.0.1:5173"]),
)

# Load .env file if it exists (checks backend/.env, then project root .env)
env_file_backend = BASE_DIR / ".env"
env_file_root = BASE_DIR.parent / ".env"
if env_file_backend.is_file():
    environ.Env.read_env(env_file_backend)
elif env_file_root.is_file():
    environ.Env.read_env(env_file_root)

# Security defaults
SECRET_KEY = env("SECRET_KEY", default="django-insecure-finefit-dev-key-change-in-production-1234567890")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# Application definition
INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    "unfold.contrib.import_export",
    "unfold.contrib.guardian",
    "unfold.contrib.simple_history",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party applications
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",

    # Domain modular applications
    "apps.accounts.apps.AccountsConfig",
    "apps.catalog.apps.CatalogConfig",
    "apps.inventory.apps.InventoryConfig",
    "apps.cart.apps.CartConfig",
    "apps.dashboard.apps.DashboardConfig",
    "apps.admin_panel.apps.AdminPanelConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.TwoFactorRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database Configuration (PostgreSQL 16+ with psycopg 3)
# Note: Production and staging databases must provide a valid PostgreSQL connection string.
# Default targets the local PostgreSQL instance.
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://finefit_user:finefit_password@127.0.0.1:5432/finefit_db"
    )
}

# Custom User Model (Configured before the first database migration)
AUTH_USER_MODEL = "accounts.CustomUser"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 8,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media uploads
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django Unfold configuration
UNFOLD = {
    "SITE_TITLE": "FineFit Admin Panel",
    "SITE_HEADER": "FineFit E-Commerce Administration",
    "SITE_SUBHEADER": "Fashion e-commerce operations dashboard",
    "SITE_FAVICON": "/static/images/favicon.png",
    "SHOW_SEARCH": True,
    "SEARCH_QUERY": "",
    "SEARCH_INPUT_PLACEHOLDER": "Search categories, products, variants...",
    "SITE_LOGO": "/static/images/logo.png",
    "SITE_SYMBOL": "finefit",
    "THEME": {
        "dark_mode": True,
        "colors": {
            "primary": {
                "50": "#f0f9ff",
                "100": "#e0f2fe",
                "200": "#bae6fd",
                "300": "#7dd3fc",
                "400": "#38bdf8",
                "500": "#0ea5e9",
                "600": "#0284c7",
                "700": "#0369a1",
                "800": "#075985",
                "900": "#0c4a6e",
            },
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_apps": True,
        "navigation": [
            {
                "title": "Dashboard",
                "separator": False,
                "items": [
                    {
                        "title": "Dashboard",
                        "icon": "dashboard",
                        "link": "/admin/",
                    },
                ],
            },
            {
                "title": "Catalog",
                "separator": False,
                "items": [
                    {
                        "title": "Categories",
                        "icon": "category",
                        "link": "/admin/catalog/category/",
                    },
                    {
                        "title": "Subcategories",
                        "icon": "subdirectory",
                        "link": "/admin/catalog/subcategory/",
                    },
                    {
                        "title": "Products",
                        "icon": "inventory_2",
                        "link": "/admin/catalog/product/",
                    },
                    {
                        "title": "Product Variants",
                        "icon": "tune",
                        "link": "/admin/catalog/productvariant/",
                    },
                    {
                        "title": "Product Images",
                        "icon": "photo",
                        "link": "/admin/catalog/productimage/",
                    },
                ],
            },
            {
                "title": "Inventory",
                "separator": False,
                "items": [
                    {
                        "title": "Stock Records",
                        "icon": "storage",
                        "link": "/admin/inventory/stockrecord/",
                    },
                ],
            },
            {
                "title": "Accounts",
                "separator": False,
                "items": [
                    {
                        "title": "Users",
                        "icon": "person",
                        "link": "/admin/accounts/customuser/",
                    },
                ],
            },
        ],
    },
}

# Django REST Framework configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # SessionAuthentication is the primary authentication scheme for the initial browser app
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

# CORS Configuration (Explicit origins only, no wildcards)
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# CSRF Configuration
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
CSRF_COOKIE_HTTPONLY = False  # Allows frontend JavaScript to read csrftoken cookie for API headers
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True

AUTHENTICATION_BACKENDS = [
    "apps.accounts.authentication.EmailOrPhoneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Login/Logout URLs for admin panel HTML views
LOGIN_URL = "/admin/login/"
LOGOUT_REDIRECT_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/custom-dashboard/"

# Session cookie age: 2 weeks (1209600 seconds) when "remember me" is used
SESSION_COOKIE_AGE = 1209600

# Email configuration (SMTP via env; console backend in dev)
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@finefit.store")
SITE_NAME = env("SITE_NAME", default="FineFit")

# Simple JWT configuration
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# REST Framework authentication: JWT for API clients, Session for HTML panel
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = [
    "rest_framework_simplejwt.authentication.JWTAuthentication",
    "rest_framework.authentication.SessionAuthentication",
]

# Hardened session/cookie security
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = "Lax"

# OTP / verification configuration
OTP_CODE_LENGTH = 6
OTP_CODE_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
VERIFICATION_MAX_PER_DAY = 15
PASSWORD_RESET_TOKEN_EXPIRY_HOURS = 1
SENSITIVE_ACTION_REVERIFY_WINDOW_MINUTES = 30

# Device / browser verification (remember this device)
DEVICE_VERIFICATION_COOKIE_NAME = "ff_device_token"
DEVICE_VERIFICATION_DAYS = 30
