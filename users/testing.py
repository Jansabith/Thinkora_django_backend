"""Small helpers shared by the automated tests of all apps."""

from rest_framework.authtoken.models import Token

from .models import User

TEST_PASSWORD = 'Test-Password-2026'


def create_user(username, role=User.Role.STUDENT, **extra_fields):
    """Create an approved, active user with TEST_PASSWORD (change anything with extra_fields)."""
    extra_fields.setdefault('access_status', User.AccessStatus.APPROVED)
    extra_fields.setdefault('email', f'{username}@example.com')
    return User.objects.create_user(
        username=username,
        password=TEST_PASSWORD,
        role=role,
        **extra_fields,
    )


def log_in(client, user):
    """Make the test client send this user's token with every request."""
    token, _created = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
