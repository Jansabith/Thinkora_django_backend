from rest_framework import serializers

from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = ['id', 'kind', 'message', 'link', 'actor_name', 'created_at']

    def get_actor_name(self, log):
        return log.actor.display_name if log.actor else None
