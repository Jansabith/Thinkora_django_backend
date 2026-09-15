from django.conf import settings
from django.db import models
from django.db.models import F


class Task(models.Model):
    """A personal to-do item. Every user (student or admin) has their own private list."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tasks')
    title = models.CharField(max_length=200)
    is_done = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Open tasks first, then the nearest due date (tasks without a date last), then newest.
        ordering = ['is_done', F('due_date').asc(nulls_last=True), '-created_at']

    def __str__(self):
        return self.title
