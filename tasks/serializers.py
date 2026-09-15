from rest_framework import serializers

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'title', 'is_done', 'due_date', 'completed_at', 'created_at']
        read_only_fields = ['completed_at', 'created_at']
