from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from courses.models import Course, Topic
from progress.models import QuestionProgress
from questions.models import Question
from users.models import User
from users.permissions import IsLmsAdmin
from videos.models import Video


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """A tiny endpoint to confirm the LMS API is running."""
    return Response({'status': 'ok', 'message': 'LMS API is running'})


@api_view(['GET'])
@permission_classes([IsLmsAdmin])
def dashboard_stats(request):
    """GET /api/admin/stats/ -> the numbers shown on the admin dashboard."""
    students = User.objects.filter(role=User.Role.STUDENT)
    return Response(
        {
            'pending_requests': students.filter(access_status=User.AccessStatus.PENDING).count(),
            'approved_students': students.filter(access_status=User.AccessStatus.APPROVED).count(),
            'courses': Course.objects.count(),
            'topics': Topic.objects.count(),
            'questions': Question.objects.count(),
            'videos': Video.objects.count(),
            'open_doubts': QuestionProgress.objects.filter(doubt_status=QuestionProgress.DoubtStatus.OPEN).count(),
            'admins': User.objects.filter(role=User.Role.ADMIN).count(),
        }
    )
