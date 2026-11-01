from django.contrib import admin
from django.urls import path
from apps.dashboard import views

class DashboardAdmin:
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('', views.dashboard_view, name='dashboard'),
        ]
        return custom_urls + urls

# Add dashboard to admin site
admin.site.site_title = "FineFit Admin Panel"
admin.site.site_header = "FineFit E-Commerce Administration"
admin.site.index_title = "Dashboard"
