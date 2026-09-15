from django.db.models import Count, Max, Q

from .models import QuestionProgress

EMPTY_COUNTS = {'done_count': 0, 'open_doubt_count': 0, 'resolved_doubt_count': 0}


def percent(part, whole):
    """percent(2, 3) -> 67. Returns 0 when there is nothing to divide by."""
    return round(part * 100 / whole) if whole else 0


def count_progress_by_topic(records):
    """
    Group progress rows by topic and count them in the database.

    Returns: {topic_id: {'done_count': 3, 'open_doubt_count': 1, 'resolved_doubt_count': 0}, ...}
    Topics without any rows are simply missing (use EMPTY_COUNTS for them).
    """
    rows = (
        records.order_by()  # remove Meta.ordering so GROUP BY only uses the topic
        .values('question__topic')
        .annotate(
            done_count=Count('id', filter=Q(is_done=True)),
            open_doubt_count=Count('id', filter=Q(doubt_status=QuestionProgress.DoubtStatus.OPEN)),
            resolved_doubt_count=Count('id', filter=Q(doubt_status=QuestionProgress.DoubtStatus.RESOLVED)),
        )
    )

    counts_by_topic = {}
    for row in rows:
        topic_id = row.pop('question__topic')
        counts_by_topic[topic_id] = row
    return counts_by_topic


def build_progress_overview(student, topics):
    """
    Done / doubt numbers of ONE student for every course and topic that has questions.

    topics: which topics to include (students: published courses only; admins: every course).
    Returns {'summary': {...totals...}, 'courses': [{..., 'topics': [...]}, ...]}
    """
    records = QuestionProgress.objects.filter(student=student)
    counts_by_topic = count_progress_by_topic(records)

    topics_with_questions = (
        topics.select_related('course')
        .annotate(question_count=Count('questions'))
        .filter(question_count__gt=0)
        .order_by('course__title', 'course_id', 'order', 'id')
    )

    courses = {}
    for topic in topics_with_questions:
        counts = counts_by_topic.get(topic.id, EMPTY_COUNTS)
        if topic.course_id not in courses:
            courses[topic.course_id] = {
                'id': topic.course_id,
                'title': topic.course.title,
                'description': topic.course.description,
                'category': topic.course.category,
                'level': topic.course.level,
                'is_published': topic.course.is_published,
                'question_count': 0,
                **EMPTY_COUNTS,
                'topics': [],
            }
        course = courses[topic.course_id]
        course['topics'].append(
            {'id': topic.id, 'title': topic.title, 'order': topic.order, 'question_count': topic.question_count, **counts}
        )
        course['question_count'] += topic.question_count
        for key in EMPTY_COUNTS:
            course[key] += counts[key]

    totals = records.order_by().aggregate(
        done_count=Count('id', filter=Q(is_done=True)),
        open_doubt_count=Count('id', filter=Q(doubt_status=QuestionProgress.DoubtStatus.OPEN)),
        resolved_doubt_count=Count('id', filter=Q(doubt_status=QuestionProgress.DoubtStatus.RESOLVED)),
        last_activity=Max('updated_at'),
    )

    return {
        'summary': {
            'question_count': sum(course['question_count'] for course in courses.values()),
            **totals,
        },
        'courses': list(courses.values()),
    }
