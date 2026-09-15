from django.urls import path

from . import views

urlpatterns = [
    path('questions/', views.AllQuestionsView.as_view(), name='all-questions'),
    path('assigned-questions/', views.StudentAssignedQuestionsView.as_view(), name='student-assigned'),
    path('students/<int:student_id>/assign-questions/', views.AdminAssignQuestionsView.as_view(), name='admin-assign-questions'),
    path('questions/bulk/', views.BulkCreateQuestionsView.as_view(), name='bulk-questions'),
    path('questions/extract-pdf/', views.ExtractPdfQuestionsView.as_view(), name='extract-pdf'),
    path('topics/<int:topic_id>/questions/', views.QuestionListCreateView.as_view(), name='question-list'),
    path('questions/<int:pk>/', views.QuestionDetailView.as_view(), name='question-detail'),
]
