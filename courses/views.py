from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from activity.models import ActivityLog
from activity.services import log_activity
from users.permissions import CanManageContentOrReadOnly

from .serializers import CourseSerializer, TopicSerializer
from .visibility import add_course_counts, add_topic_counts, get_visible_courses, get_visible_topics

CONTENT_LOG = ActivityLog.Kind.CONTENT


class CourseListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/courses/  -> list courses (students: published only)
    POST /api/courses/  -> create a course (content managers only)
    """

    serializer_class = CourseSerializer
    permission_classes = [CanManageContentOrReadOnly]

    def get_queryset(self):
        return add_course_counts(get_visible_courses(self.request.user))

    def perform_create(self, serializer):
        course = serializer.save()
        log_activity(self.request.user, CONTENT_LOG, f'Course "{course.title}" was created', f'/admin/courses/{course.id}')


class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET              /api/courses/<id>/  -> one course with its section counts
    PUT/PATCH/DELETE /api/courses/<id>/  -> content managers only
    """

    serializer_class = CourseSerializer
    permission_classes = [CanManageContentOrReadOnly]

    def get_queryset(self):
        return add_course_counts(get_visible_courses(self.request.user))

    def perform_update(self, serializer):
        course = serializer.save()
        log_activity(self.request.user, CONTENT_LOG, f'Course "{course.title}" was updated', f'/admin/courses/{course.id}')

    def perform_destroy(self, instance):
        log_activity(self.request.user, CONTENT_LOG, f'Course "{instance.title}" was deleted', '/admin/courses')
        instance.delete()


class AllTopicsView(generics.ListAPIView):
    """
    GET /api/topics/  -> topics of every course I can see, with their counts
    Filters: ?course=1  ?search=list
    """

    serializer_class = TopicSerializer

    def get_queryset(self):
        topics = get_visible_topics(self.request.user)

        course_id = self.request.query_params.get('course')
        if course_id:
            if not course_id.isdigit():
                raise ValidationError({'course': 'Must be a number.'})
            topics = topics.filter(course_id=course_id)

        search = self.request.query_params.get('search', '').strip()
        if search:
            topics = topics.filter(Q(title__icontains=search) | Q(description__icontains=search))

        return add_topic_counts(topics).order_by('course__title', 'course_id', 'order', 'id')


class TopicListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/courses/<course_id>/topics/  -> topics of one course, in order, with counts
    POST /api/courses/<course_id>/topics/  -> add a topic (content managers only)
    """

    serializer_class = TopicSerializer
    permission_classes = [CanManageContentOrReadOnly]

    def get_course(self):
        return get_object_or_404(get_visible_courses(self.request.user), pk=self.kwargs['course_id'])

    def get_queryset(self):
        topics = get_visible_topics(self.request.user).filter(course=self.get_course())
        return add_topic_counts(topics)

    def perform_create(self, serializer):
        course = self.get_course()
        topic = serializer.save(course=course)
        log_activity(
            self.request.user,
            CONTENT_LOG,
            f'Topic "{topic.title}" was added to "{course.title}"',
            f'/admin/courses/{course.id}',
        )


class TopicDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET              /api/topics/<id>/  -> one topic with its counts
    PUT/PATCH/DELETE /api/topics/<id>/  -> content managers only
    """

    serializer_class = TopicSerializer
    permission_classes = [CanManageContentOrReadOnly]

    def get_queryset(self):
        return add_topic_counts(get_visible_topics(self.request.user))

    def perform_update(self, serializer):
        topic = serializer.save()
        log_activity(
            self.request.user,
            CONTENT_LOG,
            f'Topic "{topic.title}" in "{topic.course.title}" was updated',
            f'/admin/courses/{topic.course_id}',
        )

    def perform_destroy(self, instance):
        log_activity(
            self.request.user,
            CONTENT_LOG,
            f'Topic "{instance.title}" was deleted from "{instance.course.title}"',
            f'/admin/courses/{instance.course_id}',
        )
        instance.delete()
