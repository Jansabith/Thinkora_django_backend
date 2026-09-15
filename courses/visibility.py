"""
Who can see which courses and topics, and the numbers shown next to them.

Content managers (Main Admin, or Admins with content rights) see everything,
including unpublished (draft) courses. Everyone else sees only published courses.
"""

from django.db.models import Count, Q

from questions.models import Question

from .models import Course, Topic


def can_manage_content(user):
    # getattr(): a not-logged-in AnonymousUser has no 'may_manage_content' attribute.
    return getattr(user, 'may_manage_content', False)


def get_visible_courses(user):
    courses = Course.objects.all()
    if not can_manage_content(user):
        courses = courses.filter(is_published=True)
        if user.is_authenticated and user.is_student:
            courses = courses.filter(id__in=user.allowed_courses.all())
    return courses


def get_visible_topics(user):
    topics = Topic.objects.select_related('course')
    if not can_manage_content(user):
        topics = topics.filter(course__is_published=True)
        if user.is_authenticated and user.is_student:
            topics = topics.filter(course__id__in=user.allowed_courses.all())
    return topics


def get_visible_questions(user):
    questions = Question.objects.all()
    if not can_manage_content(user):
        questions = questions.filter(topic__course__is_published=True)
        if user.is_authenticated and user.is_student:
            questions = questions.filter(topic__course__id__in=user.allowed_courses.all())
    return questions


# annotate() asks the DATABASE to count, in the same query that loads the rows.
# That stays fast with many courses (instead of one extra query per course).
# distinct=True avoids double counting when two different relations are joined.
#
# Counting uses GROUP BY, and then Django ignores the model's Meta.ordering,
# so we sort again with order_by().


def add_course_counts(courses):
    return courses.annotate(
        topic_count=Count('topics', distinct=True),
        question_count=Count('topics__questions', distinct=True),
        video_count=Count('topics__videos', distinct=True),
    ).order_by('title')


def add_topic_counts(topics):
    return topics.annotate(
        question_count=Count('questions', distinct=True),
        easy_count=Count('questions', filter=Q(questions__difficulty='easy'), distinct=True),
        medium_count=Count('questions', filter=Q(questions__difficulty='medium'), distinct=True),
        hard_count=Count('questions', filter=Q(questions__difficulty='hard'), distinct=True),
        video_count=Count('videos', distinct=True),
    ).order_by('order', 'id')
