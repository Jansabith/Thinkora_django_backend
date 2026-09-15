from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from activity.models import ActivityLog
from activity.services import log_activity
from config.pagination import StandardPagination
from courses.visibility import can_manage_content, get_visible_questions, get_visible_topics
from users.permissions import CanManageContentOrReadOnly

from .filters import filter_questions, order_questions
from .models import AssignedQuestion, Question
from .serializers import AssignedQuestionSerializer, QuestionSerializer, StudentQuestionSerializer
from .services import extract_questions_from_pdf

CONTENT_LOG = ActivityLog.Kind.CONTENT


def get_question_serializer_class(user):
    """
    Content managers receive the answer. Students do NOT: hiding a button in React
    would not be enough, because anyone can read the API response in the browser.
    """
    if can_manage_content(user):
        return QuestionSerializer
    return StudentQuestionSerializer


def describe_location(question):
    """'"Lists" (Python)': where a question lives, for the activity log."""
    return f'"{question.topic.title}" ({question.topic.course.title})'


class AllQuestionsView(generics.ListAPIView):
    """
    GET /api/questions/  -> questions of every course I can see, 20 per page
    Filters: ?course=1 ?topic=4 ?difficulty=easy ?search=list
    """

    pagination_class = StandardPagination

    def get_queryset(self):
        questions = get_visible_questions(self.request.user).select_related('topic__course')
        return order_questions(filter_questions(questions, self.request.query_params))

    def get_serializer_class(self):
        return get_question_serializer_class(self.request.user)


class QuestionListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/topics/<topic_id>/questions/                  -> all questions (easy first)
    GET  /api/topics/<topic_id>/questions/?difficulty=hard  -> only one difficulty
    POST /api/topics/<topic_id>/questions/                  -> add a question (content managers only)
    """

    permission_classes = [CanManageContentOrReadOnly]

    def get_topic(self):
        return get_object_or_404(get_visible_topics(self.request.user), pk=self.kwargs['topic_id'])

    def get_queryset(self):
        questions = Question.objects.filter(topic=self.get_topic()).select_related('topic__course')
        return order_questions(filter_questions(questions, self.request.query_params), by_topic=False)

    def get_serializer_class(self):
        return get_question_serializer_class(self.request.user)

    def perform_create(self, serializer):
        topic = self.get_topic()
        question = serializer.save(topic=topic)
        log_activity(
            self.request.user,
            CONTENT_LOG,
            f'Question added to {describe_location(question)}',
            f'/admin/topics/{topic.id}/questions',
        )


class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET              /api/questions/<id>/  -> one question
    PUT/PATCH/DELETE /api/questions/<id>/  -> content managers only
    """

    permission_classes = [CanManageContentOrReadOnly]

    def get_queryset(self):
        return get_visible_questions(self.request.user).select_related('topic__course')

    def get_serializer_class(self):
        return get_question_serializer_class(self.request.user)

    def perform_update(self, serializer):
        question = serializer.save()
        log_activity(
            self.request.user,
            CONTENT_LOG,
            f'Question in {describe_location(question)} was updated',
            f'/admin/topics/{question.topic_id}/questions',
        )

    def perform_destroy(self, instance):
        log_activity(
            self.request.user,
            CONTENT_LOG,
            f'Question deleted from {describe_location(instance)}',
            f'/admin/topics/{instance.topic_id}/questions',
        )
        instance.delete()


class ExtractPdfQuestionsView(APIView):
    """
    POST /api/questions/extract-pdf/
    Expects multipart/form-data with 'file' (PDF) and 'topic' (ID).
    Content managers only.
    """
    permission_classes = [CanManageContentOrReadOnly]
    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        topic_id = request.data.get('topic')
        difficulty = request.data.get('difficulty', Question.Difficulty.MEDIUM)

        if not file_obj or not topic_id:
            return Response({'detail': 'Both file and topic are required.'}, status=400)

        topic = get_object_or_404(get_visible_topics(request.user), pk=topic_id)

        try:
            extracted_qs = extract_questions_from_pdf(file_obj)
        except Exception as e:
            return Response({'detail': f'Error reading PDF: {str(e)}'}, status=400)

        if not extracted_qs:
            return Response({'detail': 'No questions could be extracted from this PDF. Please check the formatting.'}, status=400)

        for q_data in extracted_qs:
            q_data['difficulty'] = difficulty

        return Response({'questions': extracted_qs}, status=200)

