from django.urls import path

from . import views

urlpatterns = [
    path('topics/<int:topic_id>/videos/', views.VideoListCreateView.as_view(), name='video-list'),
    path('videos/<int:pk>/', views.VideoDetailView.as_view(), name='video-detail'),
]
