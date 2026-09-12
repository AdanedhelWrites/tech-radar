"""Manuel tetikleme testleri: gate, trigger, sinyal ve refresh uc noktalari.

Redis gercek kullanilir (benzersiz onekle). Celery task'lari hicbir zaman
gercekten kuyruga atilmaz: canli worker ayni broker'i dinliyor.
"""
import uuid

from django.test import SimpleTestCase

from news.api_v1.refresh import RefreshGate
from news.tests.base import test_redis_client


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
