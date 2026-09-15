from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .models import Task
from .serializers import TaskSerializer


class TaskListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/tasks/               -> my tasks  (?status=open or ?status=done)
    POST /api/tasks/               -> add a task: {"title": "...", "due_date": "2026-09-20"}
    """

    serializer_class = TaskSerializer

    def get_queryset(self):
        # Only MY tasks: another user's tasks are never visible.
        tasks = Task.objects.filter(owner=self.request.user)
        status = self.request.query_params.get('status')
        if status == 'open':
            tasks = tasks.filter(is_done=False)
        elif status == 'done':
            tasks = tasks.filter(is_done=True)
        elif status:
            raise ValidationError({'status': 'Choose open or done.'})
        return tasks

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    PATCH  /api/tasks/<id>/  -> change the title, due date, or tick it: {"is_done": true}
    DELETE /api/tasks/<id>/  -> remove the task
    """

    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.filter(owner=self.request.user)

    def perform_update(self, serializer):
        task = serializer.instance
        is_done = serializer.validated_data.get('is_done', task.is_done)
        if is_done and not task.is_done:
            completed_at = timezone.now()
        elif is_done:
            completed_at = task.completed_at
        else:
            completed_at = None
        serializer.save(completed_at=completed_at)
