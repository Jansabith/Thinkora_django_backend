"""
Dashboards, reports, notifications and search.
Each dashboard is ONE request, so the page loads everything at once.
"""

from django.db.models import Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from activity.models import ActivityLog
from activity.serializers import ActivityLogSerializer
from courses.models import Course, Topic
from courses.visibility import get_visible_courses, get_visible_questions, get_visible_topics
from progress.models import QuestionProgress
from progress.summary import build_progress_overview, percent
from questions.filters import read_id
from questions.models import Question
from users.models import User
from users.permissions import CanManageStudents, IsLmsAdmin, IsStudent
from users.serializers import StudentSerializer
from videos.models import Video

from .stats import (
    LEADERBOARD_PERIODS,
    build_achievements,
    build_leaderboard,
    build_content_overview,
    build_course_card,
    build_course_completion,
    build_doubt_summary,
    build_month_stat,
    build_recommended_courses,
    build_student_activity,
    build_student_growth,
    build_top_students,
    build_weekly_activity,
)

OPEN = QuestionProgress.DoubtStatus.OPEN
RESOLVED = QuestionProgress.DoubtStatus.RESOLVED
GROWTH_RANGES = (3, 6, 12)


@api_view(['GET'])
@permission_classes([IsStudent])
def student_dashboard(request):
    """GET /api/student/dashboard/ -> everything the student dashboard shows."""
    student = request.user
    overview = build_progress_overview(student, get_visible_topics(student))
    courses = overview['courses']
    summary = overview['summary']

    topics = [topic for course in courses for topic in course['topics']]
    topics_completed = sum(1 for topic in topics if topic.get('is_completed', False))
    topics_in_progress = sum(1 for topic in topics if not topic.get('is_completed', False) and topic.get('done_count', 0) > 0)
    courses_completed = sum(1 for course in courses if course['question_count'] > 0 and course['done_count'] >= course['question_count'])

    records = QuestionProgress.objects.filter(student=student)
    last_activity_by_course = dict(
        records.order_by().values_list('question__topic__course').annotate(last=Max('updated_at'))
    )
    started_courses = sorted(
        (course for course in courses if course['id'] in last_activity_by_course),
        key=lambda course: last_activity_by_course[course['id']],
        reverse=True,
    )

    return Response(
        {
            'stats': {
                'started_courses': len(started_courses),
                'topics_completed': topics_completed,
                'topic_count': len(topics),
                'questions_solved': summary['done_count'],
                'question_count': summary['question_count'],
                'overall_progress': percent(summary['done_count'], summary['question_count']),
            },
            'topic_progress': {
                'completed': topics_completed,
                'in_progress': topics_in_progress,
                'not_started': len(topics) - topics_completed - topics_in_progress,
            },
            # Courses the student worked on most recently (or the first courses, for a new student).
            'continue_learning': [build_course_card(course) for course in (started_courses or courses)[:3]],
            'recommended': build_recommended_courses(student, last_activity_by_course.keys()),
            'recent_activity': build_student_activity(records),
            'achievements': build_achievements(
                questions_done=summary['done_count'],
                doubts_asked=records.exclude(doubt_status=QuestionProgress.DoubtStatus.NONE).count(),
                topics_completed=topics_completed,
                courses_completed=courses_completed,
            ),
            'unread_messages': records.filter(reply_seen=False).count(),
            'open_doubts': summary['open_doubt_count'],
        }
    )


@api_view(['GET'])
@permission_classes([IsLmsAdmin])
def admin_dashboard(request):
    """GET /api/admin/dashboard/ -> everything the admin dashboard shows."""
    admin = request.user
    month_begin = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    students = User.objects.filter(role=User.Role.STUDENT)
    pending_students = students.filter(access_status=User.AccessStatus.PENDING)

    return Response(
        {
            'stats': {
                'students': build_month_stat(students, 'date_joined', month_begin),
                'courses': build_month_stat(Course.objects.all(), 'created_at', month_begin),
                'topics': build_month_stat(Topic.objects.all(), 'created_at', month_begin),
                'questions': build_month_stat(Question.objects.all(), 'created_at', month_begin),
                'videos': build_month_stat(Video.objects.all(), 'created_at', month_begin),
            },
            'pending_requests': pending_students.count(),
            'open_doubts': QuestionProgress.objects.filter(doubt_status=OPEN).count(),
            'admins': User.objects.filter(role=User.Role.ADMIN).count(),
            'student_growth': build_student_growth(6),
            'content_overview': build_content_overview(),
            # Student details are only sent to admins who may manage students.
            'recent_requests': (
                StudentSerializer(pending_students.order_by('-date_joined')[:5], many=True).data
                if admin.may_manage_students
                else []
            ),
            'recent_activity': ActivityLogSerializer(ActivityLog.objects.select_related('actor')[:8], many=True).data,
        }
    )


