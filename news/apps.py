from django.apps import AppConfig


class NewsConfig(AppConfig):
    name = 'news'
    verbose_name = 'Teknoloji Haberleri'

    def ready(self):
        # Manuel tetiklenen is bitince bolum kilidini birakan Celery sinyali
        from .api_v1 import job_signals  # noqa: F401
        # Her cekim ve retranslate turunu FetchRun satiri olarak kaydeden sinyaller
        from . import fetch_runs  # noqa: F401
