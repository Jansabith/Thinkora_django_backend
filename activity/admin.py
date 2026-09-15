from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'kind', 'message', 'actor']
    list_filter = ['kind']
    search_fields = ['message', 'actor__username']
    readonly_fields = ['created_at', 'kind', 'message', 'link', 'actor']
