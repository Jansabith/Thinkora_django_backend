from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class LmsUserManager(UserManager):
    """
    Django's normal UserManager with one change:
    'python manage.py createsuperuser' creates a Main Admin who can use the LMS.
    """

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('role', User.Role.MAIN_ADMIN)
        extra_fields.setdefault('access_status', User.AccessStatus.APPROVED)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    Our own User model for the LMS.

    It keeps everything from Django's AbstractUser (username, password hashing,
    is_active, ...) and adds the fields our LMS needs.
    """

    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        ADMIN = 'admin', 'Admin'
        MAIN_ADMIN = 'main_admin', 'Main Admin'

    class AccessStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)

    # is_active (from AbstractUser) decides IF the user can log in.
    # access_status explains WHY: still waiting, approved or rejected.
    access_status = models.CharField(
        max_length=20,
        choices=AccessStatus.choices,
        default=AccessStatus.PENDING,
    )
    request_message = models.TextField(
        blank=True,
        help_text='Optional message from the student when requesting access.',
    )
    whatsapp_number = models.CharField(
        max_length=20,
        blank=True,
        help_text='Student WhatsApp number, e.g. +971501234567. Collected at registration.',
    )
    reviewed_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_students',
        help_text='The admin who approved or rejected this student.',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    allowed_courses = models.ManyToManyField(
        'courses.Course',
        blank=True,
        related_name='allowed_students',
        help_text='Courses this student is allowed to access.',
    )

    # The Main Admin switches these on or off for each Admin.
    can_manage_students = models.BooleanField(
        default=True,
        help_text='Admins only: may approve, reject and manage students.',
    )
    can_manage_content = models.BooleanField(
        default=True,
        help_text='Admins only: may create, edit and delete courses, topics and questions.',
    )

    objects = LmsUserManager()

    @property
    def display_name(self):
        """'Sara Ahmed', or the username when no name was given."""
        return self.get_full_name() or self.username

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_lms_admin(self):
        """True for both Admins and the Main Admin."""
        return self.role in (self.Role.ADMIN, self.Role.MAIN_ADMIN)

    @property
    def is_main_admin(self):
        return self.role == self.Role.MAIN_ADMIN

    @property
    def may_manage_students(self):
        """The Main Admin always may. An Admin only if the Main Admin allowed it."""
        return self.is_main_admin or (self.role == self.Role.ADMIN and self.can_manage_students)

    @property
    def may_manage_content(self):
        """The Main Admin always may. An Admin only if the Main Admin allowed it."""
        return self.is_main_admin or (self.role == self.Role.ADMIN and self.can_manage_content)
