"""Job durum uc noktasi testleri.

Celery sonuc backend'i mock'lanir: AsyncResult canli Redis'teki gercek
sonuclari okumasin ve durumlar deterministik olsun.
"""
from unittest import mock

from django.test import SimpleTestCase

from news.api_v1 import refresh
from news.tests.base import RefreshTestMixin, V1TestCase


class SahteSonuc:
    def __init__(self, state, result=None):
        self.state = state
        self.result = result


class JobUcNoktasiTests(RefreshTestMixin, V1TestCase):

    def setUp(self):
        super().setUp()
        self.baslik = self.token_basligi()
        self.job_id = refresh.trigger('cve').job_id

    def _durum(self, sahte_sonuc, job_id=None):
        with mock.patch('news.api_v1.views.AsyncResult', return_value=sahte_sonuc) as sahte:
            yanit = self.client.get(f'/api/v1/jobs/{job_id or self.job_id}/', **self.baslik)
        return yanit, sahte

    def test_kuyrukta_pending(self):
        yanit, _ = self._durum(SahteSonuc('PENDING'))
        self.assertEqual(yanit.status_code, 200)
        self.assertEqual(yanit.json(), {'job_id': self.job_id, 'section': 'cve', 'status': 'pending'})

    def test_calisiyor_started(self):
        yanit, _ = self._durum(SahteSonuc('STARTED'))
        self.assertEqual(yanit.json()['status'], 'started')

    def test_basarili_is_kayit_sayisini_verir(self):
        yanit, _ = self._durum(SahteSonuc('SUCCESS', {'success': True, 'count': 17}))
        govde = yanit.json()
        self.assertEqual(govde['status'], 'success')
        self.assertEqual(govde['count'], 17)
        self.assertNotIn('error', govde)

    def test_yeni_kayit_yoksa_yine_basarili(self):
        """Task'lar yeni kayit bulamayinca success=False ama hata alani olmadan doner."""
        yanit, _ = self._durum(SahteSonuc('SUCCESS', {'success': False, 'count': 0}))
        self.assertEqual(yanit.json()['status'], 'success')
        self.assertEqual(yanit.json()['count'], 0)

    def test_task_icinde_yakalanan_hata_failure_olur(self):
        """news/tasks.py istisnalari yakalayip {'success': False, 'error': ...} doner;
        Celery bunu SUCCESS sayar ama tuketici icin is basarisizdir."""
        hata = 'NOT NULL constraint failed: news_cveentry.updated_at'
        yanit, _ = self._durum(SahteSonuc('SUCCESS', {'success': False, 'error': hata}))
        govde = yanit.json()
        self.assertEqual(govde['status'], 'failure')
        self.assertEqual(govde['error'], hata)
        self.assertNotIn('count', govde)

    def test_celery_failure(self):
        yanit, _ = self._durum(SahteSonuc('FAILURE', RuntimeError('worker coktu')))
        self.assertEqual(yanit.json()['status'], 'failure')
        self.assertIn('worker coktu', yanit.json()['error'])

    def test_bilinmeyen_job_404(self):
        yanit, sahte = self._durum(SahteSonuc('PENDING'), job_id='hic-verilmemis-bir-kimlik')
        self.assertEqual(yanit.status_code, 404)
        self.assertEqual(yanit.json()['error']['code'], 'not_found')
        sahte.assert_not_called()

    def test_proje_celery_uygulamasiyla_sorgular(self):
        from cybernews.celery import app
        _, sahte = self._durum(SahteSonuc('PENDING'))
        sahte.assert_called_once_with(self.job_id, app=app)

    def test_tokensiz_401(self):
        self.assertEqual(self.client.get(f'/api/v1/jobs/{self.job_id}/').status_code, 401)
