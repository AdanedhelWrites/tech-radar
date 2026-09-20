"""Manuel tetikleme testleri: gate, trigger, sinyal ve refresh uc noktalari.

Redis gercek kullanilir (benzersiz onekle). Celery task'lari hicbir zaman
gercekten kuyruga atilmaz: canli worker ayni broker'i dinliyor.
"""
import uuid
from unittest import mock

from django.test import SimpleTestCase
from rest_framework.throttling import ScopedRateThrottle

from news.api_v1 import refresh
from news.api_v1.refresh import RefreshGate
from news.tests.base import RefreshTestMixin, V1TestCase, test_redis_client


class RedisOnekliTestMixin:
    """Benzersiz onekli RefreshGate kurar ve test sonunda kendi anahtarlarini siler."""

    def setUp(self):
        super().setUp()
        self.redis = test_redis_client()
        self.gate = RefreshGate(self.redis, prefix=f'test-refresh-{uuid.uuid4().hex}')
        self.addCleanup(self._anahtarlari_sil)

    def _anahtarlari_sil(self):
        for anahtar in self.redis.scan_iter(f'{self.gate.prefix}:*'):
            self.redis.delete(anahtar)


class RefreshGateTests(RedisOnekliTestMixin, SimpleTestCase):

    def test_ilk_kilit_alinir_ikincisi_alinamaz(self):
        self.assertTrue(self.gate.acquire('cve', 'is-1', 60))
        self.assertFalse(self.gate.acquire('cve', 'is-2', 60))
        self.assertEqual(self.gate.running_job('cve'), 'is-1')

    def test_bolumler_birbirini_kilitlemez(self):
        self.assertTrue(self.gate.acquire('cve', 'is-1', 60))
        self.assertTrue(self.gate.acquire('ai', 'is-2', 60))

    def test_kilit_yoksa_calisan_is_none(self):
        self.assertIsNone(self.gate.running_job('cve'))

    def test_soguma_yoksa_kalan_sifir(self):
        self.assertEqual(self.gate.cooldown_remaining('cve'), 0)

    def test_soguma_kalan_sureyi_saniye_olarak_verir(self):
        self.gate.start_cooldown('cve', 900)
        kalan = self.gate.cooldown_remaining('cve')
        self.assertGreater(kalan, 890)
        self.assertLessEqual(kalan, 900)

    def test_sifir_soguma_anahtar_yazmaz(self):
        self.gate.start_cooldown('cve', 0)
        self.assertEqual(self.gate.cooldown_remaining('cve'), 0)

    def test_baska_isin_kilidi_birakilamaz(self):
        self.gate.acquire('cve', 'is-1', 60)
        self.assertFalse(self.gate.release('cve', 'baska-is'))
        self.assertEqual(self.gate.running_job('cve'), 'is-1')

    def test_kendi_kilidini_birakir(self):
        self.gate.acquire('cve', 'is-1', 60)
        self.assertTrue(self.gate.release('cve', 'is-1'))
        self.assertIsNone(self.gate.running_job('cve'))

    def test_job_kaydi_uzerinden_birakir(self):
        self.gate.acquire('cve', 'is-1', 60)
        self.gate.record_job('is-1', 'cve')
        self.assertEqual(self.gate.job_section('is-1'), 'cve')
        self.assertTrue(self.gate.release_job('is-1'))
        self.assertIsNone(self.gate.running_job('cve'))

    def test_kaydi_olmayan_job_hicbir_seyi_birakmaz(self):
        self.gate.acquire('cve', 'is-1', 60)
        self.assertFalse(self.gate.release_job('beat-isi'))
        self.assertEqual(self.gate.running_job('cve'), 'is-1')

    def test_rollback_her_seyi_siler(self):
        self.gate.acquire('cve', 'is-1', 60)
        self.gate.record_job('is-1', 'cve')
        self.gate.start_cooldown('cve', 900)
        self.gate.rollback('cve', 'is-1')
        self.assertIsNone(self.gate.running_job('cve'))
        self.assertEqual(self.gate.cooldown_remaining('cve'), 0)
        self.assertIsNone(self.gate.job_section('is-1'))


