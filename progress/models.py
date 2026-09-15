from django.conf import settings
from django.db import models
from django.utils import timezone


class QuestionProgress(models.Model):
    """
    What ONE student did with ONE practice question:
    marked it as done, bookmarked it, and/or asked a doubt (which an admin can answer).
    """

    class DoubtStatus(models.TextChoices):
        NONE = 'none', 'No doubt'
        OPEN = 'open', 'Open'
        RESOLVED = 'resolved', 'Resolved'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='question_progress',
    )
    question = models.ForeignKey('questions.Question', on_delete=models.CASCADE, related_name='progress')

    is_done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)

    is_bookmarked = models.BooleanField(default=False)

    doubt_status = models.CharField(max_length=10, choices=DoubtStatus.choices, default=DoubtStatus.NONE)
    doubt_message = models.TextField(blank=True)
    doubt_raised_at = models.DateTimeField(null=True, blank=True)
    admin_reply = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_doubts',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    # False while the student has not yet opened Messages after the latest reply.
    reply_seen = models.BooleanField(default=True)

    # Students never see a question's answer, unless an admin shows it to THIS student.
    answer_shared = models.BooleanField(default=False)
    answer_shared_at = models.DateTimeField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            # A student has at most ONE progress row per question.
            models.UniqueConstraint(fields=['student', 'question'], name='one_progress_per_student_question'),
        ]
        indexes = [
            # The admin Doubts page asks for "all OPEN doubts" often.
            models.Index(fields=['doubt_status']),
        ]

    def __str__(self):
        return f'{self.student} - question {self.question_id}'

    def set_done(self, is_done):
        if is_done != self.is_done:
            self.is_done = is_done
            self.done_at = timezone.now() if is_done else None

    def raise_doubt(self, message):
        self.doubt_status = self.DoubtStatus.OPEN
        self.doubt_message = message
        self.doubt_raised_at = timezone.now()
        # A new doubt starts fresh: an older reply no longer applies.
        self.admin_reply = ''
        self.resolved_by = None
        self.resolved_at = None
        self.reply_seen = True

    def clear_doubt(self):
        self.doubt_status = self.DoubtStatus.NONE
        self.doubt_message = ''
        self.doubt_raised_at = None
        self.admin_reply = ''
        self.resolved_by = None
        self.resolved_at = None
        self.reply_seen = True

    def share_answer(self, is_shared):
        if is_shared != self.answer_shared:
            self.answer_shared = is_shared
            self.answer_shared_at = timezone.now() if is_shared else None

    def resolve_doubt(self, admin, reply):
        self.doubt_status = self.DoubtStatus.RESOLVED
        self.admin_reply = reply
        self.resolved_by = admin
        self.resolved_at = timezone.now()
        self.reply_seen = False


class TopicProgress(models.Model):
    """
    Tracks if a student has completed a topic (Roadmap feature)
    and if an admin has manually unlocked it.
    """
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='topic_progress',
    )
    topic = models.ForeignKey('courses.Topic', on_delete=models.CASCADE, related_name='progress')
    
    is_completed = models.BooleanField(default=False)
    admin_unlocked = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'topic'], name='one_progress_per_student_topic'),
        ]

    def __str__(self):
        return f'{self.student} - topic {self.topic_id} (completed: {self.is_completed})'
