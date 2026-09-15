"""
Admin views: see every student's progress and doubts, reply to doubts and share answers.
Progress is student data, so these need student-management rights.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from activity.models import ActivityLog
from activity.services import log_activity
from courses.models import Topic
from questions.filters import read_id
from users.models import User
from users.permissions import CanManageStudents
from users.serializers import StudentSerializer

from .models import QuestionProgress
from .serializers import ProgressRecordSerializer, ResolveDoubtSerializer, ShareAnswerSerializer
from .summary import build_progress_overview

NONE = QuestionProgress.DoubtStatus.NONE
OPEN = QuestionProgress.DoubtStatus.OPEN
RESOLVED = QuestionProgress.DoubtStatus.RESOLVED

NO_ANSWER_MESSAGE = 'This question has no answer yet. Add one on the Questions page first.'
RECORD_RELATIONS = ['student', 'question__topic__course', 'resolved_by']

STATUS_FILTERS = {
    'done': Q(is_done=True),
    'open': Q(doubt_status=OPEN),
    'resolved': Q(doubt_status=RESOLVED),
    'doubts': ~Q(doubt_status=NONE),
}

# URL filter name -> database field
ID_FILTERS = {
    'student': 'student_id',
    'course': 'question__topic__course_id',
    'topic': 'question__topic_id',
    'question': 'question_id',
}


class ProgressRecordListView(generics.ListAPIView):
    """
    GET /api/admin/progress/
    Filters (all optional): ?student=5 ?course=1 ?topic=4 ?question=12
                            ?status=done | open | resolved | doubts
    """

    serializer_class = ProgressRecordSerializer
    permission_classes = [CanManageStudents]

    def get_queryset(self):
        params = self.request.query_params

        # Skip rows with nothing to show (for example only a bookmark).
        records = QuestionProgress.objects.filter(Q(is_done=True) | ~Q(doubt_status=NONE)).select_related(
            *RECORD_RELATIONS
        )

        for param, field in ID_FILTERS.items():
            value = read_id(params, param)
            if value:
                records = records.filter(**{field: value})

        status = params.get('status')
        if status:
            if status not in STATUS_FILTERS:
                raise ValidationError({'status': f'Choose one of: {", ".join(STATUS_FILTERS)}.'})
            records = records.filter(STATUS_FILTERS[status])

        return records.order_by('-updated_at')


def describe_record(record):
    return f'{record.student.display_name} on "{record.question.topic.title}"'


@api_view(['POST'])
@permission_classes([CanManageStudents])
def resolve_doubt(request, pk):
    """
    POST /api/admin/progress/<id>/resolve/  {"reply": "...", "share_answer": true}
    The student sees the reply. share_answer (optional) also shows or hides the answer.
    """
    record = get_object_or_404(QuestionProgress.objects.exclude(doubt_status=NONE).select_related(*RECORD_RELATIONS), pk=pk)
    serializer = ResolveDoubtSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    if data.get('share_answer') and not record.question.answer:
        raise ValidationError({'share_answer': NO_ANSWER_MESSAGE})

    record.resolve_doubt(request.user, data['reply'])
    if 'share_answer' in data:
        record.share_answer(data['share_answer'])
    record.save()

    log_activity(request.user, ActivityLog.Kind.DOUBT, f'Doubt answered for {describe_record(record)}', f'/admin/students/{record.student_id}')
    return Response(ProgressRecordSerializer(record).data)


@api_view(['POST'])
@permission_classes([CanManageStudents])
def share_answer(request, pk):
    """
    POST /api/admin/progress/<id>/share-answer/  {"shared": true}
    Show the question's answer to THIS ONE student ({"shared": false} hides it again).
    """
    record = get_object_or_404(QuestionProgress.objects.select_related(*RECORD_RELATIONS), pk=pk)
    serializer = ShareAnswerSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    is_shared = serializer.validated_data['shared']

    if is_shared and not record.question.answer:
        raise ValidationError({'shared': NO_ANSWER_MESSAGE})

    record.share_answer(is_shared)
    record.save()

    action = 'shown to' if is_shared else 'hidden from'
    log_activity(
        request.user,
        ActivityLog.Kind.DOUBT,
        f'Answer {action} {describe_record(record)}',
        f'/admin/students/{record.student_id}',
    )
    return Response(ProgressRecordSerializer(record).data)


@api_view(['GET'])
@permission_classes([CanManageStudents])
def student_progress_overview(request, pk):
    """
    GET /api/admin/students/<id>/progress/
    Totals for one student, plus done / doubt numbers for every course and topic.
    """
    student = get_object_or_404(User, pk=pk, role=User.Role.STUDENT)
    overview = build_progress_overview(student, Topic.objects.all())
    return Response({'student': StudentSerializer(student).data, **overview})


@api_view(['POST'])
@permission_classes([CanManageStudents])
def unlock_topic(request, student_id, topic_id):
    """
    POST /api/admin/students/<student_id>/topics/<topic_id>/unlock/
    {"unlock": true} -> manually unlocks the topic for the student (or false to relock)
    """
    from .models import TopicProgress
    
    student = get_object_or_404(User, pk=student_id, role=User.Role.STUDENT)
    topic = get_object_or_404(Topic, pk=topic_id)
    
    unlock = request.data.get('unlock', True)
    
    progress, _ = TopicProgress.objects.get_or_create(student=student, topic=topic)
    progress.admin_unlocked = unlock
    progress.save()
    
    action = 'unlocked' if unlock else 'relocked'
    log_activity(
        request.user,
        ActivityLog.Kind.CONTENT,
        f'Topic "{topic.title}" was {action} for {student.display_name}',
        f'/admin/students/{student.id}',
    )
    
    return Response({'message': f'Topic successfully {action}.'})
