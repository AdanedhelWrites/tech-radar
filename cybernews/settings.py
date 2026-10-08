"""
Django settings for cybernews project.

Environment variable'lar ile tamamen konfigüre edilebilir.
Docker Compose ve Kubernetes ortamlarında çalışır.
"""

import os
from pathlib import Path

from csp.constants import NONCE, NONE, SELF, UNSAFE_INLINE

from cybernews.ayar_dogrulama import dogrulanmis_secret_key, veritabani_ayari
from cybernews.loglama import loglama_ayari

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# DEBUG=False iken bos, ornek veya zayif anahtarla acilmayi reddeder (GUVENLIK-PLANI P4)
SECRET_KEY = dogrulanmis_secret_key(os.environ.get('SECRET_KEY'), DEBUG)

# ALLOWED_HOSTS — virgülle ayrılmış liste; '*' yalnizca acikca verilirse
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if host.strip()
]

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
    'drf_spectacular',
    'drf_spectacular_sidecar',
    'news',
    'django_celery_beat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # CSP ve diger guvenlik basliklari WhiteNoise'dan ONCE: statik dosya yanitlari da baslik tasir
    'csp.middleware.CSPMiddleware',
    'cybernews.guvenlik_basliklari.GuvenlikBasliklariMiddleware',
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

# Content-Security-Policy (django-csp 4; ZAP 10038, GUVENLIK-PLANI 2026-10-08).
# Backend'in HTML yuzeyi admin, /api/v1/docs/ ve hata sayfalaridir; React arayuzu ayri sunucudan gelir.
# script-src: yalniz 'self' + istek basina nonce (admin sablonlarinda inline script yok; Swagger UI
# SpectacularSwaggerSplitView ile ayri script URL'si kullanir). style-src 'unsafe-inline': drf-spectacular
# sablonundaki <style> blogu ve Swagger UI'nin kendi stilleri icin; inline stil dusuk risklidir.
CONTENT_SECURITY_POLICY = {
    'DIRECTIVES': {
        'default-src': [SELF],
        'script-src': [SELF, NONCE],
        'style-src': [SELF, UNSAFE_INLINE],
        'img-src': [SELF, 'data:'],
        'font-src': [SELF, 'data:'],
        'connect-src': [SELF],
        'object-src': [NONE],
        'base-uri': [SELF],
        'form-action': [SELF],
        'frame-ancestors': [NONE],
    },
}

# WhiteNoise varsayilani statik dosyalara Access-Control-Allow-Origin: * ekler (ZAP 10098
# "Cross-Domain Misconfiguration"). Statik dosyalar yalniz ayni origin'den (admin, docs) ve frontend
# proxy'sinden tuketilir; cross-origin erisime gerek yok.
WHITENOISE_ALLOW_ALL_ORIGINS = False

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
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# Sema yalnizca /api/v1/ icindir. DEFAULT_SCHEMA_CLASS global bir ayardir ve
# teknik olarak eski /api/* view'larini da kapsar, ama davranissal etkisi
# yoktur: sema sinifi yalnizca sema uretiminde kullanilir, istek isleme
# yolunda degil. Eski uclar ayrica asagidaki hook ile semadan tamamen elenir.
SPECTACULAR_SETTINGS = {
    'TITLE': 'CyberNews Entegrasyon API',
    'DESCRIPTION': (
        'Dis tuketiciler icin imlecli delta senkron API. Tuketici tarafi upsert '
        'olmalidir ve birlestirme anahtari `id` DEGILDIR: `cve` bolumunde '
        '`cve_id`, diger bes bolumde `link` kullanilir. Ayrinti icin README '
        'icindeki "Entegrasyon API" bolumune bakiniz.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'PREPROCESSING_HOOKS': ['news.api_v1.schema.yalniz_v1'],
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
}

ROOT_URLCONF = 'cybernews.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

# Database — DB_HOST doluysa PostgreSQL; bossa yalniz DEBUG=True iken SQLite (Faz B1)
DATABASES = veritabani_ayari(os.environ, DEBUG, BASE_DIR)

# Cache — Redis
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0'),
        # Cache blob sekli (serializer alanlari) degistiginde artirilir; eski
        # surumdeki bloblar okunmaz ve 1 saat icinde kendiliginden duser.
        # DRF throttle sayaclari da bu surume tabidir (artirinca bir kez sifirlanir).
        "VERSION": 3,
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
# Django 5.1 STATICFILES_STORAGE'i kaldirdi; yerini STORAGES sozlugu aldi.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Loglama (2026-10-08): scraper ve ceviri katmani print yerine logging kullanir.
# LOG_LEVEL (INFO) ve LOG_FORMAT (text | json) ortamdan; bkz. cybernews/loglama.py.
LOGGING = loglama_ayari(os.environ)

# Yerel LibreTranslate servisi: cekim aninda tek ceviri saglayicisi.
# Bos ise hic denenmez (bkz. news/translation_providers.py).
LIBRETRANSLATE_URL = os.environ.get('LIBRETRANSLATE_URL', '')

# Gemini API (retranslate'te kayit duzeyinde yukseltme; bkz. news/gemini.py).
# Bos ise Gemini hic denenmez. Deger yalniz ortam degiskeninden gelir.
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

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

# Celery varsayilan olarak root logger'i ele gecirip kendi handler'ini kurar; o zaman
# worker'da LOGGING (bicim, seviye, JSON) gecersiz kalirdi. Worker da Django ayarini kullanir.
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

# Gorev sure sinirlari (2026-10-08). Onceden yoktu: takilan tek bir kaynak istegi
# bolum kilidini REFRESH_LOCK_TTL (3600 sn) boyunca tutar, worker tek concurrency ile
# calistigi icin Beat'in diger gorevleri kuyrukta beklerdi.
#   soft: task icinde SoftTimeLimitExceeded yukselir; fetch task'lari bunu yakalayip
#         {'success': False, 'error': 'SoftTimeLimitExceeded: ...'} doner, FetchRun 'failure' olur.
#   hard: worker alt surecini oldurur; FetchRun 'running' kalir (fetch_runs.py), bolum
#         kilidi TTL sonunda kendiliginden duser. Soft'tan en az 60 sn buyuk tutulur.
# En uzun gozlenen cekim 751 sn (CVE, 2026-09-12); 12 haber kaynagiyla ~15 dk beklenir.
CELERY_TASK_SOFT_TIME_LIMIT = int(os.environ.get('CELERY_TASK_SOFT_TIME_LIMIT', '1500'))
CELERY_TASK_TIME_LIMIT = max(int(os.environ.get('CELERY_TASK_TIME_LIMIT', '1800')),
                             CELERY_TASK_SOFT_TIME_LIMIT + 60)
# Uzun omurlu alt surecte requests oturumlari ve BeautifulSoup agaclari birikmesin
CELERY_WORKER_MAX_TASKS_PER_CHILD = int(os.environ.get('CELERY_WORKER_MAX_TASKS_PER_CHILD', '50'))

# Celery Beat — tum bolumler 6 saatte bir otomatik cekilir.
# Ceviri bekleyen kayitlar 2 saatte bir (tek saatlerde) yeniden cevrilir.
# Bolumler worker ve ceviri yukunu dagitmak icin 10 dk arayla kaydirilir.
# skip_existing=True: sadece yeni kayitlar cevrilir (ceviri saglayicisinin kotasi korunur).
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
