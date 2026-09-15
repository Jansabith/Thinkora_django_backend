from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import User
from .testing import TEST_PASSWORD, create_user, log_in


class RequestAccessTests(APITestCase):
    url = '/api/auth/request-access/'

    def valid_data(self, **changes):
        data = {
            'first_name': 'Ali',
            'last_name': 'Khan',
            'email': 'ali@example.com',
            'username': 'ali',
            'password': 'Learn-Python-2026',
            'confirm_password': 'Learn-Python-2026',
            'request_message': 'I am in class 10A.',
        }
        data.update(changes)
        return data

    def test_request_creates_inactive_pending_student(self):
        response = self.client.post(self.url, self.valid_data(), format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        student = User.objects.get(username='ali')
        self.assertEqual(student.role, User.Role.STUDENT)
        self.assertEqual(student.access_status, User.AccessStatus.PENDING)
        self.assertFalse(student.is_active)
        # The password is stored as a hash, never as plain text.
        self.assertNotEqual(student.password, 'Learn-Python-2026')
        self.assertTrue(student.check_password('Learn-Python-2026'))

    def test_passwords_must_match(self):
        response = self.client.post(
            self.url, self.valid_data(confirm_password='Different-2026'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_password', response.data)

    def test_email_must_be_unique(self):
        create_user('existing', email='ali@example.com')
        response = self.client.post(self.url, self.valid_data(email='ALI@example.com'), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_weak_password_is_rejected(self):
        response = self.client.post(
            self.url, self.valid_data(password='123', confirm_password='123'), format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)


class LoginTests(APITestCase):
    url = '/api/auth/login/'

    def login(self, username, password=TEST_PASSWORD):
        return self.client.post(self.url, {'username': username, 'password': password}, format='json')

    def test_approved_student_gets_token(self):
        student = create_user('ali')
        response = self.login('ali')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['token'], Token.objects.get(user=student).key)
        self.assertEqual(response.data['user']['role'], 'student')
        self.assertNotIn('password', response.data['user'])

    def test_pending_student_cannot_log_in(self):
        create_user('newbie', access_status=User.AccessStatus.PENDING, is_active=False)
        response = self.login('newbie')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('pending', response.data['detail'])

    def test_rejected_student_cannot_log_in(self):
        create_user('blocked', access_status=User.AccessStatus.REJECTED, is_active=False)
        response = self.login('blocked')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('rejected', response.data['detail'])

    def test_wrong_password_is_refused(self):
        create_user('ali')
        response = self.login('ali', 'wrong-password')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('token', response.data)

    def test_wrong_password_does_not_reveal_pending_status(self):
        create_user('newbie', access_status=User.AccessStatus.PENDING, is_active=False)
        response = self.login('newbie', 'wrong-password')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('pending', response.data['detail'])

    def test_me_requires_login(self):
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_logged_in_user(self):
        log_in(self.client, create_user('ali'))
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'ali')

    def test_logout_deletes_token(self):
        student = create_user('ali')
        log_in(self.client, student)

        response = self.client.post('/api/auth/logout/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Token.objects.filter(user=student).exists())
        self.assertEqual(self.client.get('/api/auth/me/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_createsuperuser_makes_a_main_admin(self):
        boss = User.objects.create_superuser('boss', 'boss@example.com', TEST_PASSWORD)
        self.assertEqual(boss.role, User.Role.MAIN_ADMIN)
        self.assertEqual(boss.access_status, User.AccessStatus.APPROVED)
        self.assertEqual(self.login('boss').status_code, status.HTTP_200_OK)

    def test_change_password_gives_new_token(self):
        student = create_user('ali')
        log_in(self.client, student)
        old_token = Token.objects.get(user=student).key

        response = self.client.post(
            '/api/auth/change-password/',
            {'current_password': TEST_PASSWORD, 'new_password': 'Brand-New-Pass-2026'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotEqual(response.data['token'], old_token)
        student.refresh_from_db()
        self.assertTrue(student.check_password('Brand-New-Pass-2026'))


class StudentManagementTests(APITestCase):
    def setUp(self):
        self.admin = create_user('teacher', role=User.Role.ADMIN)
        self.pending_student = create_user(
            'newbie', access_status=User.AccessStatus.PENDING, is_active=False
        )

    def test_anonymous_user_gets_401(self):
        response = self.client.get('/api/admin/students/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_gets_403(self):
        log_in(self.client, create_user('ali'))
        response = self.client.get('/api/admin/students/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_sees_pending_requests(self):
        create_user('ali')  # approved student, must not appear
        log_in(self.client, self.admin)

        response = self.client.get('/api/admin/students/?status=pending')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([student['username'] for student in response.data], ['newbie'])

    def test_admin_can_approve_student(self):
        log_in(self.client, self.admin)
        response = self.client.post(f'/api/admin/students/{self.pending_student.pk}/approve/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_student.refresh_from_db()
        self.assertTrue(self.pending_student.is_active)
        self.assertEqual(self.pending_student.access_status, User.AccessStatus.APPROVED)
        self.assertEqual(self.pending_student.reviewed_by, self.admin)

        # The student can now log in.
        self.client.credentials()
        login_response = self.client.post(
            '/api/auth/login/', {'username': 'newbie', 'password': TEST_PASSWORD}, format='json'
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_rejecting_student_logs_them_out(self):
        student = create_user('ali')
        Token.objects.create(user=student)
        log_in(self.client, self.admin)

        response = self.client.post(f'/api/admin/students/{student.pk}/reject/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student.refresh_from_db()
        self.assertFalse(student.is_active)
        self.assertEqual(student.access_status, User.AccessStatus.REJECTED)
        self.assertFalse(Token.objects.filter(user=student).exists())

    def test_admin_without_student_rights_gets_403(self):
        limited_admin = create_user('limited', role=User.Role.ADMIN, can_manage_students=False)
        log_in(self.client, limited_admin)
        response = self.client.get('/api/admin/students/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_edit_student_and_set_password(self):
        student = create_user('ali')
        Token.objects.create(user=student)
        log_in(self.client, self.admin)

        response = self.client.patch(
            f'/api/admin/students/{student.pk}/',
            {'first_name': 'Ali', 'email': 'ali.new@example.com', 'password': 'Fresh-Start-2026'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'ali.new@example.com')
        student.refresh_from_db()
        self.assertTrue(student.check_password('Fresh-Start-2026'))
        self.assertFalse(Token.objects.filter(user=student).exists())

    def test_editing_a_student_cannot_change_access(self):
        log_in(self.client, self.admin)
        self.client.patch(
            f'/api/admin/students/{self.pending_student.pk}/',
            {'access_status': 'approved', 'is_active': True},
            format='json',
        )
        self.pending_student.refresh_from_db()
        self.assertFalse(self.pending_student.is_active)
        self.assertEqual(self.pending_student.access_status, User.AccessStatus.PENDING)

    def test_approve_only_works_for_students(self):
        log_in(self.client, self.admin)
        response = self.client.post(f'/api/admin/students/{self.admin.pk}/approve/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminManagementTests(APITestCase):
    url = '/api/main-admin/admins/'

    def setUp(self):
        self.main_admin = create_user('boss', role=User.Role.MAIN_ADMIN)

    def test_main_admin_can_create_admin(self):
        log_in(self.client, self.main_admin)
        response = self.client.post(
            self.url,
            {
                'username': 'teacher2',
                'email': 'teacher2@example.com',
                'first_name': 'Sara',
                'last_name': 'Ali',
                'password': 'Teach-Python-2026',
                'can_manage_students': True,
                'can_manage_content': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('password', response.data)
        new_admin = User.objects.get(username='teacher2')
        self.assertEqual(new_admin.role, User.Role.ADMIN)
        self.assertTrue(new_admin.check_password('Teach-Python-2026'))
        self.assertFalse(new_admin.may_manage_content)

    def test_regular_admin_cannot_manage_admins(self):
        log_in(self.client, create_user('teacher', role=User.Role.ADMIN))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_disabled_admin_is_logged_out_and_cannot_log_in(self):
        admin = create_user('teacher', role=User.Role.ADMIN)
        Token.objects.create(user=admin)
        log_in(self.client, self.main_admin)

        response = self.client.patch(f'{self.url}{admin.pk}/', {'is_active': False}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(user=admin).exists())
        self.client.credentials()
        login_response = self.client.post(
            '/api/auth/login/', {'username': 'teacher', 'password': TEST_PASSWORD}, format='json'
        )
        self.assertEqual(login_response.status_code, status.HTTP_403_FORBIDDEN)
