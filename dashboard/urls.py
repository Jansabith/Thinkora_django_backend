from django.urls import path

from . import chat_views, views

urlpatterns = [
    path('student/dashboard/', views.student_dashboard, name='student-dashboard'),
    path('admin/dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path('admin/student-growth/', views.student_growth, name='student-growth'),
    path('admin/reports/', views.reports, name='admin-reports'),
    path('notifications/', views.notifications, name='notifications'),
    path('search/', views.search, name='search'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    
    # Ephemeral Chat Endpoints
    path('chat/sync/', chat_views.chat_sync, name='chat-sync'),
    path('chat/messages/', chat_views.chat_messages, name='chat-messages'),
]
