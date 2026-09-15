from django.shortcuts import get_object_or_404
from rest_framework import generics

from activity.models import ActivityLog
from activity.services import log_activity
from courses.visibility import can_manage_content, get_visible_topics
from users.permissions import CanManageContentOrReadOnly

from .models import Video
from .serializers import VideoSerializer

CONTENT_LOG = ActivityLog.Kind.CONTENT


def get_visible_videos(user):
    videos = Video.objects.select_related('topic__course')
    if not can_manage_content(user):
        videos = videos.filter(topic__course__is_published=True)
    return videos


def describe_video(video):
    return f'Video "{video.title}" in "{video.topic.title}" ({video.topic.course.title})'


class VideoListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/topics/<topic_id>/videos/  -> videos of one topic
    POST /api/topics/<topic_id>/videos/  -> add a video (content managers only)
    """

    serializer_class = VideoSerializer
    permission_classes = [CanManageContentOrReadOnly]

    def get_topic(self):
        return get_object_or_404(get_visible_topics(self.request.user), pk=self.kwargs['topic_id'])

    def get_queryset(self):
        return Video.objects.filter(topic=self.get_topic())

    def perform_create(self, serializer):
        topic = self.get_topic()
        video = serializer.save(topic=topic)
        log_activity(self.request.user, CONTENT_LOG, f'{describe_video(video)} was added', f'/admin/topics/{topic.id}/videos')


class VideoDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET              /api/videos/<id>/  -> one video
    PUT/PATCH/DELETE /api/videos/<id>/  -> content managers only
    """

    serializer_class = VideoSerializer
    permission_classes = [CanManageContentOrReadOnly]

    def get_queryset(self):
        return get_visible_videos(self.request.user)

    def perform_update(self, serializer):
        video = serializer.save()
        log_activity(self.request.user, CONTENT_LOG, f'{describe_video(video)} was updated', f'/admin/topics/{video.topic_id}/videos')

    def perform_destroy(self, instance):
        log_activity(self.request.user, CONTENT_LOG, f'{describe_video(instance)} was deleted', f'/admin/topics/{instance.topic_id}/videos')
        instance.delete()
