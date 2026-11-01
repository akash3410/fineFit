from django.urls import path
from . import views
from . import admin_user_views
from . import role_views
from apps.accounts import views as accounts_views

app_name = "admin_panel"

urlpatterns = [
    # Auth (HTML)
    path("login/", accounts_views.AdminLoginView.as_view(), name="login"),
    path("logout/", accounts_views.AdminLogoutView.as_view(), name="logout"),
    path("forgot-password/", accounts_views.ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset-password/<uuid:token>/", accounts_views.ResetPasswordView.as_view(), name="reset_password"),
    path("verify/", accounts_views.VerifyAccountView.as_view(), name="verify_account"),
    path("2fa/enroll/", accounts_views.TwoFactorEnrollView.as_view(), name="2fa_enroll"),
    path("2fa/challenge/", accounts_views.TwoFactorChallengeView.as_view(), name="2fa_challenge"),
    path("2fa/settings/", accounts_views.TwoFactorSettingsView.as_view(), name="2fa_settings"),
    
    path("", views.dashboard, name="dashboard"),
    path("custom-dashboard/", views.dashboard, name="custom_dashboard"),
    
    # Admin Users
    path("admins/", admin_user_views.admin_user_list, name="admin_user_list"),
    path("admins/create/", admin_user_views.admin_user_create, name="admin_user_create"),
    path("admins/<uuid:pk>/edit/", admin_user_views.admin_user_edit, name="admin_user_edit"),
    path("admins/<uuid:pk>/toggle/", admin_user_views.admin_user_toggle, name="admin_user_toggle"),
    
    # Roles & Permissions
    path("access-control/", role_views.access_control, name="access_control"),
    # Keep old URLs for backward compatibility
    path("roles/", role_views.access_control, name="role_list"),
    path("roles/create/", role_views.role_create, name="role_create"),
    path("roles/<int:pk>/edit/", role_views.role_edit, name="role_edit"),
    path("roles/<int:pk>/delete/", role_views.role_delete, name="role_delete"),
    path("permissions/", role_views.access_control, name="permission_list"),
    
    path("", views.dashboard, name="dashboard"),
    
    # Categories
    path("", views.category_list, name="category_list"),
    path("categories/", views.category_list, name="category_list_alt"),
    path("categories/add/", views.category_add, name="category_add"),
    path("add/", views.category_add, name="category_add_short"),
    path("categories/<int:pk>/view/", views.category_view, name="category_view"),
    path("<int:pk>/view/", views.category_view, name="category_view_short"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("<int:pk>/edit/", views.category_edit, name="category_edit_short"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("<int:pk>/delete/", views.category_delete, name="category_delete_short"),
    
    # Subcategories
    path("subcategories/", views.subcategory_list, name="subcategory_list"),
    path("subcategories/add/", views.subcategory_add, name="subcategory_add"),
    path("subcategories/<int:pk>/view/", views.subcategory_view, name="subcategory_view"),
    path("subcategories/<int:pk>/edit/", views.subcategory_edit, name="subcategory_edit"),
    path("subcategories/<int:pk>/delete/", views.subcategory_delete, name="subcategory_delete"),
    
    # Products
    path("products/", views.product_list, name="product_list"),
    path("products/add/", views.product_add, name="product_add"),
    path("products/<uuid:pk>/view/", views.product_view, name="product_view"),
    path("products/<uuid:pk>/edit/", views.product_edit, name="product_edit"),
    path("products/<uuid:pk>/delete/", views.product_delete, name="product_delete"),
    
    # AJAX endpoints
    path("api/subcategories/<int:category_id>/", views.get_subcategories_ajax, name="get_subcategories_ajax"),
    path("subcategories/api/<int:category_id>/", views.get_subcategories_ajax, name="get_subcategories_ajax_alt"),
]
