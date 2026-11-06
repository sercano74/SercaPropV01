"""
Django settings for SercaProp project.

Las credenciales NO viven aquí. Están en .env (desarrollo) o en las variables
de entorno del servidor (producción). Ver .env.example para la lista completa
de claves que hay que definir.

Arranque local:
    venv\\Scripts\\activate
    python manage.py runserver

Las cuentas de prueba se crean con `python manage.py createsuperuser` o con
`python scripts/crear_superuser.py`; no se documentan contraseñas en el código.
"""


import logging
import os
import socket
import warnings
from pathlib import Path
from urllib.parse import urlsplit

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Variables de entorno ───────────────────────────
# Todo lo sensible (claves de Django, Cloudinary, correo, base de datos) vive
# en .env o en las variables del servidor, nunca en este archivo.
# override=False es deliberado: en Railway las variables las inyecta la
# plataforma y deben ganar sobre el .env local, que solo rellena lo que falte.
load_dotenv(BASE_DIR / '.env', override=False)


# ── Seguridad ──────────────────────────────────────
# Sin SECRET_KEY no hay sesiones ni tokens válidos. Se exige en producción.
# La clave de emergencia se mantiene solo para que un despliegue antiguo sin
# la variable definida no se caiga, pero avisa en los logs para que se corrija.
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

_SECRET_KEY_EMERGENCIA = 'django-insecure-_)doxtosak_g=*ilerp#=6pkm=s_5%ycju13=#lps-hl%v0gaf'
_SECRET_KEY_ENV = os.environ.get('DJANGO_SECRET_KEY')
SECRET_KEY = _SECRET_KEY_ENV or _SECRET_KEY_EMERGENCIA
if not _SECRET_KEY_ENV:
    warnings.warn(
        'DJANGO_SECRET_KEY no está definida: se usa la clave de emergencia, '
        'que es pública. Define DJANGO_SECRET_KEY en el servidor.',
        RuntimeWarning,
    )
    logging.getLogger(__name__).warning(
        'DJANGO_SECRET_KEY no definida: usando la clave de emergencia pública.'
    )

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
    'django.contrib.sitemaps',  # SEO: generación de sitemap.xml
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

ACCOUNT_EMAIL_VERIFICATION = 'optional'
# ACCOUNT_LOGIN_METHODS y ACCOUNT_SIGNUP_FIELDS reemplazan a
# ACCOUNT_AUTHENTICATION_METHOD y ACCOUNT_EMAIL_REQUIRED (deprecados en allauth)
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*', 'first_name', 'last_name']
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 2
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[Serca Propiedades] '
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


def _host_interno_inalcanzable(url):
    """¿La URL apunta a un dominio .railway.internal que aquí no resuelve?

    Railway entrega DATABASE_URL con el host interno (postgres.railway.internal),
    que solo existe dentro de su red. Cuando se ejecuta un comando desde el PC
    con `railway run`, ese nombre no resuelve y la conexión falla. En ese caso
    hay que usar DATABASE_PUBLIC_URL, que Railway publica cuando el Postgres
    tiene el TCP Proxy habilitado. Dentro de Railway el nombre sí resuelve y se
    sigue usando la URL interna, que es la vía rápida y no sale a internet.
    """
    host = urlsplit(url).hostname or ''
    if not host.endswith('.railway.internal'):
        return False
    try:
        socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True
    return False


DATABASE_PUBLIC_URL = os.environ.get('DATABASE_PUBLIC_URL')
if DATABASE_URL and DATABASE_PUBLIC_URL and _host_interno_inalcanzable(DATABASE_URL):
    DATABASE_URL = DATABASE_PUBLIC_URL

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
# Sin credenciales en el código: salen del .env (o de las variables del
# servidor). Se admiten las tres partes por separado o la CLOUDINARY_URL ya
# armada; si solo vienen las partes, la URL se compone aquí.
CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY', '')
CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')

CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL', '')

if CLOUDINARY_URL:
    # Con solo la URL ya se pueden rellenar las tres partes: el formato es
    # cloudinary://API_KEY:API_SECRET@CLOUD_NAME. Así CLOUDINARY_STORAGE queda
    # completo aunque el servidor solo defina CLOUDINARY_URL.
    _partes_cloudinary = urlsplit(CLOUDINARY_URL)
    CLOUDINARY_CLOUD_NAME = CLOUDINARY_CLOUD_NAME or (_partes_cloudinary.hostname or '')
    CLOUDINARY_API_KEY = CLOUDINARY_API_KEY or (_partes_cloudinary.username or '')
    CLOUDINARY_API_SECRET = CLOUDINARY_API_SECRET or (_partes_cloudinary.password or '')
