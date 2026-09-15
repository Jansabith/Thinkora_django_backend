from django.db import models


class Course(models.Model):
    """A subject students can study, for example 'Python' or 'JavaScript'."""

    class Level(models.TextChoices):
        BEGINNER = 'beginner', 'Beginner'
        INTERMEDIATE = 'intermediate', 'Intermediate'
        ADVANCED = 'advanced', 'Advanced'

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=60,
        blank=True,
        help_text='For example "Programming" or "Web Development". Used to group courses.',
    )
    level = models.CharField(max_length=20, choices=Level.choices, default=Level.BEGINNER)
    is_published = models.BooleanField(
        default=True,
        help_text='Only published courses are visible to students.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title


class Topic(models.Model):
    """
    One subject area inside a course, for example 'Lists' in Python.

    Every section of a course (Practice Questions, Videos, ...) is organised by topics:
    each question and each video belongs to exactly one topic.
    """

    # ForeignKey: each topic belongs to ONE course; a course has MANY topics.
    # on_delete=CASCADE: deleting a course also deletes its topics.
    # related_name='topics': lets us write course.topics.all()
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='topics')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, help_text='A short summary of what this topic covers.')
    syllabus_points = models.JSONField(default=list, blank=True, help_text='A list of bullet points covering the subtopics.')
    order = models.PositiveIntegerField(default=0, help_text='Smaller numbers are shown first.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.course.title}: {self.title}'
