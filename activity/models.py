from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """
    One line of history for admins, for example: Course "Python" was updated (by Sara).
    Lines are only added, never changed, so admins can always see who did what.
    """

    class Kind(models.TextChoices):
        STUDENT = 'student', 'Students'  # access requests, approvals, student accounts
        CONTENT = 'content', 'Content'  # courses, topics, questions, videos
        DOUBT = 'doubt', 'Doubts'  # doubts answered, answers shown
        ADMIN = 'admin', 'Admins'  # admin accounts

    # SET_NULL: the history stays even when the user who did it is deleted.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs',
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    message = models.CharField(max_length=300)
    link = models.CharField(max_length=200, blank=True, help_text='A page in the React app, for example /admin/students/5')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return self.message
