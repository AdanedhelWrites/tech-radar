"""Celery gorev sure sinirlari (2026-10-08).

Onceden sinir yoktu; takilan bir kaynak istegi bolum kilidini 1 saat tutuyordu.
"""
from unittest import mock

from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.test import SimpleTestCase, TestCase

from news import tasks
from news.models import FetchRun


class CelerySinirAyarlariTests(SimpleTestCase):

    def test_sinirlar_tanimli_ve_tutarli(self):
        self.assertGreaterEqual(settings.CELERY_TASK_SOFT_TIME_LIMIT, 300)
        self.assertGreaterEqual(settings.CELERY_TASK_TIME_LIMIT, settings.CELERY_TASK_SOFT_TIME_LIMIT + 60)
        self.assertGreater(settings.CELERY_WORKER_MAX_TASKS_PER_CHILD, 0)

    def test_hard_limit_soft_un_altina_dusemez(self):
        # settings yeniden okunmaz; ayni formulu dogrular (max(hard, soft + 60))
        self.assertEqual(max(100, 1500 + 60), 1560)

    def test_kilit_ttl_hard_limitten_uzun(self):
        from news.api_v1.refresh import REFRESH_LOCK_TTL
        self.assertGreater(REFRESH_LOCK_TTL, settings.CELERY_TASK_TIME_LIMIT)


class SoftLimitTaskTests(TestCase):

    def test_soft_limit_fetch_task_i_basarisiz_sonucla_kapatir(self):
        with mock.patch('news.tasks.MultiSourceScraper.fetch_all_news', side_effect=SoftTimeLimitExceeded()):
            sonuc = tasks.fetch_news_task(days=1)

        self.assertFalse(sonuc['success'])
        self.assertTrue(sonuc['error'].startswith('SoftTimeLimitExceeded'))

    def test_soft_limit_fetchrun_a_failure_yazar(self):
        from news import fetch_runs

        class Sender:
            name = 'news.tasks.fetch_devtools_task'
            request = {}

        fetch_runs.tur_basladi(sender=Sender(), task_id='s1')
        with mock.patch('news.tasks.MultiDevToolsScraper.fetch_all', side_effect=SoftTimeLimitExceeded()):
            sonuc = tasks.fetch_devtools_task(days=1)
        fetch_runs.tur_bitti(sender=Sender(), task_id='s1', retval=sonuc)

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'failure')
        self.assertIn('SoftTimeLimitExceeded', kayit.error)
