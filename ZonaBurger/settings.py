"""
Django settings for ZonaBurger project.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Cargamos el archivo .env ubicado en la raíz del proyecto
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ==========================================
# VARIABLES DE ENTORNO (Seguridad y Entorno)
# ==========================================
SECRET_KEY = os.getenv('SECRET_KEY')

DEBUG = os.getenv('DEBUG', 'False') == 'True'

# Convierte una lista separada por comas en el .env a una lista de Python
allowed_hosts_env = os.getenv('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = allowed_hosts_env.split(',') if allowed_hosts_env else []


# ==========================================
# APLICACIONES Y MIDDLEWARES
# ==========================================
INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
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

ROOT_URLCONF = 'ZonaBurger.urls'

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

WSGI_APPLICATION = 'ZonaBurger.wsgi.application'


# ==========================================
# BASE DE DATOS
# ==========================================
DATABASES = {
    'default': {
        'ENGINE': 'mssql',
        'NAME': os.getenv('DB_NAME'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT', ''),
        'OPTIONS': {
            'driver': os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server'),
            'trusted_connection': os.getenv('DB_TRUSTED_CONNECTION', 'yes'),
        },
    }
}


# ==========================================
# VALIDACIÓN DE CONTRASEÑAS E INTERNACIONALIZACIÓN
# ==========================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-ar' # Cambiado a español de Argentina (opcional, recomendado)
TIME_ZONE = 'America/Argentina/Buenos_Aires' # Cambiado a zona horaria local (opcional)
USE_I18N = True
USE_TZ = True


# ==========================================
# ARCHIVOS ESTÁTICOS Y CORREO
# ==========================================
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

MAILERS = {
    'default': {
        'BACKEND': 'django.core.mail.backends.console.EmailBackend',
    },
}


# ==========================================
# CONFIGURACIÓN DE JAZZMIN Y TU CSS
# ==========================================
JAZZMIN_SETTINGS = {
    "site_title": "Zona-Burger Admin",
    "site_header": "Zona-Burger",
    "site_brand": "Zona-Burger",
    "site_logo": "img/logo.png",
    "login_logo": "img/logo.png",
    "welcome_sign": "Bienvenido al panel de Zona-Burger",
    "copyright": "", 
    "show_sidebar": True,
    "navigation_expanded": True,
    "custom_css": "css/admin_custom.css",
}

JAZZMIN_UI_TWEAKS = {
    "theme": "darkly",
    "dark_mode_theme": "darkly",
    "navbar": "navbar-dark",
    "sidebar": "sidebar-dark-primary",
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-dark",
    "accent": "accent-primary",
    "navbar_dark": True,
    "navbar_fixed": False,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "show_ui_builder": False,
}