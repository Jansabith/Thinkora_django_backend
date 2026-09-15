from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User
from users.testing import create_user, log_in

from .models import Task


class TaskTests(APITestCase):
    def setUp(self):
        self.student = create_user('ali')
        self.admin = create_user('teacher', role=User.Role.ADMIN)

    def test_add_complete_and_reopen_a_task(self):
        log_in(self.client, self.student)

        created = self.client.post('/api/tasks/', {'title': 'Solve 5 practice questions'}, format='json')
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        task_url = f"/api/tasks/{created.data['id']}/"

        done = self.client.patch(task_url, {'is_done': True}, format='json')
        self.assertTrue(done.data['is_done'])
        self.assertIsNotNone(done.data['completed_at'])

        reopened = self.client.patch(task_url, {'is_done': False}, format='json')
        self.assertIsNone(reopened.data['completed_at'])

    def test_users_only_see_their_own_tasks(self):
        admin_task = Task.objects.create(owner=self.admin, title='Review student feedback')
        log_in(self.client, self.student)

        self.assertEqual(self.client.get('/api/tasks/').data, [])
        response = self.client.patch(f'/api/tasks/{admin_task.pk}/', {'is_done': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_open_tasks_come_first(self):
        Task.objects.create(owner=self.student, title='Finished', is_done=True)
        Task.objects.create(owner=self.student, title='Still to do')
        log_in(self.client, self.student)

        titles = [task['title'] for task in self.client.get('/api/tasks/').data]

        self.assertEqual(titles, ['Still to do', 'Finished'])

    def test_title_is_required(self):
        log_in(self.client, self.student)
        response = self.client.post('/api/tasks/', {'title': '  '}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_required(self):
        self.assertEqual(self.client.get('/api/tasks/').status_code, status.HTTP_401_UNAUTHORIZED)