class TriggerTests(RefreshTestMixin, SimpleTestCase):
    """Kontrol sirasi: once kilit, sonra soguma, sonra kuyruga atma."""

    def test_ilk_tetikleme_baslar(self):
        sonuc = refresh.trigger('cve')
        self.assertEqual(sonuc.status, 'started')
        self.assertEqual(sonuc.section, 'cve')
        uuid.UUID(sonuc.job_id)  # gecerli bir uuid olmali
        self.gorevler['cve'].assert_called_once_with(
            kwargs={'skip_existing': True}, task_id=sonuc.job_id,
            headers={'fetchrun_trigger': 'api'})
        self.assertEqual(self.gate.running_job('cve'), sonuc.job_id)
        self.assertEqual(self.gate.job_section(sonuc.job_id), 'cve')
        self.assertGreater(self.gate.cooldown_remaining('cve'), 0)

    def test_varsayilan_soguma_15_dakika(self):
        refresh.trigger('cve')
        self.assertGreater(self.gate.cooldown_remaining('cve'), 890)
        self.assertLessEqual(self.gate.cooldown_remaining('cve'), refresh.REFRESH_COOLDOWN)

    def test_calisirken_ikinci_tetikleme_ayni_isi_doner(self):
        ilk = refresh.trigger('cve')
        ikinci = refresh.trigger('cve')
        self.assertEqual(ikinci.status, 'already_running')
        self.assertEqual(ikinci.job_id, ilk.job_id)
        self.gorevler['cve'].assert_called_once()

    def test_is_bittikten_sonra_soguma_devam_eder(self):
        ilk = refresh.trigger('cve')
        self.gate.release('cve', ilk.job_id)
        sonuc = refresh.trigger('cve')
        self.assertEqual(sonuc.status, 'cooldown')
        self.assertGreater(sonuc.retry_after, 0)
        self.assertIsNone(sonuc.job_id)
        self.gorevler['cve'].assert_called_once()

    def test_soguma_bitince_yeniden_baslar(self):
        ilk = refresh.trigger('cve', cooldown=0)
        self.gate.release('cve', ilk.job_id)
        ikinci = refresh.trigger('cve', cooldown=0)
        self.assertEqual(ikinci.status, 'started')
        self.assertNotEqual(ikinci.job_id, ilk.job_id)
        self.assertEqual(self.gorevler['cve'].call_count, 2)

    def test_bir_bolumun_sogumasi_digerini_etkilemez(self):
        refresh.trigger('cve')
        self.assertEqual(refresh.trigger('ai').status, 'started')

    def test_kuyruga_atma_basarisizsa_iz_birakmaz(self):
        self.gorevler['cve'].side_effect = ConnectionError('broker yok')
        with self.assertRaises(ConnectionError):
            refresh.trigger('cve')
        self.assertIsNone(self.gate.running_job('cve'))
        self.assertEqual(self.gate.cooldown_remaining('cve'), 0)

    def test_yarisi_kaybeden_kazananin_isini_doner(self):
        """Iki istek ayni anda kilidin bos oldugunu gorurse yalnizca biri kuyruga atar."""
        self.gate.acquire('cve', 'kazanan-is', 60)
        with mock.patch.object(self.gate, 'running_job', side_effect=[None, 'kazanan-is']):
            sonuc = refresh.trigger('cve')
        self.assertEqual(sonuc.status, 'already_running')
        self.assertEqual(sonuc.job_id, 'kazanan-is')
        self.gorevler['cve'].assert_not_called()

    def test_bilinmeyen_bolum_reddedilir(self):
        with self.assertRaises(ValueError):
            refresh.trigger('olmayan-bolum')

    def test_bolum_listesi_url_yollariyla_ayni(self):
        self.assertEqual(refresh.SECTIONS, ('news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai'))
        self.assertEqual(set(refresh.section_tasks()), set(refresh.SECTIONS))


from celery.signals import task_postrun


class KilitBirakmaSinyaliTests(RefreshTestMixin, SimpleTestCase):
    """Worker isi bitirince kilit birakilmali; soguma ise devam etmeli."""

    def _is_bitti(self, task_id):
        task_postrun.send(sender=None, task_id=task_id, task=None, args=(), kwargs={},
                          retval=None, state='SUCCESS')

    def test_is_bitince_kilit_birakilir(self):
        sonuc = refresh.trigger('cve')
        self._is_bitti(sonuc.job_id)
        self.assertIsNone(self.gate.running_job('cve'))

    def test_is_bitince_soguma_devam_eder(self):
        sonuc = refresh.trigger('cve')
        self._is_bitti(sonuc.job_id)
        self.assertGreater(self.gate.cooldown_remaining('cve'), 0)

    def test_beat_isi_manuel_kilide_dokunmaz(self):
        sonuc = refresh.trigger('cve')
        self._is_bitti('beat-tarafindan-baslatilmis-is')
        self.assertEqual(self.gate.running_job('cve'), sonuc.job_id)

    def test_news_uygulama_yapilandirmasi_yuklu(self):
        from django.apps import apps
        self.assertEqual(type(apps.get_app_config('news')).__name__, 'NewsConfig')


