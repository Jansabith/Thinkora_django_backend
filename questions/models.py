from django.db import models


class Question(models.Model):
    """A practice question inside a topic, added by an admin."""

    class Difficulty(models.TextChoices):
        EASY = 'easy', 'Easy'
        MEDIUM = 'medium', 'Medium'
        HARD = 'hard', 'Hard'

    # 'courses.Topic' as text avoids importing the courses app here.
    topic = models.ForeignKey('courses.Topic', on_delete=models.CASCADE, related_name='questions')
    text = models.TextField(help_text='The question students will practise.')
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.EASY)
    answer = models.TextField(
        blank=True,
        help_text='Model answer or solution. Hidden from students, unless an admin shows it to one student.',
    )
    order = models.PositiveIntegerField(default=0, help_text='Smaller numbers are shown first.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']
        # "All EASY questions of this topic" is the most common search: an index keeps it fast.
        indexes = [models.Index(fields=['topic', 'difficulty'])]

    def __str__(self):
        return self.text[:60]

class AssignedQuestion(models.Model):
    """A specific question assigned to a student by a teacher/admin."""
    student = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='assigned_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='assignments')
    assigned_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='assigned_tasks')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-assigned_at']
        unique_together = ['student', 'question']

    def __str__(self):
        return f"Assigned to {self.student.username}: {self.question.id}"
