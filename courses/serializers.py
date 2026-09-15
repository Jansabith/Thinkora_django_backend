from rest_framework import serializers

from .models import Course, Topic


class CourseSerializer(serializers.ModelSerializer):
    # Counted by the database (see visibility.add_course_counts).
    topic_count = serializers.IntegerField(read_only=True)
    question_count = serializers.IntegerField(read_only=True)
    video_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'description',
            'category',
            'level',
            'is_published',
            'topic_count',
            'question_count',
            'video_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class TopicSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    # Counted by the database (see visibility.add_topic_counts).
    question_count = serializers.IntegerField(read_only=True)
    easy_count = serializers.IntegerField(read_only=True)
    medium_count = serializers.IntegerField(read_only=True)
    hard_count = serializers.IntegerField(read_only=True)
    video_count = serializers.IntegerField(read_only=True)
    
    is_completed = serializers.SerializerMethodField()
    admin_unlocked = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = Topic
        fields = [
            'id',
            'course',
            'course_title',
            'title',
            'description',
            'syllabus_points',
            'order',
            'question_count',
            'easy_count',
            'medium_count',
            'hard_count',
            'video_count',
            'is_completed',
            'admin_unlocked',
            'is_locked',
            'created_at',
            'updated_at',
        ]
        # The course comes from the URL when creating, and cannot be changed later.
        read_only_fields = ['course', 'created_at', 'updated_at']

    def _get_progress(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated or request.user.is_staff:
            return None
            
        # Cache the progress dictionary on the serializer instance to prevent N+1 queries
        if not hasattr(self, '_progress_cache'):
            from progress.models import TopicProgress
            # We assume the serializer is serializing a list of topics for the same course
            # If not, we just fetch progress for all topics in the DB for this user
            progress_qs = TopicProgress.objects.filter(student=request.user).select_related('topic')
            self._progress_cache = {p.topic_id: p for p in progress_qs}
            
            # We also need the ordered list of topics in the course to determine previous topic completion
            # This is slightly tricky if it's a list view vs detail view.
            if hasattr(self, 'instance') and isinstance(self.instance, list) and len(self.instance) > 0:
                course_id = self.instance[0].course_id
            else:
                course_id = obj.course_id
                
            from courses.models import Topic
            course_topics = Topic.objects.filter(course_id=course_id).order_by('order', 'id')
            self._ordered_topic_ids = [t.id for t in course_topics]

        return self._progress_cache.get(obj.id)

    def get_is_completed(self, obj):
        prog = self._get_progress(obj)
        return prog.is_completed if prog else False

    def get_admin_unlocked(self, obj):
        prog = self._get_progress(obj)
        return prog.admin_unlocked if prog else False

    def get_is_locked(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated or request.user.is_staff:
            return False # Admins see everything unlocked
            
        prog = self._get_progress(obj)
        if prog and prog.admin_unlocked:
            return False # Explicitly unlocked by admin
            
        # Is it the first topic?
        if not hasattr(self, '_ordered_topic_ids'):
            self._get_progress(obj) # initialize caches
            
        try:
            idx = self._ordered_topic_ids.index(obj.id)
            if idx == 0:
                return False # First topic is always unlocked
                
            # Check if previous topic is completed
            prev_topic_id = self._ordered_topic_ids[idx - 1]
            prev_prog = self._progress_cache.get(prev_topic_id)
            if prev_prog and prev_prog.is_completed:
                return False # Unlocked because previous is completed
                
            return True # Locked!
        except ValueError:
            # Should not happen, but fallback to unlocked if we can't determine order
            return False
