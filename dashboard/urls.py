from django.urls import path

from . import views

urlpatterns = [
    path('student/dashboard/', views.student_dashboard, name='student-dashboard'),
    path('admin/dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path('admin/student-growth/', views.student_growth, name='student-growth'),
    path('admin/reports/', views.reports, name='reports'),
    path('notifications/', views.notifications, name='notifications'),
    path('search/', views.search, name='search'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
]
