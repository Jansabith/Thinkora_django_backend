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

    class Meta:
        model = Topic
        fields = [
            'id',
            'course',
            'course_title',
            'title',
            'description',
            'order',
            'question_count',
            'easy_count',
            'medium_count',
            'hard_count',
            'video_count',
            'created_at',
            'updated_at',
        ]
        # The course comes from the URL when creating, and cannot be changed later.
        read_only_fields = ['course', 'created_at', 'updated_at']
