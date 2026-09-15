"""
URL configuration for the LMS project.

Every API address starts with /api/. Each app keeps its own urls.py,
and include() plugs them in here.

Django's built-in admin site lives at /django-admin/ because /admin/... is used by
the React admin pages (in production both are served from the same domain).
"""

from django.contrib import admin
from django.urls import include, path

from .views import dashboard_stats, health_check

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('api/health/', health_check, name='health-check'),
    path('api/admin/stats/', dashboard_stats, name='dashboard-stats'),
    path('api/', include('users.urls')),
    path('api/', include('courses.urls')),
    path('api/', include('questions.urls')),
    path('api/', include('videos.urls')),
    path('api/', include('progress.urls')),
    path('api/', include('activity.urls')),
    path('api/', include('tasks.urls')),
    path('api/', include('dashboard.urls')),
]
