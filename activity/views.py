from rest_framework import generics
from rest_framework.exceptions import ValidationError

from config.pagination import StandardPagination
from users.permissions import IsLmsAdmin

from .models import ActivityLog
from .serializers import ActivityLogSerializer


class ActivityLogListView(generics.ListAPIView):
    """
    GET /api/admin/activity/            -> the history of changes, newest first, 20 per page
    GET /api/admin/activity/?kind=content  -> only one kind (student, content, doubt, admin)
    """

    serializer_class = ActivityLogSerializer
    permission_classes = [IsLmsAdmin]
    pagination_class = StandardPagination

    def get_queryset(self):
        logs = ActivityLog.objects.select_related('actor')
        kind = self.request.query_params.get('kind')
        if kind:
            if kind not in ActivityLog.Kind.values:
                raise ValidationError({'kind': f'Choose one of: {", ".join(ActivityLog.Kind.values)}.'})
            logs = logs.filter(kind=kind)
        return logs
