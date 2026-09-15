"""
Student views: a student marks questions as done, bookmarks them, asks doubts,
and sees their own progress, messages, calendar and certificates.
Only students can use these (admins do not have progress).
"""

from datetime import date

from django.db.models import Count, Exists, Max, OuterRef
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from config.pagination import StandardPagination
from courses.visibility import get_visible_courses, get_visible_questions, get_visible_topics
from questions.filters import filter_questions, order_questions
from questions.serializers import StudentQuestionSerializer
from users.permissions import IsStudent

from .models import QuestionProgress
from .serializers import MyMessageSerializer, MyProgressSerializer, ProgressUpdateSerializer
from .summary import build_progress_overview, count_progress_by_topic

NONE = QuestionProgress.DoubtStatus.NONE
OPEN = QuestionProgress.DoubtStatus.OPEN


@api_view(['GET'])
@permission_classes([IsStudent])
def my_topic_progress(request, topic_id):
    """GET /api/progress/topics/<topic_id>/ -> my progress on this topic's questions."""
    topic = get_object_or_404(get_visible_topics(request.user), pk=topic_id)
    records = QuestionProgress.objects.filter(student=request.user, question__topic=topic).select_related('question')
    return Response(MyProgressSerializer(records, many=True).data)


@api_view(['GET'])
@permission_classes([IsStudent])
def my_course_progress(request, course_id):
    """GET /api/progress/courses/<course_id>/ -> how many questions I finished, per topic."""
    course = get_object_or_404(get_visible_courses(request.user), pk=course_id)
    records = QuestionProgress.objects.filter(student=request.user, question__topic__course=course)
    counts_by_topic = count_progress_by_topic(records)

    return Response(
        {
            'done_count': sum(counts['done_count'] for counts in counts_by_topic.values()),
            'open_doubt_count': sum(counts['open_doubt_count'] for counts in counts_by_topic.values()),
            'topics': counts_by_topic,
        }
    )


@api_view(['PATCH'])
@permission_classes([IsStudent])
def update_my_progress(request, question_id):
    """
    PATCH /api/progress/questions/<question_id>/
      {"is_done": true}                                  -> mark as done
      {"is_bookmarked": true}                            -> bookmark
      {"doubt_status": "open", "doubt_message": "..."}   -> ask a doubt
      {"doubt_status": "none"}                           -> withdraw / clear the doubt
    """
    question = get_object_or_404(get_visible_questions(request.user), pk=question_id)
    serializer = ProgressUpdateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    changes = serializer.validated_data

    # The first click on a question creates the student's row for it.
    progress, _created = QuestionProgress.objects.get_or_create(student=request.user, question=question)

    if 'is_done' in changes:
        progress.set_done(changes['is_done'])

    if 'is_bookmarked' in changes:
        progress.is_bookmarked = changes['is_bookmarked']

    if changes.get('doubt_status') == OPEN:
        progress.raise_doubt(changes.get('doubt_message', ''))
    elif changes.get('doubt_status') == NONE:
        progress.clear_doubt()

    progress.save()
    return Response(MyProgressSerializer(progress).data)


@api_view(['GET'])
@permission_classes([IsStudent])
def my_overview(request):
    """GET /api/progress/overview/ -> my done / doubt numbers for every course and topic."""
    return Response(build_progress_overview(request.user, get_visible_topics(request.user)))


