from .models import ActivityLog


def log_activity(actor, kind, message, link=''):
    """
    Add one line to the admin activity log, for example:

        log_activity(request.user, ActivityLog.Kind.CONTENT, 'Course "Python" was created', '/admin/courses/1')
    """
    ActivityLog.objects.create(
        # A visitor who is not logged in (AnonymousUser) cannot be saved as the actor.
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        kind=kind,
        message=message[:300],
        link=link[:200],
    )