elif all((CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET)):
    CLOUDINARY_URL = (
        f'cloudinary://{CLOUDINARY_API_KEY}:{CLOUDINARY_API_SECRET}'
        f'@{CLOUDINARY_CLOUD_NAME}'
    )

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': CLOUDINARY_CLOUD_NAME,
    'API_KEY': CLOUDINARY_API_KEY,
    'API_SECRET': CLOUDINARY_API_SECRET,
}

# Almacenamiento de medios en Cloudinary para persistencia en Railway
# DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# ── Configuración moderna de Almacenamiento (Django 4.2+) ──
# El storage por defecto es propio (a00seg.storage.SercaMediaStorage) porque
# cloudinary_storage.storage.MediaCloudinaryStorage sube TODO como
# resource_type='image' y Cloudinary rechaza ahí los documentos que no son
# imagen ni PDF (subir un Word devolvía "Unsupported ZIP file" y el usuario
# veía la página 500). El storage propio enruta cada archivo a image, video o
# raw según su extensión.
STORAGES = {
    "default": {
        "BACKEND": "a00seg.storage.SercaMediaStorage",
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
# Valor especial: EMAIL_BACKEND=resend  -> usa la API HTTP de Resend
# (más robusto que SMTP desde Railway: evita el WORKER TIMEOUT por puerto 587
# bloqueado/colgado en IPs de datacenter).
_EMAIL_BACKEND_ENV = os.environ.get('EMAIL_BACKEND', '')
_EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
# Con Resend se usa la API HTTP (https) en vez del SMTP (puerto 587): desde las
# IPs de datacenter de Railway el SMTP se cuelga (TimeoutError) y gunicorn mata
# el worker. La API responde en ms y funciona desde cualquier IP.
# Se activa con EMAIL_BACKEND=resend o automáticamente si EMAIL_HOST es de
# resend.com (así no hay que tocar nada en Railway).
_usar_api_resend = _EMAIL_BACKEND_ENV == 'resend' or (
    not _EMAIL_BACKEND_ENV and 'resend.com' in _EMAIL_HOST
)
if _usar_api_resend:
    EMAIL_BACKEND = 'a00seg.email_backends.ResendAPIBackend'
    # La key se lee de RESEND_API_KEY y, si no está, de EMAIL_HOST_PASSWORD
    # (que en Railway guarda la key de Resend).
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '') or os.environ.get('EMAIL_HOST_PASSWORD', '')
else:
    EMAIL_BACKEND = _EMAIL_BACKEND_ENV or 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = _EMAIL_HOST
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_DEFAULT_FROM = os.environ.get('EMAIL_DEFAULT_FROM', 'Serca Propiedades <noreply@serca.online>')
DEFAULT_FROM_EMAIL = EMAIL_DEFAULT_FROM
# Remitente "no-reply" para correos transaccionales (visitas, avisos, notificaciones).
# Usa el dominio verificado en Resend (noreply@serca.online) y hace fallback al DEFAULT_FROM_EMAIL.
EMAIL_NOREPLY_FROM = os.environ.get(
    'EMAIL_NOREPLY_FROM',
    'Serca Propiedades <noreply@serca.online>'
)
# Timeout corto de conexión SMTP: evita que gunicorn (30s) mate el worker con
# un WORKER TIMEOUT si el relay tarda. La request responde en máx. ~12s y, si
# falla, se muestra el error real y el usuario puede reintentar.
EMAIL_TIMEOUT = 10

# ── Sitio ───────────────────────────────────────────
SITE_NAME = 'Serca Propiedades'
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'propiedades.serca.online')

# ── Seguridad para producción ─────────────────────
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    # *PRESERVE_WHITESPACE_ON_WWW_REDIRECT = os.environ.get('PRESERVE_WHITESPACE_ON_WWW_REDIRECT', 'False').lower() in ('true', '1', 'yes')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


GA4_MEASUREMENT_ID = os.environ.get('GA4_MEASUREMENT_ID', '')
