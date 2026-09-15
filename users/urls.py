from django.urls import path

from . import admin_views, views

urlpatterns = [
    # Authentication (anyone can request access or log in)
    path('auth/request-access/', views.request_access, name='request-access'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/me/', views.me, name='me'),
    path('auth/change-password/', views.change_password, name='change-password'),
    # Student management (Admins with student rights, Main Admin)
    path('admin/students/', admin_views.StudentListView.as_view(), name='student-list'),
    path('admin/students/<int:pk>/', admin_views.StudentDetailView.as_view(), name='student-detail'),
    path('admin/students/<int:pk>/approve/', admin_views.approve_student, name='student-approve'),
    path('admin/students/<int:pk>/reject/', admin_views.reject_student, name='student-reject'),
    # Admin management (Main Admin only)
    path('main-admin/admins/', admin_views.AdminListCreateView.as_view(), name='admin-list'),
    path('main-admin/admins/<int:pk>/', admin_views.AdminDetailView.as_view(), name='admin-detail'),
]
