from django.urls import path

from . import admin_views, views

urlpatterns = [
    # Students: my own progress
    path('progress/topics/<int:topic_id>/', views.my_topic_progress, name='my-topic-progress'),
    path('progress/topics/<int:topic_id>/complete/', views.mark_topic_completed, name='mark-topic-completed'),
    path('progress/courses/<int:course_id>/', views.my_course_progress, name='my-course-progress'),
    path('progress/questions/<int:question_id>/', views.update_my_progress, name='update-my-progress'),
    path('progress/overview/', views.my_overview, name='my-overview'),
    path('progress/practice/', views.PracticeQuestionListView.as_view(), name='my-practice'),
    path('progress/messages/', views.my_messages, name='my-messages'),
    path('progress/messages/mark-seen/', views.mark_messages_seen, name='mark-messages-seen'),
    path('progress/certificates/', views.my_certificates, name='my-certificates'),
    path('progress/calendar/', views.my_calendar, name='my-calendar'),
    # Admins with student rights: everyone's progress and doubts
    path('admin/progress/', admin_views.ProgressRecordListView.as_view(), name='progress-records'),
    path('admin/progress/<int:pk>/resolve/', admin_views.resolve_doubt, name='resolve-doubt'),
    path('admin/progress/<int:pk>/share-answer/', admin_views.share_answer, name='share-answer'),
    path('admin/students/<int:pk>/progress/', admin_views.student_progress_overview, name='student-progress'),
    path('admin/students/<int:student_id>/topics/<int:topic_id>/unlock/', admin_views.unlock_topic, name='admin-unlock-topic'),
]
