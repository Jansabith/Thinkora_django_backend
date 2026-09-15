from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User
from users.testing import create_user, log_in

from .models import ActivityLog
from .services import log_activity


class ActivityLogTests(APITestCase):
    def setUp(self):
        self.admin = create_user('teacher', role=User.Role.ADMIN, first_name='Priya')
        self.student = create_user('ali')

    def test_request_access_is_logged(self):
        self.client.post(
            '/api/auth/request-access/',
            {
                'first_name': 'Omar',
                'last_name': 'Hassan',
                'email': 'omar@example.com',
                'username': 'omar',
                'password': 'Learn-Python-2026',
                'confirm_password': 'Learn-Python-2026',
            },
            format='json',
        )
        log = ActivityLog.objects.get()
        self.assertEqual(log.message, 'New access request from Omar Hassan')
        self.assertEqual(log.kind, ActivityLog.Kind.STUDENT)

    def test_approving_a_student_is_logged_with_the_admin(self):
        pending = create_user(
            'newbie', first_name='Fatima', access_status=User.AccessStatus.PENDING, is_active=False
        )
        log_in(self.client, self.admin)

        self.client.post(f'/api/admin/students/{pending.pk}/approve/')

        log = ActivityLog.objects.get()
        self.assertEqual(log.message, 'Fatima was approved')
        self.assertEqual(log.actor, self.admin)
        self.assertEqual(log.link, f'/admin/students/{pending.pk}')

    def test_creating_content_is_logged(self):
        log_in(self.client, self.admin)
        self.client.post('/api/courses/', {'title': 'HTML'}, format='json')
        self.assertEqual(ActivityLog.objects.get().message, 'Course "HTML" was created')

    def test_admins_can_read_the_log_but_students_cannot(self):
        log_activity(self.admin, ActivityLog.Kind.CONTENT, 'Topic "Lists" was updated')

        log_in(self.client, self.admin)
        response = self.client.get('/api/admin/activity/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['actor_name'], 'Priya')

        log_in(self.client, self.student)
        self.assertEqual(self.client.get('/api/admin/activity/').status_code, status.HTTP_403_FORBIDDEN)

    def test_filter_by_kind(self):
        log_activity(self.admin, ActivityLog.Kind.CONTENT, 'Content change')
        log_activity(self.admin, ActivityLog.Kind.ADMIN, 'Admin change')
        log_in(self.client, self.admin)

        response = self.client.get('/api/admin/activity/?kind=admin')

        self.assertEqual([log['message'] for log in response.data['results']], ['Admin change'])
        self.assertEqual(self.client.get('/api/admin/activity/?kind=wrong').status_code, status.HTTP_400_BAD_REQUEST)
