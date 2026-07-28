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
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Seguridad ──────────────────────────────────────
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-_)doxtosak_g=*ilerp#=6pkm=s_5%ycju13=#lps-hl%v0gaf'
)
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.environ.get(
    'DJANGO_ALLOWED_HOSTS',
    '.railway.app,.serca.online,web-production-5f792c.up.railway.app,localhost,127.0.0.1'
).split(',')

# ── Apps ───────────────────────────────────────────
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
    'whitenoise.middleware.WhiteNoiseMiddleware',  # para servir estáticos en prod
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

# ── Base de datos ──────────────────────────────────
# Railway: DATABASE_URL (inyectado al conectar Postgres)
# Railway también inyecta PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD
# si el Postgres está vinculado al servicio web.
# Local: SQLite.
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
    }
elif os.environ.get('PGHOST'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('PGDATABASE', 'railway'),
            'USER': os.environ.get('PGUSER', 'postgres'),
            'PASSWORD': os.environ.get('PGPASSWORD', ''),
            'HOST': os.environ.get('PGHOST', 'localhost'),
            'PORT': os.environ.get('PGPORT', '5432'),
        }
    }
else:
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

# ── Archivos estáticos (Whitenoise) ───────────────
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ── Archivos subidos por usuarios ─────────────────
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'a00seg.User'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Almacenamiento local
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# ── Email ──────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'sergio.cannobbio@gmail.com'
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = 'Serca Propiedades <sergio.cannobbio@gmail.com>'

# Tiempo de expiración del token de confirmación de email (en horas)
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_HOURS = 48

# ── Seguridad para producción ─────────────────────
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
