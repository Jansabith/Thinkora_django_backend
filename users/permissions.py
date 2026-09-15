"""
Permission classes: the rules Django REST Framework checks BEFORE a view runs.

- Not logged in          -> 401 Unauthorized
- Logged in, not allowed -> 403 Forbidden
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsStudent(BasePermission):
    """Allows only students (for example: marking questions as done)."""

    message = 'Only students can do this.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_student


class IsLmsAdmin(BasePermission):
    """Allows Admins and the Main Admin."""

    message = 'Only admins can do this.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_lms_admin


class IsMainAdmin(BasePermission):
    """Allows only the Main Admin."""

    message = 'Only the Main Admin can do this.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_main_admin


class CanManageStudents(BasePermission):
    """Allows the Main Admin, and Admins who have student-management rights."""

    message = 'You do not have permission to manage students.'

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.may_manage_students


class CanManageContentOrReadOnly(BasePermission):
    """
    Any logged-in user may READ (GET).
    Only users with content rights may CREATE, UPDATE or DELETE.
    """

    message = 'You do not have permission to change learning content.'

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.may_manage_content
