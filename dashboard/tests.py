from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from courses.models import Course, Topic
from progress.models import QuestionProgress
from questions.models import Question
from users.models import User
from users.testing import create_user, log_in


class DashboardTestCase(APITestCase):
    """Python (2 topics, 3 questions) and JavaScript (1 topic, 1 question)."""

    def setUp(self):
        self.student = create_user('ali', first_name='Ali')
        self.admin = create_user('teacher', role=User.Role.ADMIN)
        self.python = Course.objects.create(title='Python', category='Programming')
        self.javascript = Course.objects.create(title='JavaScript', category='Web Development')
        self.lists = Topic.objects.create(course=self.python, title='Lists', order=1)
        self.loops = Topic.objects.create(course=self.python, title='Loops', order=2)
        self.arrays = Topic.objects.create(course=self.javascript, title='Arrays', order=1)
        self.list_question = Question.objects.create(topic=self.lists, text='What is a list?')
        self.extend_question = Question.objects.create(topic=self.lists, text='append() vs extend()?')
        self.loop_question = Question.objects.create(topic=self.loops, text='Print 1 to 10')
        Question.objects.create(topic=self.arrays, text='What is an array?')

    def mark_done(self, student, question):
        return QuestionProgress.objects.create(student=student, question=question, is_done=True, done_at=timezone.now())


class StudentDashboardTests(DashboardTestCase):
    def test_dashboard_numbers(self):
        self.mark_done(self.student, self.list_question)
        self.mark_done(self.student, self.extend_question)
        log_in(self.client, self.student)

        data = self.client.get('/api/student/dashboard/').data

        stats = data['stats']
        self.assertEqual(
            [stats['started_courses'], stats['topics_completed'], stats['questions_solved'], stats['question_count'], stats['overall_progress']],
            [1, 1, 2, 4, 50],
        )
        self.assertEqual(data['topic_progress'], {'completed': 1, 'in_progress': 0, 'not_started': 2})

        python_card = data['continue_learning'][0]
        self.assertEqual(python_card['title'], 'Python')
        self.assertEqual(python_card['current_topic']['title'], 'Loops')
        self.assertEqual(python_card['progress_percent'], 67)

        self.assertEqual([course['title'] for course in data['recommended']], ['JavaScript'])
        self.assertEqual(data['recent_activity'][0]['type'], 'done')

        achievements = {achievement['key']: achievement for achievement in data['achievements']}
        self.assertTrue(achievements['first_step']['earned'])
        self.assertFalse(achievements['problem_solver']['earned'])
        self.assertEqual(achievements['problem_solver']['current'], 2)

    def test_new_student_sees_courses_to_start(self):
        log_in(self.client, self.student)
        data = self.client.get('/api/student/dashboard/').data
        self.assertEqual(data['stats']['overall_progress'], 0)
        self.assertEqual(len(data['continue_learning']), 2)

    def test_only_students_have_a_student_dashboard(self):
        log_in(self.client, self.admin)
        self.assertEqual(self.client.get('/api/student/dashboard/').status_code, status.HTTP_403_FORBIDDEN)


class AdminDashboardTests(DashboardTestCase):
    def test_dashboard_numbers(self):
        create_user('newbie', access_status=User.AccessStatus.PENDING, is_active=False)
        log_in(self.client, self.admin)

        data = self.client.get('/api/admin/dashboard/').data

        self.assertEqual(data['stats']['students']['total'], 2)
        self.assertEqual(data['stats']['students']['new_this_month'], 2)
        self.assertEqual(data['stats']['questions']['total'], 4)
        self.assertEqual(data['pending_requests'], 1)
        self.assertEqual(
            {category['name'] for category in data['content_overview']['categories']},
            {'Programming', 'Web Development'},
        )
        self.assertEqual(len(data['student_growth']), 6)
        self.assertEqual(data['student_growth'][-1]['total_students'], 2)
        self.assertEqual([student['username'] for student in data['recent_requests']], ['newbie'])

    def test_admin_without_student_rights_gets_no_student_details(self):
        create_user('newbie', access_status=User.AccessStatus.PENDING, is_active=False)
        log_in(self.client, create_user('limited', role=User.Role.ADMIN, can_manage_students=False))
        self.assertEqual(self.client.get('/api/admin/dashboard/').data['recent_requests'], [])

    def test_students_cannot_open_the_admin_dashboard(self):
        log_in(self.client, self.student)
        self.assertEqual(self.client.get('/api/admin/dashboard/').status_code, status.HTTP_403_FORBIDDEN)

    def test_student_growth_range(self):
        log_in(self.client, self.admin)
        self.assertEqual(len(self.client.get('/api/admin/student-growth/?months=12').data), 12)
        self.assertEqual(self.client.get('/api/admin/student-growth/?months=5').status_code, status.HTTP_400_BAD_REQUEST)

    def test_reports(self):
        self.mark_done(self.student, self.list_question)
        log_in(self.client, create_user('limited', role=User.Role.ADMIN, can_manage_students=False))
        self.assertEqual(self.client.get('/api/admin/reports/').status_code, status.HTTP_403_FORBIDDEN)

        log_in(self.client, self.admin)
        data = self.client.get('/api/admin/reports/').data
        python = next(course for course in data['course_completion'] if course['title'] == 'Python')
        self.assertEqual([python['question_count'], python['students_started'], python['average_progress']], [3, 1, 33])
        self.assertEqual(data['top_students'][0]['username'], 'ali')
        self.assertEqual(len(data['weekly_activity']), 8)
        self.assertEqual(data['weekly_activity'][-1]['questions_done'], 1)


