from rest_framework import serializers

from .models import AssignedQuestion, Question

# Where the question lives: shown in lists of questions from many topics.
LOCATION_FIELDS = ['topic_title', 'course_id', 'course_title']


class QuestionLocationMixin(serializers.Serializer):
    topic_title = serializers.CharField(source='topic.title', read_only=True)
    course_id = serializers.IntegerField(source='topic.course_id', read_only=True)
    course_title = serializers.CharField(source='topic.course.title', read_only=True)


class QuestionSerializer(QuestionLocationMixin, serializers.ModelSerializer):
    """Everything about a question, including the answer (for content managers)."""

    class Meta:
        model = Question
        fields = ['id', 'topic', *LOCATION_FIELDS, 'text', 'difficulty', 'answer', 'order', 'created_at', 'updated_at']
        # The topic comes from the URL when creating, and cannot be changed later.
        read_only_fields = ['topic', 'created_at', 'updated_at']


class StudentQuestionSerializer(QuestionLocationMixin, serializers.ModelSerializer):
    """
    What students receive: NO answer.
    An admin can show the answer to one student (see the progress app).
    """

    class Meta:
        model = Question
        fields = ['id', 'topic', *LOCATION_FIELDS, 'text', 'difficulty', 'order']

class AssignedQuestionSerializer(serializers.ModelSerializer):
    question = StudentQuestionSerializer(read_only=True)
    assigned_by_name = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = AssignedQuestion
        fields = ['id', 'question', 'assigned_at', 'assigned_by_name', 'progress']

    def get_assigned_by_name(self, obj):
        if not obj.assigned_by:
            return "A Teacher"
        name = f"{obj.assigned_by.first_name} {obj.assigned_by.last_name}".strip()
        return name if name else obj.assigned_by.username

    def get_progress(self, obj):
        if hasattr(obj.question, 'user_progress') and obj.question.user_progress:
            from progress.serializers import MyProgressSerializer
            return MyProgressSerializer(obj.question.user_progress[0]).data
        return None
