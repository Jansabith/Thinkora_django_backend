"""Filtering and sorting of questions, shared by the question lists and the student Practice page."""

from django.db.models import Case, Value, When
from rest_framework.exceptions import ValidationError

from .models import Question

# Used to sort Easy first, then Medium, then Hard.
DIFFICULTY_RANK = Case(
    When(difficulty=Question.Difficulty.EASY, then=Value(0)),
    When(difficulty=Question.Difficulty.MEDIUM, then=Value(1)),
    default=Value(2),
)


def read_id(params, name):
    """Read ?course=3 from the URL as the number 3 (None when missing)."""
    value = params.get(name)
    if not value:
        return None
    if not value.isdigit():
        raise ValidationError({name: 'Must be a number.'})
    return int(value)


def filter_questions(questions, params):
    """Apply the URL filters ?course= ?topic= ?difficulty= ?search=."""
    course_id = read_id(params, 'course')
    if course_id:
        questions = questions.filter(topic__course_id=course_id)

    topic_id = read_id(params, 'topic')
    if topic_id:
        questions = questions.filter(topic_id=topic_id)

    difficulty = params.get('difficulty')
    if difficulty:
        if difficulty not in Question.Difficulty.values:
            raise ValidationError({'difficulty': f'Choose one of: {", ".join(Question.Difficulty.values)}.'})
        questions = questions.filter(difficulty=difficulty)

    search = params.get('search', '').strip()
    if search:
        questions = questions.filter(text__icontains=search)

    return questions


def order_questions(questions, by_topic=True):
    """Easy first, then Medium, then Hard. by_topic: keep questions of the same topic together."""
    questions = questions.alias(difficulty_rank=DIFFICULTY_RANK)
    if by_topic:
        return questions.order_by('topic__course__title', 'topic__order', 'topic_id', 'difficulty_rank', 'order', 'id')
    return questions.order_by('difficulty_rank', 'order', 'id')