class PracticeQuestionListView(generics.ListAPIView):
    """
    GET /api/progress/practice/  -> every question I can practise, with my progress, 20 per page
    Filters: ?course=1 ?topic=4 ?difficulty=easy ?search=list
             ?status=todo | done | doubt | bookmarked
    """

    permission_classes = [IsStudent]
    pagination_class = StandardPagination

    def get_queryset(self):
        user = self.request.user
        params = self.request.query_params
        questions = filter_questions(get_visible_questions(user).select_related('topic__course'), params)

        status = params.get('status')
        if status:
            # Exists(...) asks the database "does MY progress row for this question match?"
            my_rows = QuestionProgress.objects.filter(student=user, question=OuterRef('pk'))
            status_filters = {
                'done': Exists(my_rows.filter(is_done=True)),
                'todo': ~Exists(my_rows.filter(is_done=True)),
                'doubt': Exists(my_rows.exclude(doubt_status=NONE)),
                'bookmarked': Exists(my_rows.filter(is_bookmarked=True)),
            }
            if status not in status_filters:
                raise ValidationError({'status': f'Choose one of: {", ".join(status_filters)}.'})
            questions = questions.filter(status_filters[status])

        return order_questions(questions)

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())

        # One extra query for the progress of the questions on this page only.
        progress_by_question = {
            row.question_id: row
            for row in QuestionProgress.objects.filter(student=request.user, question__in=page).select_related('question')
        }

        results = []
        for question in page:
            item = StudentQuestionSerializer(question).data
            row = progress_by_question.get(question.id)
            item['progress'] = MyProgressSerializer(row).data if row else None
            results.append(item)
        return self.get_paginated_response(results)


@api_view(['GET'])
@permission_classes([IsStudent])
def my_messages(request):
    """GET /api/progress/messages/ -> my doubts and my teachers' replies (unread replies first)."""
    rows = (
        QuestionProgress.objects.filter(student=request.user)
        .exclude(doubt_status=NONE)
        .select_related('question__topic__course', 'resolved_by')
        .order_by('reply_seen', '-updated_at')
    )
    return Response(MyMessageSerializer(rows, many=True).data)


@api_view(['POST'])
@permission_classes([IsStudent])
def mark_messages_seen(request):
    """POST /api/progress/messages/mark-seen/ -> all replies now count as read."""
    # update() does not change updated_at, so reading a reply is not counted as "activity".
    updated = QuestionProgress.objects.filter(student=request.user, reply_seen=False).update(reply_seen=True)
    return Response({'updated': updated})


@api_view(['GET'])
@permission_classes([IsStudent])
def my_certificates(request):
    """GET /api/progress/certificates/ -> courses where I finished EVERY practice question."""
    student = request.user
    overview = build_progress_overview(student, get_visible_topics(student))
    completed_courses = [course for course in overview['courses'] if course['done_count'] >= course['question_count']]

    finished_at = dict(
        QuestionProgress.objects.filter(
            student=student,
            is_done=True,
            question__topic__course_id__in=[course['id'] for course in completed_courses],
        )
        .order_by()
        .values_list('question__topic__course')
        .annotate(last_done=Max('done_at'))
    )

    return Response(
        [
            {
                'course_id': course['id'],
                'course_title': course['title'],
                'category': course['category'],
                'level': course['level'],
                'question_count': course['question_count'],
                'topic_count': len(course['topics']),
                'completed_at': finished_at.get(course['id']),
                'student_name': student.display_name,
                'certificate_id': f'TK-{student.id:05d}-{course["id"]:04d}',
            }
            for course in completed_courses
        ]
    )


@api_view(['GET'])
@permission_classes([IsStudent])
def my_calendar(request):
    """GET /api/progress/calendar/?year=2026&month=9 -> how many questions I finished on each day."""
    today = timezone.localdate()
    try:
        year = int(request.query_params.get('year', today.year))
        month = int(request.query_params.get('month', today.month))
        date(year, month, 1)  # raises ValueError for month=13 and similar
    except ValueError:
        raise ValidationError({'month': 'Use a real year and month, for example ?year=2026&month=9.'})

    rows = (
        QuestionProgress.objects.filter(student=request.user, done_at__year=year, done_at__month=month)
        .annotate(day=TruncDate('done_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by()
    )
    return Response({'year': year, 'month': month, 'days': {row['day'].isoformat(): row['count'] for row in rows}})
