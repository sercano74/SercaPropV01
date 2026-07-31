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
# usuario   : Sergio Cannobbio
# email     : sergio.cannobbio@gmail.com
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
    'a00seg',  # antes que cloudinary_storage para que su comando collectstatic estándar tenga prioridad
    'cloudinary_storage',  # DEBE ir antes de django.contrib.staticfiles
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.sites',  # requerido por allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'allauth.socialaccount.providers.facebook',
    'cloudinary',
    'a01Com',
    'a03Prop',
    'a07serv',
]

# ── Middleware ──────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',  # requerido por allauth
]

# ── Autenticación (django-allauth) ──────────────────
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1

ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*', 'first_name', 'last_name']
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 2
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[Serca Propiedades] '
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_CONFIRM_EMAIL_ON_GET = True # Permite confirmar el correo al hacer clic en el link sin pedir POST
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = True
ACCOUNT_SESSION_REMEMBER = True

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
ACCOUNT_SIGNUP_REDIRECT_URL = '/'

ACCOUNT_ADAPTER = 'a00seg.allauth_adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'a00seg.allauth_adapters.CustomSocialAccountAdapter'

# Formulario personalizado para el registro
ACCOUNT_FORMS = {
    'signup': 'a00seg.forms.CustomSignupForm',
}

# Configuración de proveedores sociales
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
            'secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
            'key': '',
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        'FETCH_USERINFO': True,
    },
    'facebook': {
        'APP': {
            'client_id': os.environ.get('FACEBOOK_CLIENT_ID', ''),
            'secret': os.environ.get('FACEBOOK_CLIENT_SECRET', ''),
            'key': '',
        },
        'METHOD': 'oauth2',
        'SCOPE': ['email', 'public_profile'],
        'FIELDS': ['id', 'email', 'first_name', 'last_name', 'name'],
        'EXCHANGE_TOKEN': True,
        'VERIFIED_EMAIL': False,
        'VERSION': 'v18.0',
    },
}

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
# Usamos StaticFilesStorage (sin manifest ni compresión en build) porque el
# post-procesado de whitenoise falla con Django 6.0 (MissingFileError /
# FileNotFoundError). WhiteNoise sigue sirviendo los estáticos en runtime.
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# ── Archivos subidos por usuarios (Cloudinary) ───
CLOUDINARY_URL = os.environ.get(
    'CLOUDINARY_URL',
    'cloudinary://914777239115561:FFFOUSftuKP_Z6Z4MieCBbIaIRY@dtcskupwr'
)

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': 'dtcskupwr',
    'API_KEY': '914777239115561',
    'API_SECRET': 'FFFOUSftuKP_Z6Z4MieCBbIaIRY',
}

# Almacenamiento de medios en Cloudinary para persistencia en Railway
# DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# ── Configuración moderna de Almacenamiento (Django 4.2+) ──
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

MEDIA_URL = '/media/'  # fallback local
MEDIA_ROOT = BASE_DIR / 'media'  # fallback local

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'a00seg.User'

# ── Email ──────────────────────────────────────────
# Configurable por variables de entorno para poder usar un relay transaccional
# (Mailgun/SendGrid/Resend) en producción sin tocar código. Por defecto SMTP Gmail.
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'ordered.dev.01@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'lulicoglmtgsfeed')
EMAIL_DEFAULT_FROM = os.environ.get('EMAIL_DEFAULT_FROM', 'sercaprop <ordered.dev.01@gmail.com>')
DEFAULT_FROM_EMAIL = EMAIL_DEFAULT_FROM
# Timeout de conexión SMTP: si el servidor de correo/red tarda, la request falla
# con mensaje claro en lugar de quedar colgada esperando indefinidamente.
EMAIL_TIMEOUT = 20

# ── Sitio ───────────────────────────────────────────
SITE_NAME = 'Serca Propiedades'
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'propiedades.serca.online')

# ── Seguridad para producción ─────────────────────
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
