"""Manuel tetikleme testleri: gate, trigger, sinyal ve refresh uc noktalari.

Redis gercek kullanilir (benzersiz onekle). Celery task'lari hicbir zaman
gercekten kuyruga atilmaz: canli worker ayni broker'i dinliyor.
"""
import uuid
from unittest import mock

from django.test import SimpleTestCase

from news.api_v1 import refresh
from news.api_v1.refresh import RefreshGate
from news.tests.base import RefreshTestMixin, test_redis_client


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
            kwargs={'skip_existing': True}, task_id=sonuc.job_id)
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
