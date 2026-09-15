from rest_framework import status
from rest_framework.test import APITestCase

from questions.models import Question
from users.models import User
from users.testing import create_user, log_in
from videos.models import Video

from .models import Course, Topic


class CourseAndTopicTests(APITestCase):
    def setUp(self):
        self.student = create_user('ali')
        self.admin = create_user('teacher', role=User.Role.ADMIN)
        self.python = Course.objects.create(title='Python')
        self.draft = Course.objects.create(title='Draft course', is_published=False)
        self.lists = Topic.objects.create(course=self.python, title='Lists', order=2)
        self.draft_topic = Topic.objects.create(course=self.draft, title='Secret topic', order=1)

    def test_anonymous_user_gets_401(self):
        response = self.client.get('/api/courses/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_sees_only_published_courses(self):
        log_in(self.client, self.student)
        response = self.client.get('/api/courses/')
        self.assertEqual([course['title'] for course in response.data], ['Python'])

    def test_admin_sees_all_courses(self):
        log_in(self.client, self.admin)
        response = self.client.get('/api/courses/')
        self.assertEqual([course['title'] for course in response.data], ['Draft course', 'Python'])

    def test_student_cannot_create_course(self):
        log_in(self.client, self.student)
        response = self.client.post('/api/courses/', {'title': 'Hacked'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Course.objects.count(), 2)

    def test_admin_can_create_course_and_topic(self):
        log_in(self.client, self.admin)

        course_response = self.client.post(
            '/api/courses/', {'title': 'JavaScript', 'description': 'The language of the web'}, format='json'
        )
        self.assertEqual(course_response.status_code, status.HTTP_201_CREATED)
        course_id = course_response.data['id']

        topic_response = self.client.post(
            f'/api/courses/{course_id}/topics/',
            {'title': 'Arrays', 'description': 'Lists of values', 'order': 1},
            format='json',
        )
        self.assertEqual(topic_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Topic.objects.get(title='Arrays').course_id, course_id)

    def test_admin_without_content_rights_cannot_edit(self):
        limited_admin = create_user('limited', role=User.Role.ADMIN, can_manage_content=False)
        log_in(self.client, limited_admin)
        response = self.client.patch(f'/api/courses/{self.python.pk}/', {'title': 'X'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_open_topic_of_unpublished_course(self):
        log_in(self.client, self.student)
        response = self.client.get(f'/api/topics/{self.draft_topic.pk}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_topics_are_listed_in_order(self):
        Topic.objects.create(course=self.python, title='Variables', order=1)
        log_in(self.client, self.student)
        response = self.client.get(f'/api/courses/{self.python.pk}/topics/')
        self.assertEqual([topic['title'] for topic in response.data], ['Variables', 'Lists'])

    def test_counts_questions_by_difficulty_and_videos(self):
        Question.objects.create(topic=self.lists, text='Easy 1', difficulty=Question.Difficulty.EASY)
        Question.objects.create(topic=self.lists, text='Easy 2', difficulty=Question.Difficulty.EASY)
        Question.objects.create(topic=self.lists, text='Hard 1', difficulty=Question.Difficulty.HARD)
        Video.objects.create(topic=self.lists, title='Lists explained', url='https://youtu.be/AbCdEfGhIj1')
        log_in(self.client, self.student)

        topic = self.client.get(f'/api/courses/{self.python.pk}/topics/').data[0]
        self.assertEqual(
            [topic['question_count'], topic['easy_count'], topic['medium_count'], topic['hard_count']],
            [3, 2, 0, 1],
        )
        self.assertEqual(topic['video_count'], 1)

        course = self.client.get(f'/api/courses/{self.python.pk}/').data
        self.assertEqual([course['topic_count'], course['question_count'], course['video_count']], [1, 3, 1])

    def test_deleting_course_deletes_its_topics_and_questions(self):
        Question.objects.create(topic=self.lists, text='What is a list?')
        log_in(self.client, self.admin)

        response = self.client.delete(f'/api/courses/{self.python.pk}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Topic.objects.filter(title='Lists').exists())
        self.assertFalse(Question.objects.filter(text='What is a list?').exists())
