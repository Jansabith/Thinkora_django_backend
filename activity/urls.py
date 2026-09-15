from django.urls import path

from . import views

urlpatterns = [
    path('admin/activity/', views.ActivityLogListView.as_view(), name='activity-log'),
]