class NotificationTests(DashboardTestCase):
    def test_student_sees_unread_reply(self):
        record = QuestionProgress.objects.create(student=self.student, question=self.loop_question, doubt_status='open')
        record.resolve_doubt(self.admin, 'Use range(1, 11).')
        record.save()
        log_in(self.client, self.student)

        data = self.client.get('/api/notifications/').data

        self.assertEqual(data['badges']['unread_messages'], 1)
        self.assertEqual(data['items'][0]['link'], '/student/messages')

    def test_admin_sees_waiting_requests_and_open_doubts(self):
        create_user('newbie', access_status=User.AccessStatus.PENDING, is_active=False)
        QuestionProgress.objects.create(student=self.student, question=self.loop_question, doubt_status='open')
        log_in(self.client, self.admin)

        data = self.client.get('/api/notifications/').data

        self.assertEqual(data['badges'], {'pending_requests': 1, 'open_doubts': 1})
        self.assertEqual(data['count'], 2)


class SearchTests(DashboardTestCase):
    def test_students_only_find_published_content_and_no_students(self):
        Course.objects.create(title='Python Advanced', is_published=False)
        log_in(self.client, self.student)

        data = self.client.get('/api/search/?q=python').data

        self.assertEqual([course['title'] for course in data['courses']], ['Python'])
        self.assertEqual(data['students'], [])

    def test_admins_can_find_students(self):
        log_in(self.client, self.admin)
        data = self.client.get('/api/search/?q=ali').data
        self.assertEqual([student['username'] for student in data['students']], ['ali'])

    def test_short_queries_return_nothing(self):
        log_in(self.client, self.admin)
        data = self.client.get('/api/search/?q=p').data
        self.assertEqual(data, {'courses': [], 'topics': [], 'questions': [], 'students': []})


class LeaderboardTests(DashboardTestCase):
    """Sara: 3 questions done. Omar: 2. Ali (the logged-in student): 2."""

    def setUp(self):
        super().setUp()
        self.sara = create_user('sara', first_name='Sara')
        self.omar = create_user('omar', first_name='Omar')
        for question in [self.list_question, self.extend_question, self.loop_question]:
            self.mark_done(self.sara, question)
        self.mark_done(self.omar, self.list_question)
        self.mark_done(self.omar, self.extend_question)
        self.mark_done(self.student, self.list_question)
        self.mark_done(self.student, self.loop_question)

    def test_students_are_ranked_and_ties_share_a_rank(self):
        log_in(self.client, self.student)

        data = self.client.get('/api/leaderboard/').data

        self.assertEqual(
            [(row['name'], row['rank'], row['done_count']) for row in data['leaders']],
            [('Sara', 1, 3), ('Omar', 2, 2), ('Ali', 2, 2)],
        )
        self.assertTrue(data['leaders'][2]['is_me'])
        self.assertEqual(data['me']['rank'], 2)
        # Ali needs 2 more questions (4) to pass Sara (3).
        self.assertEqual(data['me']['to_next_rank'], 2)

    def test_this_week_only_counts_recent_questions(self):
        old_record = QuestionProgress.objects.get(student=self.sara, question=self.loop_question)
        old_record.done_at = timezone.now() - timedelta(days=40)
        old_record.save()
        log_in(self.client, self.student)

        data = self.client.get('/api/leaderboard/?period=week').data

        sara = next(row for row in data['leaders'] if row['name'] == 'Sara')
        self.assertEqual(sara['done_count'], 2)

    def test_inactive_students_and_draft_courses_are_not_counted(self):
        self.omar.is_active = False
        self.omar.save()
        draft_topic = Topic.objects.create(course=Course.objects.create(title='Draft', is_published=False), title='Secret')
        self.mark_done(self.student, Question.objects.create(topic=draft_topic, text='Hidden?'))
        log_in(self.client, self.admin)

        data = self.client.get('/api/leaderboard/').data

        self.assertNotIn('Omar', [row['name'] for row in data['leaders']])
        ali = next(row for row in data['leaders'] if row['name'] == 'Ali')
        self.assertEqual(ali['done_count'], 2)
        self.assertIsNone(data['me'])  # admins are not on the leaderboard

    def test_filter_by_course(self):
        self.mark_done(self.omar, Question.objects.get(topic=self.arrays))
        log_in(self.client, self.student)

        data = self.client.get(f'/api/leaderboard/?course={self.javascript.pk}').data

        self.assertEqual([row['name'] for row in data['leaders']], ['Omar'])
        self.assertIsNone(data['me']['rank'])
        self.assertEqual(data['me']['to_next_rank'], 1)

    def test_bad_filters_and_login(self):
        self.assertEqual(self.client.get('/api/leaderboard/').status_code, status.HTTP_401_UNAUTHORIZED)
        log_in(self.client, self.student)
        self.assertEqual(self.client.get('/api/leaderboard/?period=year').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get('/api/leaderboard/?limit=0').status_code, status.HTTP_400_BAD_REQUEST)
