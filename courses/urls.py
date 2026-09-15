from django.urls import path

from . import views

urlpatterns = [
    path('courses/', views.CourseListCreateView.as_view(), name='course-list'),
    path('courses/<int:pk>/', views.CourseDetailView.as_view(), name='course-detail'),
    path('courses/<int:course_id>/topics/', views.TopicListCreateView.as_view(), name='topic-list'),
    path('topics/', views.AllTopicsView.as_view(), name='all-topics'),
    path('topics/<int:pk>/', views.TopicDetailView.as_view(), name='topic-detail'),
]