class RefreshUcNoktasiTests(RefreshTestMixin, V1TestCase):

    def setUp(self):
        super().setUp()
        self.baslik = self.token_basligi()

    def _tetikle(self, bolum='cve'):
        return self.client.post(f'/api/v1/{bolum}/refresh/', **self.baslik)

    def test_tokensiz_401(self):
        yanit = self.client.post('/api/v1/cve/refresh/')
        self.assertEqual(yanit.status_code, 401)
        self.assertEqual(yanit.json()['error']['code'], 'unauthorized')
        self.gorevler['cve'].assert_not_called()

    def test_baslatir_202(self):
        yanit = self._tetikle()
        self.assertEqual(yanit.status_code, 202)
        govde = yanit.json()
        self.assertEqual(govde['status'], 'started')
        self.assertEqual(govde['section'], 'cve')
        self.assertEqual(govde['status_url'], f"/api/v1/jobs/{govde['job_id']}/")
        self.gorevler['cve'].assert_called_once()

    def test_calisirken_ayni_isi_doner_202(self):
        ilk = self._tetikle().json()
        yanit = self._tetikle()
        self.assertEqual(yanit.status_code, 202)
        self.assertEqual(yanit.json()['status'], 'already_running')
        self.assertEqual(yanit.json()['job_id'], ilk['job_id'])
        self.assertEqual(yanit.json()['status_url'], ilk['status_url'])

    def test_sogumada_429_ve_retry_after(self):
        ilk = self._tetikle().json()
        self.gate.release('cve', ilk['job_id'])
        yanit = self._tetikle()
        self.assertEqual(yanit.status_code, 429)
        self.assertEqual(yanit.json()['error']['code'], 'cooldown')
        self.assertGreater(int(yanit['Retry-After']), 0)

    def test_bilinmeyen_bolum_404(self):
        yanit = self._tetikle('olmayan')
        self.assertEqual(yanit.status_code, 404)
        self.assertEqual(yanit.json()['error']['code'], 'not_found')

    def test_get_405(self):
        yanit = self.client.get('/api/v1/cve/refresh/', **self.baslik)
        self.assertEqual(yanit.status_code, 405)

    def test_alti_bolum_de_tetiklenebilir(self):
        for bolum in ('news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai'):
            with self.subTest(bolum=bolum):
                self.assertEqual(self._tetikle(bolum).status_code, 202)
                self.gorevler[bolum].assert_called_once()

    def test_token_basina_hiz_siniri_ayri_scope(self):
        """Refresh, okuma sinirindan bagimsiz ve cok daha siki sinirlanir."""
        oranlar = {'v1_read': '120/min', 'v1_refresh': '2/hour'}
        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', oranlar):
            self.assertEqual(self._tetikle('cve').status_code, 202)
            self.assertEqual(self._tetikle('sre').status_code, 202)
            ucuncu = self._tetikle('ai')
            okuma = self.client.get('/api/v1/ai/', **self.baslik)
        self.assertEqual(ucuncu.status_code, 429)
        self.assertEqual(ucuncu.json()['error']['code'], 'throttled')
        self.gorevler['ai'].assert_not_called()
        self.assertEqual(okuma.status_code, 200)


class TopluRefreshTests(RefreshTestMixin, V1TestCase):

    def setUp(self):
        super().setUp()
        self.baslik = self.token_basligi()

    def _toplu(self):
        return self.client.post('/api/v1/refresh/', **self.baslik)

    @staticmethod
    def _bolumler(liste):
        return [oge['section'] for oge in liste]

    def test_ilk_cagri_alti_bolumu_baslatir(self):
        yanit = self._toplu()
        self.assertEqual(yanit.status_code, 202)
        govde = yanit.json()
        self.assertEqual(self._bolumler(govde['started']),
                         ['news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai'])
        self.assertEqual(govde['already_running'], [])
        self.assertEqual(govde['skipped'], [])
        for sahte in self.gorevler.values():
            sahte.assert_called_once()

    def test_ikinci_cagri_calisan_isleri_doner(self):
        self._toplu()
        govde = self._toplu().json()
        self.assertEqual(govde['started'], [])
        self.assertEqual(len(govde['already_running']), 6)
        for sahte in self.gorevler.values():
            sahte.assert_called_once()

    def test_karisik_durum_dogru_ayrilir(self):
        refresh.trigger('ai')                        # calisiyor
        cve = refresh.trigger('cve')
        self.gate.release('cve', cve.job_id)         # bitti, sogumada
        self.gorevler['ai'].reset_mock()
        self.gorevler['cve'].reset_mock()

        govde = self._toplu().json()
        self.assertEqual(self._bolumler(govde['started']),
                         ['news', 'kubernetes', 'sre', 'devtools'])
        self.assertEqual(self._bolumler(govde['already_running']), ['ai'])
        self.assertEqual(self._bolumler(govde['skipped']), ['cve'])
        self.assertGreater(govde['skipped'][0]['retry_after'], 0)
        self.gorevler['ai'].assert_not_called()
        self.gorevler['cve'].assert_not_called()

    def test_hic_baslamasa_da_202(self):
        for bolum in refresh.SECTIONS:
            sonuc = refresh.trigger(bolum)
            self.gate.release(bolum, sonuc.job_id)
        yanit = self._toplu()
        self.assertEqual(yanit.status_code, 202)
        self.assertEqual(len(yanit.json()['skipped']), 6)

    def test_tokensiz_401(self):
        self.assertEqual(self.client.post('/api/v1/refresh/').status_code, 401)
