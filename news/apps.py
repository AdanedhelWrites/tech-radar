from django.apps import AppConfig


class NewsConfig(AppConfig):
    name = 'news'
    verbose_name = 'Teknoloji Haberleri'

    def ready(self):
        # Manuel tetiklenen is bitince bolum kilidini birakan Celery sinyali
        from .api_v1 import job_signals  # noqa: F401
