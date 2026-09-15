from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from courses.models import Course, Topic
from questions.models import Question
from users.models import User
from users.testing import create_user, log_in

from .models import QuestionProgress

OPEN = QuestionProgress.DoubtStatus.OPEN
RESOLVED = QuestionProgress.DoubtStatus.RESOLVED


class ProgressTestCase(APITestCase):
    """Shared test data: one course, two topics, three questions, two students, one admin."""

    def setUp(self):
        self.student = create_user('ali', first_name='Ali')
        self.other_student = create_user('sara')
        self.admin = create_user('teacher', role=User.Role.ADMIN)
        self.course = Course.objects.create(title='Python')
        self.lists = Topic.objects.create(course=self.course, title='Lists', order=1)
        self.loops = Topic.objects.create(course=self.course, title='Loops', order=2)
        self.list_question = Question.objects.create(topic=self.lists, text='What is a list?')
        self.extend_question = Question.objects.create(topic=self.lists, text='append() vs extend()?')
        self.loop_question = Question.objects.create(topic=self.loops, text='Print 1 to 10')

    def update_progress(self, question, **changes):
        return self.client.patch(f'/api/progress/questions/{question.pk}/', changes, format='json')

    def get_my_record(self, question):
        """The logged-in student's progress row for one question, as the student API returns it."""
        records = self.client.get(f'/api/progress/topics/{question.topic_id}/').data
        return next(record for record in records if record['question'] == question.pk)

    def share_answer(self, record, shared):
        return self.client.post(f'/api/admin/progress/{record.pk}/share-answer/', {'shared': shared}, format='json')


class StudentProgressTests(ProgressTestCase):
    def test_student_marks_question_done_and_undone(self):
        log_in(self.client, self.student)

        done = self.update_progress(self.list_question, is_done=True)
        self.assertEqual(done.status_code, status.HTTP_200_OK)
        self.assertTrue(done.data['is_done'])
        self.assertIsNotNone(done.data['done_at'])

        undone = self.update_progress(self.list_question, is_done=False)
        self.assertFalse(undone.data['is_done'])
        self.assertIsNone(undone.data['done_at'])
        self.assertEqual(QuestionProgress.objects.count(), 1)

    def test_student_asks_and_withdraws_doubt(self):
        log_in(self.client, self.student)

        asked = self.update_progress(self.extend_question, doubt_status='open', doubt_message='Why two methods?')
        self.assertEqual(asked.data['doubt_status'], 'open')
        self.assertEqual(asked.data['doubt_message'], 'Why two methods?')

        withdrawn = self.update_progress(self.extend_question, doubt_status='none')
        self.assertEqual(withdrawn.data['doubt_status'], 'none')
        self.assertEqual(withdrawn.data['doubt_message'], '')

    def test_student_cannot_resolve_own_doubt(self):
        log_in(self.client, self.student)
        response = self.update_progress(self.list_question, doubt_status='resolved')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_update_is_rejected(self):
        log_in(self.client, self.student)
        response = self.update_progress(self.list_question)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_required(self):
        response = self.update_progress(self.list_question, is_done=True)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admins_have_no_student_progress(self):
        log_in(self.client, self.admin)
        response = self.update_progress(self.list_question, is_done=True)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_questions_of_unpublished_course_cannot_be_marked(self):
        draft_topic = Topic.objects.create(course=Course.objects.create(title='Draft', is_published=False), title='Secret')
        draft_question = Question.objects.create(topic=draft_topic, text='Hidden?')
        log_in(self.client, self.student)
        response = self.update_progress(draft_question, is_done=True)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_topic_progress_only_contains_my_own_records(self):
        QuestionProgress.objects.create(student=self.other_student, question=self.list_question, is_done=True)
        QuestionProgress.objects.create(student=self.student, question=self.extend_question, is_done=True)
        log_in(self.client, self.student)

        response = self.client.get(f'/api/progress/topics/{self.lists.pk}/')

        self.assertEqual([record['question'] for record in response.data], [self.extend_question.pk])

    def test_course_progress_counts_per_topic(self):
        log_in(self.client, self.student)
        self.update_progress(self.list_question, is_done=True)
        self.update_progress(self.extend_question, is_done=True)
        self.update_progress(self.loop_question, doubt_status='open')

        data = self.client.get(f'/api/progress/courses/{self.course.pk}/').json()

        self.assertEqual([data['done_count'], data['open_doubt_count']], [2, 1])
        self.assertEqual(data['topics'][str(self.lists.pk)]['done_count'], 2)
        self.assertEqual(data['topics'][str(self.loops.pk)]['open_doubt_count'], 1)


