"""
Production settings for FineFit E-Commerce backend.
"""

from .base import *

DEBUG = False

# Host configuration - must be explicitly defined in environment
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# Enforce HTTPS and strict security headers
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True

# Validate that production SECRET_KEY is provided
if SECRET_KEY.startswith("django-insecure-"):
    raise RuntimeError("Insecure SECRET_KEY detected in production settings!")
