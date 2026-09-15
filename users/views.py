"""
Authentication views: request access, log in, log out, and the user's own profile.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from activity.models import ActivityLog
from activity.services import log_activity

from .models import User
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    ProfileSerializer,
    RequestAccessSerializer,
    UserSerializer,
)

INACTIVE_ACCOUNT_MESSAGES = {
    User.AccessStatus.PENDING: 'Your access request is still pending. Please wait for an admin to approve it.',
    User.AccessStatus.REJECTED: 'Your access request was rejected. Please contact your teacher.',
}


@api_view(['POST'])
@permission_classes([AllowAny])
def request_access(request):
    """
    POST /api/auth/request-access/
    A student asks for access. The account is created INACTIVE and PENDING.
    """
    serializer = RequestAccessSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    student = serializer.save()
    log_activity(
        student,
        ActivityLog.Kind.STUDENT,
        f'New access request from {student.display_name}',
        f'/admin/students/{student.id}',
    )
    return Response(
        {'detail': 'Your request has been sent. You can log in after an admin approves it.'},
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """
    POST /api/auth/login/
    Checks username + password and returns a token for future requests.
    """
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    username = serializer.validated_data['username']
    password = serializer.validated_data['password']

    # authenticate() checks the password hash AND refuses inactive users.
    user = authenticate(request, username=username, password=password)

    if user is None:
        # Was the password right, but the account is inactive? Then tell the user why.
        # (We only explain this AFTER the correct password, so strangers learn nothing.)
        inactive_user = User.objects.filter(username=username, is_active=False).first()
        if inactive_user is not None and inactive_user.check_password(password):
            message = INACTIVE_ACCOUNT_MESSAGES.get(
                inactive_user.access_status, 'Your account has been disabled.'
            )
            return Response({'detail': message}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            {'detail': 'Invalid username or password.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    token, _created = Token.objects.get_or_create(user=user)
    update_last_login(None, user)
    return Response({'token': token.key, 'user': UserSerializer(user).data})


@api_view(['POST'])
def logout_view(request):
    """
    POST /api/auth/logout/
    Deletes the token so it can never be used again.
    """
    request.auth.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET', 'PATCH'])
def me(request):
    """
    GET   /api/auth/me/  -> who am I?
    PATCH /api/auth/me/  -> update my name or email
    """
    if request.method == 'PATCH':
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(UserSerializer(request.user).data)


@api_view(['POST'])
def change_password(request):
    """
    POST /api/auth/change-password/
    Changes the password, logs out old sessions and returns a new token.
    """
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)

    user = request.user
    user.set_password(serializer.validated_data['new_password'])
    user.save()

    Token.objects.filter(user=user).delete()
    token = Token.objects.create(user=user)
    return Response({'token': token.key})