class AdminProgressTests(ProgressTestCase):
    def setUp(self):
        super().setUp()
        QuestionProgress.objects.create(student=self.student, question=self.list_question, is_done=True)
        self.doubt = QuestionProgress.objects.create(
            student=self.student, question=self.extend_question, doubt_status=OPEN, doubt_message='Why two methods?'
        )
        QuestionProgress.objects.create(student=self.other_student, question=self.loop_question, is_done=True)

    def test_admin_sees_which_student_has_a_doubt_on_which_question(self):
        log_in(self.client, self.admin)
        response = self.client.get('/api/admin/progress/?status=open')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        record = response.data[0]
        self.assertEqual(
            [record['student_username'], record['question_text'], record['topic_title'], record['course_title']],
            ['ali', 'append() vs extend()?', 'Lists', 'Python'],
        )

    def test_filter_by_student(self):
        log_in(self.client, self.admin)
        response = self.client.get(f'/api/admin/progress/?student={self.student.pk}')
        self.assertEqual(len(response.data), 2)

    def test_filter_by_topic_and_done(self):
        log_in(self.client, self.admin)
        response = self.client.get(f'/api/admin/progress/?topic={self.loops.pk}&status=done')
        self.assertEqual([record['student_username'] for record in response.data], ['sara'])

    def test_students_cannot_see_other_students_progress(self):
        log_in(self.client, self.student)
        response = self.client.get('/api/admin/progress/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_without_student_rights_cannot_see_progress(self):
        log_in(self.client, create_user('limited', role=User.Role.ADMIN, can_manage_students=False))
        response = self.client.get('/api/admin/progress/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_resolves_doubt_and_student_sees_reply(self):
        log_in(self.client, self.admin)
        response = self.client.post(
            f'/api/admin/progress/{self.doubt.pk}/resolve/',
            {'reply': 'append() adds one item, extend() adds many.'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.doubt.refresh_from_db()
        self.assertEqual(self.doubt.doubt_status, RESOLVED)
        self.assertEqual(self.doubt.resolved_by, self.admin)

        log_in(self.client, self.student)
        records = self.client.get(f'/api/progress/topics/{self.lists.pk}/').data
        reply = next(record['admin_reply'] for record in records if record['question'] == self.extend_question.pk)
        self.assertEqual(reply, 'append() adds one item, extend() adds many.')

    def test_reply_is_required(self):
        log_in(self.client, self.admin)
        response = self.client.post(f'/api/admin/progress/{self.doubt.pk}/resolve/', {'reply': ''}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_asking_again_reopens_a_resolved_doubt(self):
        self.doubt.resolve_doubt(self.admin, 'Old reply')
        self.doubt.save()
        log_in(self.client, self.student)

        response = self.update_progress(self.extend_question, doubt_status='open', doubt_message='Still confused')

        self.assertEqual(response.data['doubt_status'], 'open')
        self.assertEqual(response.data['admin_reply'], '')

    def test_answer_is_hidden_until_an_admin_shows_it(self):
        self.extend_question.answer = 'append() adds one item. extend() adds each item.'
        self.extend_question.save()

        log_in(self.client, self.student)
        self.assertIsNone(self.get_my_record(self.extend_question)['answer'])

        log_in(self.client, self.admin)
        response = self.share_answer(self.doubt, True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['answer_shared'])

        log_in(self.client, self.student)
        self.assertEqual(self.get_my_record(self.extend_question)['answer'], self.extend_question.answer)

        log_in(self.client, self.admin)
        self.share_answer(self.doubt, False)
        log_in(self.client, self.student)
        self.assertIsNone(self.get_my_record(self.extend_question)['answer'])

    def test_answer_is_shown_only_to_that_one_student(self):
        self.extend_question.answer = 'The answer'
        self.extend_question.save()
        QuestionProgress.objects.create(student=self.other_student, question=self.extend_question, doubt_status=OPEN)

        log_in(self.client, self.admin)
        self.share_answer(self.doubt, True)

        log_in(self.client, self.other_student)
        self.assertIsNone(self.get_my_record(self.extend_question)['answer'])

    def test_reply_can_also_show_the_answer(self):
        self.extend_question.answer = 'The answer'
        self.extend_question.save()
        log_in(self.client, self.admin)

        response = self.client.post(
            f'/api/admin/progress/{self.doubt.pk}/resolve/',
            {'reply': 'Look at the answer below.', 'share_answer': True},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['answer_shared'])

    def test_cannot_show_an_answer_that_does_not_exist(self):
        log_in(self.client, self.admin)
        response = self.share_answer(self.doubt, True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_students_cannot_show_answers(self):
        log_in(self.client, self.student)
        response = self.share_answer(self.doubt, True)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_overview_totals(self):
        log_in(self.client, self.admin)
        data = self.client.get(f'/api/admin/students/{self.student.pk}/progress/').data

        self.assertEqual(data['student']['username'], 'ali')
        summary = data['summary']
        self.assertEqual([summary['question_count'], summary['done_count'], summary['open_doubt_count']], [3, 1, 1])
        lists_topic, loops_topic = data['courses'][0]['topics']
        self.assertEqual([lists_topic['question_count'], lists_topic['done_count'], lists_topic['open_doubt_count']], [2, 1, 1])
        self.assertEqual(loops_topic['done_count'], 0)

    def test_dashboard_counts_open_doubts(self):
        log_in(self.client, self.admin)
        response = self.client.get('/api/admin/stats/')
        self.assertEqual(response.data['open_doubts'], 1)

    def test_answering_a_doubt_makes_the_reply_unread(self):
        log_in(self.client, self.admin)
        self.client.post(f'/api/admin/progress/{self.doubt.pk}/resolve/', {'reply': 'Here you go.'}, format='json')
        self.doubt.refresh_from_db()
        self.assertFalse(self.doubt.reply_seen)


class StudentPagesTests(ProgressTestCase):
    def test_bookmark_a_question(self):
        log_in(self.client, self.student)

        response = self.update_progress(self.list_question, is_bookmarked=True)
        self.assertTrue(response.data['is_bookmarked'])

        bookmarks = self.client.get('/api/progress/practice/?status=bookmarked').data
        self.assertEqual([question['id'] for question in bookmarks['results']], [self.list_question.pk])
        self.assertTrue(bookmarks['results'][0]['progress']['is_bookmarked'])

    def test_practice_filters_done_and_todo_without_answers(self):
        self.list_question.answer = 'Secret answer'
        self.list_question.save()
        log_in(self.client, self.student)
        self.update_progress(self.extend_question, is_done=True)

        done = self.client.get('/api/progress/practice/?status=done').data
        self.assertEqual([question['id'] for question in done['results']], [self.extend_question.pk])

        todo = self.client.get('/api/progress/practice/?status=todo').data
        self.assertEqual(todo['count'], 2)
        self.assertTrue(all('answer' not in question for question in todo['results']))
        self.assertEqual(todo['results'][0]['course_title'], 'Python')

    def test_practice_hides_unpublished_courses(self):
        draft_topic = Topic.objects.create(course=Course.objects.create(title='Draft', is_published=False), title='Secret')
        Question.objects.create(topic=draft_topic, text='Hidden?')
        log_in(self.client, self.student)
        self.assertEqual(self.client.get('/api/progress/practice/').data['count'], 3)

    def test_messages_show_unread_replies_until_seen(self):
        record = QuestionProgress.objects.create(
            student=self.student, question=self.extend_question, doubt_status=OPEN, doubt_message='Why?'
        )
        record.resolve_doubt(self.admin, 'Because extend() adds each item.')
        record.save()
        log_in(self.client, self.student)

        messages = self.client.get('/api/progress/messages/').data
        self.assertEqual(len(messages), 1)
        self.assertFalse(messages[0]['reply_seen'])
        self.assertEqual(messages[0]['topic_title'], 'Lists')

        self.assertEqual(self.client.post('/api/progress/messages/mark-seen/').data['updated'], 1)
        self.assertTrue(self.client.get('/api/progress/messages/').data[0]['reply_seen'])

    def test_certificate_only_after_every_question_of_the_course(self):
        log_in(self.client, self.student)
        self.update_progress(self.list_question, is_done=True)
        self.update_progress(self.extend_question, is_done=True)
        self.assertEqual(self.client.get('/api/progress/certificates/').data, [])

        self.update_progress(self.loop_question, is_done=True)
        certificates = self.client.get('/api/progress/certificates/').data
        self.assertEqual([certificate['course_title'] for certificate in certificates], ['Python'])
        self.assertEqual(certificates[0]['student_name'], 'Ali')

    def test_calendar_counts_done_questions_per_day(self):
        log_in(self.client, self.student)
        self.update_progress(self.list_question, is_done=True)
        self.update_progress(self.extend_question, is_done=True)
        today = timezone.localdate()

        data = self.client.get(f'/api/progress/calendar/?year={today.year}&month={today.month}').data

        self.assertEqual(data['days'][today.isoformat()], 2)
        self.assertEqual(self.client.get('/api/progress/calendar/?year=2026&month=13').status_code, status.HTTP_400_BAD_REQUEST)

    def test_my_overview(self):
        log_in(self.client, self.student)
        self.update_progress(self.list_question, is_done=True)

        data = self.client.get('/api/progress/overview/').data

        self.assertEqual(data['summary']['done_count'], 1)
        self.assertEqual(data['courses'][0]['topics'][0]['done_count'], 1)
