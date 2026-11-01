from functools import wraps
from django.conf import settings
from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta


def superuser_required(function):
    @wraps(function)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/admin/login/")
        if not request.user.is_superuser:
            messages.error(request, "Only superusers can access this page.")
            return redirect("/admin/custom-dashboard/")
        return function(request, *args, **kwargs)
    return _wrapped_view


def staff_or_permission_required(perm):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("/admin/login/")
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if request.user.is_staff and request.user.is_active:
                if request.user.has_perm(perm):
                    return view_func(request, *args, **kwargs)
            messages.error(request, "You do not have permission to access this page.")
            return redirect("/admin/custom-dashboard/")
        return _wrapped_view
    return decorator


def sensitive_action_required(function):
    """
    Require recent verification before performing a sensitive action.

    Checks session for ``last_verified_at``. If the user was verified within
    SENSITIVE_ACTION_REVERIFY_WINDOW_MINUTES, the action proceeds. Otherwise
    they are redirected to the verification page.
    """
    window = getattr(settings, "SENSITIVE_ACTION_REVERIFY_WINDOW_MINUTES", 30)

    @wraps(function)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/admin/login/")
        last_verified = request.session.get("last_verified_at")
        if last_verified:
            last_verified_time = timezone.datetime.fromisoformat(last_verified)
            if timezone.is_naive(last_verified_time):
                last_verified_time = timezone.make_aware(last_verified_time)
            if timezone.now() - last_verified_time < timedelta(minutes=window):
                return function(request, *args, **kwargs)
        messages.error(
            request,
            "Please verify your identity before performing this action.",
        )
        return redirect("/admin/verify/?purpose=sensitive_action")
    return _wrapped_view


def admin_access_required(user):
    return user.is_active and user.is_staff


def staff_required_check(user):
    return user.is_active and user.is_staff
