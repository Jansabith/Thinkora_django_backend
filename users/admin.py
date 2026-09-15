from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class LmsUserAdmin(UserAdmin):
    """Django's ready-made user screen, plus our LMS fields."""

    list_display = ['username', 'email', 'role', 'access_status', 'is_active', 'date_joined']
    list_filter = ['role', 'access_status', 'is_active']
    fieldsets = UserAdmin.fieldsets + (
        (
            'LMS',
            {
                'fields': (
                    'role',
                    'access_status',
                    'request_message',
                    'reviewed_by',
                    'reviewed_at',
                    'can_manage_students',
                    'can_manage_content',
                )
            },
        ),
    )