@api_view(['GET'])
@permission_classes([IsLmsAdmin])
def student_growth(request):
    """GET /api/admin/student-growth/?months=12 -> new and total students per month (3, 6 or 12 months)."""
    months = request.query_params.get('months', '6')
    if not months.isdigit() or int(months) not in GROWTH_RANGES:
        raise ValidationError({'months': 'Choose 3, 6 or 12.'})
    return Response(build_student_growth(int(months)))


@api_view(['GET'])
@permission_classes([CanManageStudents])
def reports(request):
    """GET /api/admin/reports/ -> growth, weekly activity, course completion, top students and doubts."""
    return Response(
        {
            'student_growth': build_student_growth(12),
            'weekly_activity': build_weekly_activity(8),
            'course_completion': build_course_completion(),
            'top_students': build_top_students(5),
            'doubts': build_doubt_summary(),
        }
    )


@api_view(['GET'])
def notifications(request):
    """
    GET /api/notifications/ -> the bell menu and the numbers on the sidebar.
    Students: unread replies. Admins with student rights: waiting requests and open doubts.
    """
    user = request.user
    badges = {}
    items = []

    if user.is_student:
        unread_replies = (
            QuestionProgress.objects.filter(student=user, doubt_status=RESOLVED, reply_seen=False)
            .select_related('question__topic')
            .order_by('-resolved_at')
        )
        badges['unread_messages'] = unread_replies.count()
        for row in unread_replies[:5]:
            items.append(
                {
                    'id': f'reply-{row.id}',
                    'kind': 'reply',
                    'title': 'Your teacher replied',
                    'message': f'Your doubt in "{row.question.topic.title}"',
                    'link': '/student/messages',
                    'time': row.resolved_at,
                }
            )

    elif user.may_manage_students:
        pending = User.objects.filter(role=User.Role.STUDENT, access_status=User.AccessStatus.PENDING)
        open_doubts = QuestionProgress.objects.filter(doubt_status=OPEN)
        badges['pending_requests'] = pending.count()
        badges['open_doubts'] = open_doubts.count()

        if badges['pending_requests']:
            items.append(
                {
                    'id': 'pending-requests',
                    'kind': 'request',
                    'title': f'{badges["pending_requests"]} student request(s) waiting',
                    'message': 'Approve or reject new students.',
                    'link': '/admin/requests',
                    'time': pending.aggregate(latest=Max('date_joined'))['latest'],
                }
            )
        if badges['open_doubts']:
            items.append(
                {
                    'id': 'open-doubts',
                    'kind': 'doubt',
                    'title': f'{badges["open_doubts"]} open doubt(s)',
                    'message': 'Students are waiting for your reply.',
                    'link': '/admin/doubts',
                    'time': open_doubts.aggregate(latest=Max('doubt_raised_at'))['latest'],
                }
            )

    return Response({'count': sum(badges.values()), 'badges': badges, 'items': items})


@api_view(['GET'])
def search(request):
    """
    GET /api/search/?q=list -> up to 5 matching courses, topics and questions (and students, for admins).
    Everyone only finds what they are allowed to see.
    """
    query = request.query_params.get('q', '').strip()
    results = {'courses': [], 'topics': [], 'questions': [], 'students': []}
    if len(query) < 2:
        return Response(results)

    user = request.user
    courses = get_visible_courses(user).filter(Q(title__icontains=query) | Q(category__icontains=query))[:5]
    results['courses'] = [{'id': course.id, 'title': course.title, 'category': course.category} for course in courses]

    topics = get_visible_topics(user).filter(title__icontains=query)[:5]
    results['topics'] = [
        {'id': topic.id, 'title': topic.title, 'course_id': topic.course_id, 'course_title': topic.course.title}
        for topic in topics
    ]

    questions = get_visible_questions(user).select_related('topic__course').filter(text__icontains=query)[:5]
    results['questions'] = [
        {
            'id': question.id,
            'text': question.text[:120],
            'difficulty': question.difficulty,
            'topic_id': question.topic_id,
            'topic_title': question.topic.title,
            'course_title': question.topic.course.title,
        }
        for question in questions
    ]

    if user.may_manage_students:
        students = User.objects.filter(role=User.Role.STUDENT).filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )[:5]
        results['students'] = [
            {'id': student.id, 'name': student.display_name, 'username': student.username, 'access_status': student.access_status}
            for student in students
        ]

    return Response(results)


@api_view(['GET'])
def leaderboard(request):
    """
    GET /api/leaderboard/?period=week|month|all&course=1&limit=10
    Students ranked by questions marked as done. Every logged-in user may see it.
    """
    period = request.query_params.get('period', 'all')
    if period not in LEADERBOARD_PERIODS:
        raise ValidationError({'period': 'Choose week, month or all.'})

    course_id = read_id(request.query_params, 'course')
    if course_id:
        # Students may only filter by courses they can see.
        get_object_or_404(get_visible_courses(request.user), pk=course_id)

    limit = request.query_params.get('limit', '10')
    if not limit.isdigit() or not 1 <= int(limit) <= 50:
        raise ValidationError({'limit': 'Choose a number from 1 to 50.'})

    return Response(build_leaderboard(request.user, period, course_id, int(limit)))
