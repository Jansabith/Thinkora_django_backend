"""
Django settings for the LMS project.

Development works with no extra setup: the defaults below are meant for your own computer.
In production, important values come from ENVIRONMENT VARIABLES (see docs/14-production.md).

For the full list of settings and their values, see
https://docs.djangoproject.com/en/6.1/ref/settings/
"""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default):
    """Read an environment variable as True/False ('true', '1' and 'yes' mean True)."""
    return os.environ.get(name, str(default)).strip().lower() in ('true', '1', 'yes')


def env_list(name, default):
    """Read a comma-separated environment variable as a list: 'a,b' -> ['a', 'b']."""
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool('DJANGO_DEBUG', True)

# SECURITY WARNING: keep the secret key used in production secret!
# The default below is ONLY for development. Production must set DJANGO_SECRET_KEY.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-5w5y@@k-6y55muq!o$!m*zpuc^acc1nqb-0u8&+7l&+l9t0)f-',
)
if not DEBUG and SECRET_KEY.startswith('django-insecure'):
    raise ImproperlyConfigured('Set the DJANGO_SECRET_KEY environment variable when DEBUG is False.')

# Which domain names this Django site may be served on.
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    # Our apps
    'users',
    'courses',
    'questions',
    'videos',
    'progress',
    'activity',
    'tasks',
    'dashboard',
]

MIDDLEWARE = [
    # CorsMiddleware must be high up, before CommonMiddleware,
    # so it can add CORS headers to every response.
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database
# Development: SQLite (a single file, no setup).
# Production: PostgreSQL, used automatically when POSTGRES_DB is set.

if os.environ.get('POSTGRES_DB'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['POSTGRES_DB'],
            'USER': os.environ.get('POSTGRES_USER', ''),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/6.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = []

# Automated tests create many users, and real password hashing is slow ON PURPOSE.
# Only while running 'manage.py test', use a fast hasher. Never used for real accounts.
if 'test' in sys.argv:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']


# Internationalization
# https://docs.djangoproject.com/en/6.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images) used by the Django admin site.
# 'collectstatic' copies them into STATIC_ROOT so Nginx can serve them in production.

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'


# Email
# https://docs.djangoproject.com/en/6.1/topics/email/#topic-email-configuration
# The LMS does not send email yet.
# Development: emails are only printed in the terminal.
# Production:  a real SMTP server, configured with environment variables.

if DEBUG:
    MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.console.EmailBackend',
        },
    }
else:
    MAILERS = {
        'default': {
            'BACKEND': 'django.core.mail.backends.smtp.EmailBackend',
            'OPTIONS': {
                'host': os.environ.get('EMAIL_HOST', 'localhost'),
                'port': int(os.environ.get('EMAIL_PORT', '587')),
                'username': os.environ.get('EMAIL_HOST_USER', ''),
                'password': os.environ.get('EMAIL_HOST_PASSWORD', ''),
                'use_tls': env_bool('EMAIL_USE_TLS', True),
            },
        },
    }


# Use our own User model instead of Django's default one.
# Format: 'app_name.ModelName'
AUTH_USER_MODEL = 'users.User'


# Django REST Framework
REST_FRAMEWORK = {
    # HOW Django finds out who is making a request: the "Authorization: Token <key>" header.
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    # Secure by default: every endpoint needs a logged-in user,
    # unless a view deliberately says otherwise (for example login).
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
if not DEBUG:
    # In production, only send JSON (no browsable HTML API pages).
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = ['rest_framework.renderers.JSONRenderer']


# CORS: which frontend addresses are allowed to call our API from the browser.
# During development, React (Vite) runs on port 5173.
CORS_ALLOWED_ORIGINS = env_list(
    'DJANGO_CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173',
)

# HTTPS addresses allowed to submit forms to Django (needed for the /admin/ site in production).
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS', '')


# Production security settings (only when DEBUG is False)
if not DEBUG:
    # Nginx tells Django the original request used HTTPS.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = env_bool('DJANGO_SESSION_COOKIE_SECURE', True)
    CSRF_COOKIE_SECURE = env_bool('DJANGO_CSRF_COOKIE_SECURE', True)
    # HSTS tells browsers "always use HTTPS for this site". Start small, increase later.
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_SECURE_HSTS_SECONDS', '0'))
