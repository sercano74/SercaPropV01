"""
Django settings for SercaProp project.
"""
# ==================================================
# ====================  ACCESO =====================
# ==================================================
# En CMD entrar al:
#* venv\scripts\activate
#* python manage.py runserver
# ==================================================
# rol       : superuser
# usuario   : admin
# email     : ordered.dev.01@gmail.com
# kw        : 123
# ==================================================
# rol       : gerente
# usuario   : Gerente
# email     : sercapropgerente@gmail.com
# kw        : 123
# ==================================================
# rol       : corredor
# usuario   : Danna Smith 
# email     : cannobbiosergio9@gmail.com
# kw        : 123
# ==================================================
# rol       : usuario base
# usuario   : Luis Pitersen
# email     : sergiocannobbio@libertarios6r.lat
# kw        : 123
# ==================================================
# rol       : usuario base
# usuario   : Sergio Pérez
# email     : sergiocannobbio@gmail.com
# kw        : 123
# ==================================================


import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-_)doxtosak_g=*ilerp#=6pkm=s_5%ycju13=#lps-hl%v0gaf'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'a00seg',
    'a01Com',
    'a03Prop',
    'a07serv',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'SercaProp.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'a00seg.context_processors.site_info',
            ],
        },
    },
]

WSGI_APPLICATION = 'SercaProp.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'a00seg.User'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Almacenamiento local (reemplaza Cloudinary que tenía credenciales placeholder)
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# ─────────────────────────────────────────────────────────
# CONFIGURACIÓN DE EMAIL
# ─────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'ordered.dev.01@gmail.com'
EMAIL_HOST_PASSWORD = 'xdkykfxczxbxeszf'
DEFAULT_FROM_EMAIL = 'Serca Propiedades <ordered.dev.01@gmail.com>'

# Tiempo de expiración del token de confirmación de email (en horas)
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_HOURS = 48
