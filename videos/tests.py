from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from courses.models import Course, Topic
from users.models import User
from users.testing import create_user, log_in

from .embed import get_embed_url
from .models import Video


class EmbedUrlTests(SimpleTestCase):
    def test_youtube_links_become_embed_urls(self):
        expected = 'https://www.youtube-nocookie.com/embed/AbCdEfGhIj1'
        links = [
            'https://www.youtube.com/watch?v=AbCdEfGhIj1',
            'https://youtu.be/AbCdEfGhIj1',
            'https://www.youtube.com/embed/AbCdEfGhIj1',
            'https://www.youtube.com/shorts/AbCdEfGhIj1',
            'https://www.youtube.com/watch?list=abc&v=AbCdEfGhIj1',
        ]
        for link in links:
            with self.subTest(link=link):
                self.assertEqual(get_embed_url(link), expected)

    def test_other_links_are_not_embedded(self):
        self.assertIsNone(get_embed_url('https://vimeo.com/12345'))


class VideoApiTests(APITestCase):
    def setUp(self):
        self.student = create_user('ali')
        self.admin = create_user('teacher', role=User.Role.ADMIN)
        course = Course.objects.create(title='Python')
        self.topic = Topic.objects.create(course=course, title='Lists')
        self.url = f'/api/topics/{self.topic.pk}/videos/'

    def test_admin_can_add_youtube_video(self):
        log_in(self.client, self.admin)
        response = self.client.post(
            self.url,
            {'title': 'Lists in 10 minutes', 'url': 'https://youtu.be/AbCdEfGhIj1'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['embed_url'], 'https://www.youtube-nocookie.com/embed/AbCdEfGhIj1')

    def test_link_must_be_a_real_web_address(self):
        log_in(self.client, self.admin)
        for bad_link in ['not a link', 'javascript:alert(1)']:
            with self.subTest(link=bad_link):
                response = self.client.post(self.url, {'title': 'Bad', 'url': bad_link}, format='json')
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn('url', response.data)

    def test_student_can_watch_but_not_add(self):
        Video.objects.create(topic=self.topic, title='Lists explained', url='https://example.com/lists')
        log_in(self.client, self.student)

        list_response = self.client.get(self.url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data[0]['embed_url'], None)

        add_response = self.client.post(self.url, {'title': 'Hack', 'url': 'https://example.com'}, format='json')
        self.assertEqual(add_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_videos_of_unpublished_course_are_hidden(self):
        draft_course = Course.objects.create(title='Draft', is_published=False)
        draft_topic = Topic.objects.create(course=draft_course, title='Secret')
        log_in(self.client, self.student)
        response = self.client.get(f'/api/topics/{draft_topic.pk}/videos/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
