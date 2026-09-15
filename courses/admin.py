from django.contrib import admin

from .models import Course, Topic


class TopicInline(admin.TabularInline):
    """Shows a course's topics inside the course page."""

    model = Topic
    fields = ['order', 'title']
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['title', 'is_published', 'created_at']
    list_filter = ['is_published']
    search_fields = ['title']
    inlines = [TopicInline]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'order']
    list_filter = ['course']
    search_fields = ['title', 'description']