class BulkCreateQuestionsView(APIView):
    """
    POST /api/questions/bulk/
    Expects JSON body: { "topic": 1, "questions": [{ "text": "...", "answer": "...", "difficulty": "medium" }] }
    Content managers only.
    """
    permission_classes = [CanManageContentOrReadOnly]

    def post(self, request, *args, **kwargs):
        topic_id = request.data.get('topic')
        questions_data = request.data.get('questions', [])

        if not topic_id or not isinstance(questions_data, list):
            return Response({'detail': 'topic (ID) and questions (list) are required.'}, status=400)

        topic = get_object_or_404(get_visible_topics(request.user), pk=topic_id)

        created_count = 0
        order = topic.questions.count()
        questions_to_create = []

        for q_data in questions_data:
            order += 1
            questions_to_create.append(
                Question(
                    topic=topic,
                    text=q_data.get('text', ''),
                    answer=q_data.get('answer', ''),
                    order=order,
                    difficulty=q_data.get('difficulty', Question.Difficulty.MEDIUM)
                )
            )
            created_count += 1

        Question.objects.bulk_create(questions_to_create)

        log_activity(
            request.user,
            CONTENT_LOG,
            f'Bulk created {created_count} questions in "{topic.title}" ({topic.course.title})',
            f'/admin/topics/{topic.id}/questions',
        )

        return Response({'message': f'Successfully saved {created_count} questions.'}, status=201)


class StudentAssignedQuestionsView(generics.ListAPIView):
    """
    GET /api/assigned-questions/
    Returns the questions assigned to the current user (student), newest first.
    """
    serializer_class = AssignedQuestionSerializer

    def get_queryset(self):
        # Only return questions if the student is active/approved
        if not self.request.user.is_authenticated or self.request.user.access_status != 'approved':
            return AssignedQuestion.objects.none()
            
        from django.db.models import Prefetch
        from progress.models import QuestionProgress
        
        progress_prefetch = Prefetch(
            'question__progress',
            queryset=QuestionProgress.objects.filter(student=self.request.user),
            to_attr='user_progress'
        )
        
        return AssignedQuestion.objects.filter(
            student=self.request.user, 
            question__topic__course__is_published=True
        ).select_related('question__topic__course', 'assigned_by').prefetch_related(progress_prefetch)


class AdminAssignQuestionsView(APIView):
    """
    POST /api/students/<student_id>/assign-questions/
    Expects JSON body: { "question_ids": [1, 2, 3] }
    """
    permission_classes = [CanManageContentOrReadOnly]

    def get(self, request, student_id, *args, **kwargs):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        student = get_object_or_404(User, pk=student_id)
        
        assigned_ids = AssignedQuestion.objects.filter(student=student).values_list('question_id', flat=True)
        return Response({'assigned_question_ids': list(assigned_ids)})

    def post(self, request, student_id, *args, **kwargs):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        student = get_object_or_404(User, pk=student_id)
        
        question_ids = request.data.get('question_ids', [])
        if not isinstance(question_ids, list):
            return Response({'detail': 'question_ids must be a list.'}, status=400)
            
        questions = Question.objects.filter(id__in=question_ids)
        if len(questions) != len(question_ids):
            # some IDs were invalid
            pass
            
        # Ignore already assigned
        existing = set(AssignedQuestion.objects.filter(student=student, question__in=questions).values_list('question_id', flat=True))
        
        to_assign = []
        for q in questions:
            if q.id not in existing:
                to_assign.append(AssignedQuestion(student=student, question=q, assigned_by=request.user))
                
        if to_assign:
            AssignedQuestion.objects.bulk_create(to_assign)
            
        return Response({'message': f'Successfully assigned {len(to_assign)} questions.'}, status=201)

