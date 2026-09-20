"""
Numbers and chart data for the dashboards and the reports page.
Every function returns plain Python data (dicts and lists) that the views send as JSON.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta

from django.db.models import Count, Max
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone

from courses.models import Course
from courses.visibility import add_course_counts, get_visible_courses
from progress.models import QuestionProgress
from progress.summary import percent
from questions.models import Question
from users.models import User

NONE = QuestionProgress.DoubtStatus.NONE
OPEN = QuestionProgress.DoubtStatus.OPEN
RESOLVED = QuestionProgress.DoubtStatus.RESOLVED

# ---------- Admin dashboard ----------


def build_month_stat(queryset, date_field, month_begin):
    """{'total': 156, 'new_this_month': 12, 'growth_percent': 8} for one kind of thing."""
    total = queryset.count()
    new_this_month = queryset.filter(**{f'{date_field}__gte': month_begin}).count()
    before_this_month = total - new_this_month
    return {
        'total': total,
        'new_this_month': new_this_month,
        # None when there was nothing before this month (growth from 0 has no percentage).
        'growth_percent': percent(new_this_month, before_this_month) if before_this_month else None,
    }


def build_student_growth(months):
    """New students in each of the last `months` months, and the total at the end of each month."""
    now = timezone.localtime()
    current_month_number = now.year * 12 + now.month - 1
    first_month_number = current_month_number - (months - 1)
    first_year, first_month_index = divmod(first_month_number, 12)
    start = datetime(first_year, first_month_index + 1, 1, tzinfo=timezone.get_current_timezone())

    students = User.objects.filter(role=User.Role.STUDENT)
    running_total = students.filter(date_joined__lt=start).count()
    joined_per_month = {
        (row['month'].year, row['month'].month): row['count']
        for row in students.filter(date_joined__gte=start)
        .annotate(month=TruncMonth('date_joined'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by()
    }

    points = []
    for month_number in range(first_month_number, current_month_number + 1):
        year, month_index = divmod(month_number, 12)
        new_students = joined_per_month.get((year, month_index + 1), 0)
        running_total += new_students
        points.append(
            {'month': f'{year}-{month_index + 1:02d}', 'new_students': new_students, 'total_students': running_total}
        )
    return points


def build_content_overview():
    """Courses grouped by category: the 4 biggest categories, and the rest folded into "Other"."""
    rows = Course.objects.values('category').annotate(count=Count('id')).order_by('-count', 'category')
    categories = [{'name': row['category'] or 'Uncategorized', 'count': row['count']} for row in rows]
    total = sum(category['count'] for category in categories)

    # A chart stays readable with at most 5 slices.
    if len(categories) > 5:
        other_count = sum(category['count'] for category in categories[4:])
        categories = [*categories[:4], {'name': 'Other', 'count': other_count}]

    for category in categories:
        category['percent'] = percent(category['count'], total)
    return {'total_courses': total, 'categories': categories}


# ---------- Reports ----------


def build_weekly_activity(weeks):
    """Questions marked done and doubts asked in each of the last `weeks` weeks (Monday to Sunday)."""
    today = timezone.localdate()
    this_monday = today - timedelta(days=today.weekday())
    first_monday = this_monday - timedelta(weeks=weeks - 1)
    start = datetime.combine(first_monday, time.min, tzinfo=timezone.get_current_timezone())

    def count_per_week(field):
        rows = (
            QuestionProgress.objects.filter(**{f'{field}__gte': start})
            .annotate(week=TruncWeek(field))
            .values('week')
            .annotate(count=Count('id'))
            .order_by()
        )
        return {row['week'].date(): row['count'] for row in rows}

    done_per_week = count_per_week('done_at')
    doubts_per_week = count_per_week('doubt_raised_at')

    points = []
    for index in range(weeks):
        monday = first_monday + timedelta(weeks=index)
        points.append(
            {
                'week_start': monday.isoformat(),
                'questions_done': done_per_week.get(monday, 0),
                'doubts_asked': doubts_per_week.get(monday, 0),
            }
        )
    return points


def build_course_completion():
    """For every course: questions, students who started it, students who finished it, and open doubts."""
    question_counts = dict(Question.objects.order_by().values_list('topic__course').annotate(Count('id')))
    done_rows = (
        QuestionProgress.objects.filter(is_done=True)
        .order_by()
        .values('question__topic__course', 'student')
        .annotate(done=Count('id'))
    )

    started = defaultdict(int)
    completed = defaultdict(int)
    done_total = defaultdict(int)
    for row in done_rows:
        course_id = row['question__topic__course']
        started[course_id] += 1
        done_total[course_id] += row['done']
        if row['done'] >= question_counts.get(course_id, 0) > 0:
            completed[course_id] += 1

    open_doubts = dict(
        QuestionProgress.objects.filter(doubt_status=OPEN).order_by().values_list('question__topic__course').annotate(Count('id'))
    )

    result = []
    for course in Course.objects.order_by('title'):
        question_count = question_counts.get(course.id, 0)
        result.append(
            {
                'id': course.id,
                'title': course.title,
                'category': course.category,
                'is_published': course.is_published,
                'question_count': question_count,
                'students_started': started[course.id],
                'students_completed': completed[course.id],
                # Average progress of the students who started this course.
                'average_progress': percent(done_total[course.id], started[course.id] * question_count),
                'open_doubts': open_doubts.get(course.id, 0),
            }
        )
    return result


def build_top_students(limit):
    """The students who finished the most questions."""
    rows = list(
        QuestionProgress.objects.filter(is_done=True, student__role=User.Role.STUDENT)
        .order_by()
        .values('student')
        .annotate(done=Count('id'))
        .order_by('-done')[:limit]
    )
    students = User.objects.in_bulk([row['student'] for row in rows])
    return [
        {
            'id': row['student'],
            'name': students[row['student']].display_name,
            'username': students[row['student']].username,
            'done_count': row['done'],
        }
        for row in rows
    ]


def build_doubt_summary():
    """Open and answered doubts, and how many hours students wait for a reply (latest 500 answers)."""
    doubts = QuestionProgress.objects.exclude(doubt_status=NONE)
    answered = (
        doubts.filter(doubt_status=RESOLVED, doubt_raised_at__isnull=False, resolved_at__isnull=False)
        .order_by('-resolved_at')
        .values_list('doubt_raised_at', 'resolved_at')[:500]
    )
    waiting_hours = [(resolved - raised).total_seconds() / 3600 for raised, resolved in answered if resolved >= raised]
    return {
        'open': doubts.filter(doubt_status=OPEN).count(),
        'answered': doubts.filter(doubt_status=RESOLVED).count(),
        'average_reply_hours': round(sum(waiting_hours) / len(waiting_hours), 1) if waiting_hours else None,
    }


# ---------- Student dashboard ----------


def build_course_card(course):
    """A course in "Continue learning": its progress and the first topic that is not finished yet."""
    unfinished = [topic for topic in course['topics'] if topic['done_count'] < topic['question_count']]
    current_topic = unfinished[0] if unfinished else course['topics'][-1]
    return {
        'id': course['id'],
        'title': course['title'],
        'description': course['description'],
        'category': course['category'],
        'level': course['level'],
        'done_count': course['done_count'],
        'question_count': course['question_count'],
        'progress_percent': percent(course['done_count'], course['question_count']),
        'current_topic': {'id': current_topic['id'], 'title': current_topic['title']},
    }


def build_recommended_courses(student, started_course_ids, limit=4):
    """Published courses with questions that the student has not started yet, newest first."""
    courses = (
        add_course_counts(get_visible_courses(student))
        .filter(question_count__gt=0)
        .exclude(id__in=list(started_course_ids))
        .order_by('-created_at')[:limit]
    )
    return [
        {
            'id': course.id,
            'title': course.title,
            'description': course.description,
            'category': course.category,
            'level': course.level,
            'topic_count': course.topic_count,
            'question_count': course.question_count,
        }
        for course in courses
    ]


def build_student_activity(records, limit=6):
    """The student's latest actions and the teachers' replies, newest first."""
    events = []
    for row in records.select_related('question__topic').order_by('-updated_at')[:30]:
        topic = row.question.topic
        questions_link = f'/student/topics/{topic.id}/questions'
        if row.done_at:
            events.append({'type': 'done', 'message': f'Completed a question in "{topic.title}"', 'time': row.done_at, 'link': questions_link})
        if row.doubt_raised_at:
            events.append({'type': 'doubt', 'message': f'Asked a doubt in "{topic.title}"', 'time': row.doubt_raised_at, 'link': questions_link})
        if row.resolved_at:
            events.append({'type': 'reply', 'message': f'Your teacher replied to your doubt in "{topic.title}"', 'time': row.resolved_at, 'link': '/student/messages'})
        if row.answer_shared_at:
            events.append({'type': 'answer', 'message': f'Your teacher shared an answer in "{topic.title}"', 'time': row.answer_shared_at, 'link': questions_link})

    events.sort(key=lambda event: event['time'], reverse=True)
    return events[:limit]


# key, title, description, which number counts, goal
ACHIEVEMENTS = [
    ('first_step', 'First Step', 'Mark your first question as done', 'questions', 1),
    ('curious_mind', 'Curious Mind', 'Ask your first doubt', 'doubts', 1),
    ('quick_learner', 'Quick Learner', 'Complete 5 topics', 'topics', 5),
    ('problem_solver', 'Problem Solver', 'Solve 50 questions', 'questions', 50),
    ('course_master', 'Course Master', 'Finish every question of a course', 'courses', 1),
]


LEADERBOARD_PERIODS = ('week', 'last_week', 'month', 'all')


def build_leaderboard(viewer, period='all', course_id=None, limit=10):
    """
    Students ranked by the number of questions they marked as done.

    - Only active students, and only questions in published courses, are counted.
    - Equal numbers share a rank (1, 2, 2, 4). Within a tie, whoever got there first is listed first.
    - 'me' is the viewing student's own rank (None for admins, who are not on the leaderboard).
    """
    done = QuestionProgress.objects.filter(
        is_done=True,
        student__role=User.Role.STUDENT,
        student__is_active=True,
        question__topic__course__is_published=True,
    )

    now = timezone.localtime()
    this_monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == 'week':
        done = done.filter(done_at__gte=this_monday)
    elif period == 'last_week':
        # The week that just finished: Monday 00:00 up to (but not including) this Monday 00:00.
        done = done.filter(done_at__gte=this_monday - timedelta(days=7), done_at__lt=this_monday)
    elif period == 'month':
        done = done.filter(done_at__gte=now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))

    if course_id:
        done = done.filter(question__topic__course_id=course_id)

    rows = (
        done.order_by()
        .values('student')
        .annotate(done_count=Count('id'), last_done=Max('done_at'))
        .order_by('-done_count', 'last_done', 'student')
    )

    ranked = []
    rank = 0
    previous_count = None
    for position, row in enumerate(rows, start=1):
        if row['done_count'] != previous_count:
            rank = position
            previous_count = row['done_count']
        ranked.append({'rank': rank, 'student_id': row['student'], 'done_count': row['done_count']})

    shown = ranked[:limit]
    my_row = next((row for row in ranked if row['student_id'] == viewer.id), None)
    student_ids = {row['student_id'] for row in shown}
    if my_row:
        student_ids.add(my_row['student_id'])
    students = User.objects.in_bulk(student_ids)

    def describe(row):
        return {**row, 'name': students[row['student_id']].display_name, 'is_me': row['student_id'] == viewer.id}

    me = None
    if viewer.is_student:
        if my_row:
            higher_counts = [row['done_count'] for row in ranked if row['done_count'] > my_row['done_count']]
            # To move up, the student must do MORE than the group just above them.
            to_next_rank = min(higher_counts) - my_row['done_count'] + 1 if higher_counts else None
            me = {**describe(my_row), 'to_next_rank': to_next_rank}
        else:
            me = {
                'rank': None,
                'student_id': viewer.id,
                'done_count': 0,
                'name': viewer.display_name,
                'is_me': True,
                'to_next_rank': 1,
            }

    return {
        'period': period,
        'course_id': course_id,
        'ranked_count': len(ranked),
        'leaders': [describe(row) for row in shown],
        'me': me,
    }


def build_achievements(questions_done, doubts_asked, topics_completed, courses_completed):
    numbers = {
        'questions': questions_done,
        'doubts': doubts_asked,
        'topics': topics_completed,
        'courses': courses_completed,
    }
    return [
        {
            'key': key,
            'title': title,
            'description': description,
            'current': min(numbers[counted], goal),
            'goal': goal,
            'earned': numbers[counted] >= goal,
        }
        for key, title, description, counted, goal in ACHIEVEMENTS
    ]
