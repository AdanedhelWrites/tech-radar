"""Loglama bicimi (2026-10-08).

Onceden scraper'lar ve ceviri katmani print() kullaniyordu: konteyner stdout'unda
gorunuyordu ama seviye, kaynak modul ve zaman yoktu; "hangi kaynak ne siklikla hata
veriyor" sorusu loglardan cevaplanamiyordu. Artik her modul logging.getLogger(__name__)
ile yazar; bicim ortamdan secilir:

  LOG_LEVEL   INFO (varsayilan) | DEBUG | WARNING ...
  LOG_FORMAT  text (varsayilan; "2026-10-08 17:05:32 INFO news.devtools_scraper: ...")
              json (satir basina bir JSON nesnesi; Loki/ELK icin)

Bagimlilik eklenmez; JSON formatlayici stdlib ile yazilmistir.
"""
import json
import logging
import os
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Satir basina bir JSON nesnesi: ts, level, logger, msg (+ exc, + ekstra alanlar)."""

    # LogRecord'un standart alanlari; bunlarin disinda kalan `extra` alanlari aynen gecer
    _STANDART = set(vars(logging.makeLogRecord({}))) | {'message', 'asctime'}

    def format(self, record):
        govde = {
            'ts': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec='milliseconds'),
            'level': record.levelname,
            'logger': record.name,
            'msg': record.getMessage(),
        }
        if record.exc_info:
            govde['exc'] = self.formatException(record.exc_info)
        for ad, deger in record.__dict__.items():
            if ad not in self._STANDART and not ad.startswith('_'):
                govde[ad] = deger
        return json.dumps(govde, ensure_ascii=False, default=str)


def loglama_ayari(ortam=os.environ) -> dict:
    """Django LOGGING sozlugu. Celery worker'da da gecerli olsun diye
    CELERY_WORKER_HIJACK_ROOT_LOGGER=False ile birlikte kullanilir (settings.py)."""
    seviye = (ortam.get('LOG_LEVEL') or 'INFO').upper()
    bicim = (ortam.get('LOG_FORMAT') or 'text').lower()
    formatter = 'json' if bicim == 'json' else 'text'
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'text': {
                'format': '%(asctime)s %(levelname)s %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'json': {'()': 'cybernews.loglama.JsonFormatter'},
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': formatter,
            },
        },
        'root': {'handlers': ['console'], 'level': seviye},
        'loggers': {
            # Uygulama modulleri root'a akar; Django/Celery'nin kendi gurultusu WARNING'de kalir
            'django': {'level': 'WARNING', 'propagate': True},
            'django.request': {'level': 'WARNING', 'propagate': True},
            'celery': {'level': 'INFO', 'propagate': True},
            'news': {'level': seviye, 'propagate': True},
            'scraper_multi': {'level': seviye, 'propagate': True},
            'cybernews': {'level': seviye, 'propagate': True},
        },
    }
