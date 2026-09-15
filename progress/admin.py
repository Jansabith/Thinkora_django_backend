from django.contrib import admin

from .models import QuestionProgress


@admin.register(QuestionProgress)
class QuestionProgressAdmin(admin.ModelAdmin):
    list_display = ['student', 'question', 'is_done', 'doubt_status', 'updated_at']
    list_filter = ['is_done', 'doubt_status', 'question__topic__course']
    search_fields = ['student__username', 'question__text', 'doubt_message']
    raw_id_fields = ['student', 'question', 'resolved_by']
