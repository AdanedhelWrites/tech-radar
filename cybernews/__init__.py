# Cybernews Django Project

# Celery uygulamasi Django ile birlikte yuklenmeli; aksi halde task'lar Celery'nin
# 'default' uygulamasina baglanir ve sonuc backend'i devre disi kalir.
from .celery import app as celery_app

__all__ = ('celery_app',)
