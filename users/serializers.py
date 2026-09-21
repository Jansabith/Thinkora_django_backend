from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from .models import AVATAR_COLORS, AVATAR_ICONS, User


def check_password_strength(password, user, field_name='password'):
    """Run Django's password rules (minimum length, too common, all numbers, ...)."""
    try:
        password_validation.validate_password(password, user)
    except DjangoValidationError as error:
        raise serializers.ValidationError({field_name: list(error.messages)})


def check_email_is_free(email, current_user=None):
    """Make sure no other account uses this email (ignoring upper/lower case)."""
    users_with_email = User.objects.filter(email__iexact=email)
    if current_user is not None:
        users_with_email = users_with_email.exclude(pk=current_user.pk)
    if users_with_email.exists():
        raise serializers.ValidationError('An account with this email already exists.')
    return email.lower()


class UserSerializer(serializers.ModelSerializer):
    """The logged-in user's own information. Never includes the password."""

    # The user's real rights (the Main Admin always has both).
    can_manage_students = serializers.BooleanField(source='may_manage_students', read_only=True)
    can_manage_content = serializers.BooleanField(source='may_manage_content', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'role',
            'access_status',
            'avatar_color',
            'avatar_icon',
            'can_manage_students',
            'can_manage_content',
            'date_joined',
        ]


class RequestAccessSerializer(serializers.ModelSerializer):
    """The data a student sends from the 'Get Access' form."""

    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
            'username',
            'password',
            'confirm_password',
            'request_message',
            'whatsapp_number',
        ]
        extra_kwargs = {
            'first_name': {'required': True, 'allow_blank': False},
            'last_name': {'required': True, 'allow_blank': False},
            'email': {'required': True, 'allow_blank': False},
        }

    def validate_email(self, value):
        return check_email_is_free(value)

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'The two passwords do not match.'})

        # An unsaved User lets Django check "password is too similar to your username".
        future_user = User(
            username=data['username'],
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
        )
        check_password_strength(data['password'], future_user)
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        # create_user() hashes the password for us.
        return User.objects.create_user(
            **validated_data,
            role=User.Role.STUDENT,
            access_status=User.AccessStatus.PENDING,
            is_active=False,  # cannot log in until an admin approves
        )


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


class ProfileSerializer(serializers.ModelSerializer):
    """The fields a logged-in user may change about themselves."""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'avatar_color', 'avatar_icon']
        extra_kwargs = {'email': {'required': True, 'allow_blank': False}}

    def validate_email(self, value):
        return check_email_is_free(value, current_user=self.instance)

    def validate_avatar_color(self, value):
        # Empty means "go back to the automatic colour made from my name".
        if value and value not in AVATAR_COLORS:
            raise serializers.ValidationError(f'Choose one of: {", ".join(AVATAR_COLORS)}.')
        return value

    def validate_avatar_icon(self, value):
        if value and value not in AVATAR_ICONS:
            raise serializers.ValidationError(f'Choose one of: {", ".join(AVATAR_ICONS)}.')
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError('Your current password is not correct.')
        return value

    def validate(self, data):
        check_password_strength(data['new_password'], self.context['request'].user, 'new_password')
        return data


class StudentSerializer(serializers.ModelSerializer):
    """What admins see about a student."""

    reviewed_by = serializers.SlugRelatedField(slug_field='username', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'access_status',
            'is_active',
            'avatar_color',
            'avatar_icon',
            'request_message',
            'whatsapp_number',
            'allowed_courses',
            'date_joined',
            'last_login',
            'reviewed_by',
            'reviewed_at',
        ]


class StudentUpdateSerializer(serializers.ModelSerializer):
    """
    What an admin may change about a student: name, email and optionally a new password.
    Access (approve / reject) has its own endpoints, so it cannot be changed here.
    """

    password = serializers.CharField(
        write_only=True, required=False, allow_blank=True, style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password', 'whatsapp_number', 'allowed_courses']
        extra_kwargs = {'email': {'required': True, 'allow_blank': False}}

    def validate_email(self, value):
        return check_email_is_free(value, current_user=self.instance)

    def validate(self, data):
        if data.get('password'):
            check_password_strength(data['password'], self.instance)
        return data

    def update(self, instance, validated_data):
        password = validated_data.pop('password', '')
        student = super().update(instance, validated_data)
        if password:
            student.set_password(password)
            student.save()
            # The student must log in again with the new password.
            Token.objects.filter(user=student).delete()
        return student

    def to_representation(self, instance):
        # Answer with the full student information.
        return StudentSerializer(instance).data


class AdminAccountSerializer(serializers.ModelSerializer):
    """What the Main Admin sees and edits about an admin account."""

    password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_active',
            'can_manage_students',
            'can_manage_content',
            'date_joined',
            'last_login',
            'password',
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
        extra_kwargs = {'email': {'required': True, 'allow_blank': False}}

    def validate_email(self, value):
        return check_email_is_free(value, current_user=self.instance)

    def validate(self, data):
        password = data.get('password')
        if self.instance is None and not password:
            raise serializers.ValidationError({'password': 'A password is required for a new admin.'})
        if password:
            user = self.instance or User(username=data.get('username', ''), email=data.get('email', ''))
            check_password_strength(password, user)
        return data

    def create(self, validated_data):
        password = validated_data.pop('password')
        return User.objects.create_user(
            **validated_data,
            password=password,
            role=User.Role.ADMIN,
            access_status=User.AccessStatus.APPROVED,
        )

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        admin = super().update(instance, validated_data)
        if password:
            admin.set_password(password)
            admin.save()
        # A disabled admin, or one with a new password, must log in again.
        if password or not admin.is_active:
            Token.objects.filter(user=admin).delete()
        return admin
