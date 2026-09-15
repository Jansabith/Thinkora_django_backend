from django.db import models


class Video(models.Model):
    """A video lesson inside a topic, added by an admin."""

    # 'courses.Topic' as text avoids importing the courses app here.
    topic = models.ForeignKey('courses.Topic', on_delete=models.CASCADE, related_name='videos')
    title = models.CharField(max_length=200)
    # URLField only accepts real web links (http/https), never things like "javascript:".
    url = models.URLField(help_text='A YouTube link, or a link to any other video page.')
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0, help_text='Smaller numbers are shown first.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.title
