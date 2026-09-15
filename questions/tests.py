from rest_framework import status
from rest_framework.test import APITestCase

from courses.models import Course, Topic
from users.models import User
from users.testing import create_user, log_in

from .models import Question

EASY = Question.Difficulty.EASY
MEDIUM = Question.Difficulty.MEDIUM
HARD = Question.Difficulty.HARD


class PracticeQuestionTests(APITestCase):
    def setUp(self):
        self.student = create_user('ali')
        self.admin = create_user('teacher', role=User.Role.ADMIN)
        course = Course.objects.create(title='Python')
        self.topic = Topic.objects.create(course=course, title='Lists')
        Question.objects.create(topic=self.topic, text='Remove duplicates, keep order', difficulty=HARD)
        Question.objects.create(topic=self.topic, text='append() vs extend()?', difficulty=MEDIUM)
        self.easy_question = Question.objects.create(
            topic=self.topic, text='What is a list?', difficulty=EASY, answer='An ordered collection.'
        )
        self.url = f'/api/topics/{self.topic.pk}/questions/'

    def test_student_sees_questions_easy_first(self):
        log_in(self.client, self.student)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [question['difficulty'] for question in response.data],
            ['easy', 'medium', 'hard'],
        )

    def test_students_never_receive_answers(self):
        log_in(self.client, self.student)

        questions = self.client.get(self.url).data
        self.assertTrue(all('answer' not in question for question in questions))

        question = self.client.get(f'/api/questions/{self.easy_question.pk}/').data
        self.assertNotIn('answer', question)

    def test_content_managers_receive_answers(self):
        log_in(self.client, self.admin)
        question = self.client.get(f'/api/questions/{self.easy_question.pk}/').data
        self.assertEqual(question['answer'], 'An ordered collection.')

    def test_filter_by_difficulty(self):
        log_in(self.client, self.student)
        response = self.client.get(f'{self.url}?difficulty=hard')
        self.assertEqual([question['text'] for question in response.data], ['Remove duplicates, keep order'])

    def test_unknown_difficulty_is_rejected(self):
        log_in(self.client, self.student)
        response = self.client.get(f'{self.url}?difficulty=impossible')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_can_add_question(self):
        log_in(self.client, self.admin)
        response = self.client.post(
            self.url,
            {'text': 'Reverse a list', 'difficulty': 'medium', 'answer': 'my_list[::-1]'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Question.objects.get(text='Reverse a list').topic, self.topic)

    def test_difficulty_must_be_a_known_value(self):
        log_in(self.client, self.admin)
        response = self.client.post(self.url, {'text': 'Too hard?', 'difficulty': 'expert'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('difficulty', response.data)

    def test_student_cannot_add_question(self):
        log_in(self.client, self.student)
        response = self.client.post(self.url, {'text': 'Hack?', 'difficulty': 'easy'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_edit_and_delete_question(self):
        log_in(self.client, self.admin)
        detail_url = f'/api/questions/{self.easy_question.pk}/'

        edit_response = self.client.patch(detail_url, {'difficulty': 'medium'}, format='json')
        self.assertEqual(edit_response.status_code, status.HTTP_200_OK)
        self.easy_question.refresh_from_db()
        self.assertEqual(self.easy_question.difficulty, MEDIUM)

        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_questions_of_unpublished_course_are_hidden(self):
        draft_course = Course.objects.create(title='Draft', is_published=False)
        draft_topic = Topic.objects.create(course=draft_course, title='Secret')
        log_in(self.client, self.student)
        response = self.client.get(f'/api/topics/{draft_topic.pk}/questions/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
