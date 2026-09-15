from rest_framework import serializers

from .models import QuestionProgress

MY_PROGRESS_FIELDS = [
    'question',
    'is_done',
    'done_at',
    'is_bookmarked',
    'doubt_status',
    'doubt_message',
    'doubt_raised_at',
    'admin_reply',
    'resolved_at',
    'reply_seen',
    'answer_shared',
]


class MyProgressSerializer(serializers.ModelSerializer):
    """A student's own progress on one question."""

    # The answer is only included when an admin chose to show it to this student.
    answer = serializers.SerializerMethodField()

    class Meta:
        model = QuestionProgress
        fields = [*MY_PROGRESS_FIELDS, 'answer']
        read_only_fields = MY_PROGRESS_FIELDS

    def get_answer(self, record):
        return record.question.answer if record.answer_shared else None


class MyMessageSerializer(MyProgressSerializer):
    """A student's doubt with the teacher's reply, plus where the question lives."""

    question_text = serializers.CharField(source='question.text', read_only=True)
    question_difficulty = serializers.CharField(source='question.difficulty', read_only=True)
    topic_id = serializers.IntegerField(source='question.topic_id', read_only=True)
    topic_title = serializers.CharField(source='question.topic.title', read_only=True)
    course_title = serializers.CharField(source='question.topic.course.title', read_only=True)
    resolved_by = serializers.SlugRelatedField(slug_field='username', read_only=True)
    resolved_by_name = serializers.SerializerMethodField()

    class Meta(MyProgressSerializer.Meta):
        fields = [
            'id',
            *MyProgressSerializer.Meta.fields,
            'question_text',
            'question_difficulty',
            'topic_id',
            'topic_title',
            'course_title',
            'resolved_by',
            'resolved_by_name',
        ]

    def get_resolved_by_name(self, record):
        return record.resolved_by.display_name if record.resolved_by else None


class ProgressUpdateSerializer(serializers.Serializer):
    """What a student sends when clicking Done, Bookmark or Doubt."""

    is_done = serializers.BooleanField(required=False)
    is_bookmarked = serializers.BooleanField(required=False)
    # Students may only open or clear a doubt. Only admins can resolve one.
    doubt_status = serializers.ChoiceField(
        choices=[QuestionProgress.DoubtStatus.NONE, QuestionProgress.DoubtStatus.OPEN],
        required=False,
    )
    doubt_message = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate(self, data):
        if not {'is_done', 'is_bookmarked', 'doubt_status'} & data.keys():
            raise serializers.ValidationError('Send is_done, is_bookmarked and/or doubt_status.')
        return data


class ProgressRecordSerializer(serializers.ModelSerializer):
    """One row for admins: which student, which question, done and/or doubt."""

    student_username = serializers.CharField(source='student.username', read_only=True)
    student_name = serializers.CharField(source='student.display_name', read_only=True)
    student_whatsapp = serializers.CharField(source='student.whatsapp_number', read_only=True)
    question_text = serializers.CharField(source='question.text', read_only=True)
    question_difficulty = serializers.CharField(source='question.difficulty', read_only=True)
    question_answer = serializers.CharField(source='question.answer', read_only=True)
    topic_id = serializers.IntegerField(source='question.topic_id', read_only=True)
    topic_title = serializers.CharField(source='question.topic.title', read_only=True)
    course_id = serializers.IntegerField(source='question.topic.course_id', read_only=True)
    course_title = serializers.CharField(source='question.topic.course.title', read_only=True)
    resolved_by = serializers.SlugRelatedField(slug_field='username', read_only=True)

    class Meta:
        model = QuestionProgress
        fields = [
            'id',
            'student',
            'student_username',
            'student_name',
            'student_whatsapp',
            'question',
            'question_text',
            'question_difficulty',
            'question_answer',
            'topic_id',
            'topic_title',
            'course_id',
            'course_title',
            'is_done',
            'done_at',
            'doubt_status',
            'doubt_message',
            'doubt_raised_at',
            'admin_reply',
            'resolved_by',
            'resolved_at',
            'reply_seen',
            'answer_shared',
            'answer_shared_at',
            'updated_at',
        ]
        read_only_fields = fields


class ResolveDoubtSerializer(serializers.Serializer):
    reply = serializers.CharField(max_length=2000)
    # Optional: also show (true) or hide (false) the answer for this student.
    share_answer = serializers.BooleanField(required=False)


class ShareAnswerSerializer(serializers.Serializer):
    shared = serializers.BooleanField()
