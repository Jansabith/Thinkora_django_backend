"""
Management views:
- Students: used by Admins with student rights and by the Main Admin.
- Admins:   used only by the Main Admin.
Every change is written to the activity log.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from activity.models import ActivityLog
from activity.services import log_activity

from .models import User
from .permissions import CanManageStudents, IsMainAdmin
from .serializers import AdminAccountSerializer, StudentSerializer, StudentUpdateSerializer

STUDENT_LOG = ActivityLog.Kind.STUDENT
ADMIN_LOG = ActivityLog.Kind.ADMIN

# ---------- Students ----------


class StudentListView(generics.ListAPIView):
    """
    GET /api/admin/students/
    Optional filters: ?status=pending  and  ?search=ali
    """

    serializer_class = StudentSerializer
    permission_classes = [CanManageStudents]

    def get_queryset(self):
        students = (
            User.objects.filter(role=User.Role.STUDENT)
            .select_related('reviewed_by')
            .order_by('-date_joined')
        )

        access_status = self.request.query_params.get('status')
        if access_status:
            students = students.filter(access_status=access_status)

        search = self.request.query_params.get('search', '').strip()
        if search:
            students = students.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
            )
        return students


class StudentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/admin/students/<id>/  -> one student
    PATCH  /api/admin/students/<id>/  -> change name, email, or set a new password
    DELETE /api/admin/students/<id>/  -> delete the student account
    """

    permission_classes = [CanManageStudents]
    queryset = User.objects.filter(role=User.Role.STUDENT)

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return StudentUpdateSerializer
        return StudentSerializer

    def perform_update(self, serializer):
        student = serializer.save()
        log_activity(
            self.request.user,
            STUDENT_LOG,
            f'Account details of {student.display_name} were updated',
            f'/admin/students/{student.id}',
        )

    def perform_destroy(self, instance):
        log_activity(self.request.user, STUDENT_LOG, f'Student {instance.display_name} was deleted')
        instance.delete()


@api_view(['POST'])
@permission_classes([CanManageStudents])
def approve_student(request, pk):
    """POST /api/admin/students/<id>/approve/ -> the student can log in."""
    student = get_object_or_404(User, pk=pk, role=User.Role.STUDENT)
    student.is_active = True
    student.access_status = User.AccessStatus.APPROVED
    student.reviewed_by = request.user
    student.reviewed_at = timezone.now()
    student.save()
    
    course_ids = request.data.get('allowed_courses')
    if isinstance(course_ids, list):
        student.allowed_courses.set(course_ids)

    log_activity(request.user, STUDENT_LOG, f'{student.display_name} was approved', f'/admin/students/{student.id}')
    return Response(StudentSerializer(student).data)


@api_view(['POST'])
@permission_classes([CanManageStudents])
def reject_student(request, pk):
    """
    POST /api/admin/students/<id>/reject/
    Rejects a pending request, or removes access from an approved student.
    """
    student = get_object_or_404(User, pk=pk, role=User.Role.STUDENT)
    had_access = student.access_status == User.AccessStatus.APPROVED

    student.is_active = False
    student.access_status = User.AccessStatus.REJECTED
    student.reviewed_by = request.user
    student.reviewed_at = timezone.now()
    student.save()

    # If the student is logged in somewhere, log them out immediately.
    Token.objects.filter(user=student).delete()

    message = f'Access removed for {student.display_name}' if had_access else f'Request from {student.display_name} was rejected'
    log_activity(request.user, STUDENT_LOG, message, f'/admin/students/{student.id}')
    return Response(StudentSerializer(student).data)


# ---------- Admins (Main Admin only) ----------


class AdminListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/main-admin/admins/  -> list admins
    POST /api/main-admin/admins/  -> create an admin
    """

    serializer_class = AdminAccountSerializer
    permission_classes = [IsMainAdmin]
    queryset = User.objects.filter(role=User.Role.ADMIN).order_by('username')

    def perform_create(self, serializer):
        admin = serializer.save()
        log_activity(self.request.user, ADMIN_LOG, f'Admin account for {admin.display_name} was created', '/main-admin/admins')


class AdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/main-admin/admins/<id>/  -> one admin
    PATCH  /api/main-admin/admins/<id>/  -> change details, rights, enable/disable
    DELETE /api/main-admin/admins/<id>/  -> delete the admin account
    """

    serializer_class = AdminAccountSerializer
    permission_classes = [IsMainAdmin]
    queryset = User.objects.filter(role=User.Role.ADMIN)

    def perform_update(self, serializer):
        was_active = serializer.instance.is_active
        admin = serializer.save()
        if was_active and not admin.is_active:
            message = f'Admin {admin.display_name} was disabled'
        elif admin.is_active and not was_active:
            message = f'Admin {admin.display_name} was enabled'
        else:
            message = f'Admin account of {admin.display_name} was updated'
        log_activity(self.request.user, ADMIN_LOG, message, '/main-admin/admins')

    def perform_destroy(self, instance):
        log_activity(self.request.user, ADMIN_LOG, f'Admin {instance.display_name} was deleted', '/main-admin/admins')
        instance.delete()
