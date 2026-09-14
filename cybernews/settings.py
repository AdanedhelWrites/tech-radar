"""
Django settings for cybernews project.

Environment variable'lar ile tamamen konfigüre edilebilir.
Docker Compose ve Kubernetes ortamlarında çalışır.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# ALLOWED_HOSTS — virgülle ayrılmış liste veya '*'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'news',
    'django_celery_beat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORS settings — environment variable ile genişletilebilir
_cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
CORS_ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins.split(',') if origin.strip()]

CORS_ALLOW_CREDENTIALS = True

# CSRF — Vite dev proxy (changeOrigin) Host basligini degistirdigi icin
# frontend origin'i acikca guvenilir sayilmali (admin oturumuyla yapilan POST'lar icin)
_csrf_origins = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in _csrf_origins.split(',') if origin.strip()]

# DRF settings
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # v1 entegrasyon katmani throttle oranlari. Siniflar view uzerinde tanimli;
    # buradaki oranlar ScopedRateThrottle tarafindan okunur. Mevcut /api/* uc
    # noktalari etkilenmez.
    'DEFAULT_THROTTLE_RATES': {
        'v1_read': '120/min',
        'v1_refresh': '12/hour',
    },
}

ROOT_URLCONF = 'cybernews.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'cybernews.wsgi.application'

# Database — PostgreSQL (Kubernetes/Production) veya SQLite (lokal geliştirme)
# DATABASE_URL set edilmişse PostgreSQL, yoksa SQLite kullanılır
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # PostgreSQL: DATABASE_URL=postgres://user:pass@host:port/dbname
    # Veya ayrı ayrı env var'lar ile
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'cybernews'),
            'USER': os.environ.get('DB_USER', 'cybernews'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
            'CONN_MAX_AGE': 600,
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }
else:
    # Lokal geliştirme için SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Cache — Redis
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0'),
        # Cache blob sekli (serializer alanlari) degistiginde artirilir; eski
        # surumdeki bloblar okunmaz ve 1 saat icinde kendiliginden duser.
        # DRF throttle sayaclari da bu surume tabidir (artirinca bir kez sifirlanir).
        "VERSION": 2,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'tr-tr'
TIME_ZONE = 'Europe/Istanbul'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Yerel LibreTranslate servisi: Google kapaliyken devreye giren yedek ceviri
# saglayicisi. Bos ise hic denenmez (bkz. news/translation_providers.py).
LIBRETRANSLATE_URL = os.environ.get('LIBRETRANSLATE_URL', '')

# Testler canli LibreTranslate'e ve canli ceviri devre kesicisine dokunmaz.
TEST_RUNNER = 'news.test_runner.GuvenliTestRunner'

# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/1')
CELERY_RESULT_BACKEND = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Istanbul'

# Worker isi aldiginda durum STARTED olur; aksi halde is bitene kadar PENDING gorunur.
# /api/v1/jobs/<id>/ uc noktasinin 'started' durumunu gosterebilmesi icin gerekli.
CELERY_TASK_TRACK_STARTED = True

# Celery Beat — tum bolumler 6 saatte bir otomatik cekilir.
# Ceviri bekleyen kayitlar 2 saatte bir (tek saatlerde) yeniden cevrilir.
# Bolumler worker ve ceviri yukunu dagitmak icin 10 dk arayla kaydirilir.
# skip_existing=True: sadece yeni kayitlar cevrilir (Google Translate kotasi korunur).
# Gun araligi task varsayilanidir (manuel "Getir" ile ayni davranis).
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'fetch-news-every-6h': {
        'task': 'news.tasks.fetch_news_task',
        'schedule': crontab(minute=0, hour='*/6'),
        'kwargs': {'skip_existing': True},
    },
    'fetch-cve-every-6h': {
        'task': 'news.tasks.fetch_cve_task',
        'schedule': crontab(minute=10, hour='*/6'),
        'kwargs': {'skip_existing': True},
    },
    'fetch-k8s-every-6h': {
        'task': 'news.tasks.fetch_k8s_task',
        'schedule': crontab(minute=20, hour='*/6'),
        'kwargs': {'skip_existing': True},
    },
    'fetch-sre-every-6h': {
        'task': 'news.tasks.fetch_sre_task',
        'schedule': crontab(minute=30, hour='*/6'),
        'kwargs': {'skip_existing': True},
    },
    'fetch-devtools-every-6h': {
        'task': 'news.tasks.fetch_devtools_task',
        'schedule': crontab(minute=40, hour='*/6'),
        'kwargs': {'skip_existing': True},
    },
    'fetch-ai-news-every-6h': {
        'task': 'news.tasks.fetch_ai_news_task',
        'schedule': crontab(minute=50, hour='*/6'),
        'kwargs': {'skip_existing': True},
    },
    # Ceviri bekleyen kayitlari feed'e bakmadan yeniden cevirir. Tek saatlerde
    # calisir: fetch task'lari 00/06/12/18'de calistigi icin hic cakismaz.
    'retranslate-pending-every-2h': {
        'task': 'news.tasks.retranslate_pending_task',
        'schedule': crontab(minute=5, hour='1-23/2'),
    },
}

# Cache timeout
CACHE_TIMEOUT = 3600  # 1 saat
