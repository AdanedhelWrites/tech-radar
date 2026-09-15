"""Gemini istemcisi (spec 2026-09-15-gemini-yukseltme, bolum 3.2). Ag erisimi yok."""
import json
import uuid
from unittest import mock

import requests
from django.test import SimpleTestCase, TestCase, override_settings

from news import gemini
from news import translation_utils as tu
from news.tests.base import test_redis_client

ANAHTAR = 'test-anahtar'


def _yanit(durum=200, govde=None, metin=None, finish='STOP', ham=''):
    """Gemini generateContent yaniti. govde: modelin JSON ciktisi (dict); metin: ham part metni."""
    yanit = mock.Mock(status_code=durum, text=ham)
    if durum != 200:
        yanit.json.side_effect = ValueError('JSON degil')
        return yanit
    part = metin if metin is not None else json.dumps(govde, ensure_ascii=False)
    yanit.json.return_value = {'candidates': [{'finishReason': finish, 'content': {'parts': [{'text': part}]}}]}
    return yanit


class GeminiTestMixin:
    """Anahtar dolu, kapi/butce surec ici, bekleme yok. (override_settings mixin'e dekorator olarak
    uygulanamaz — yalniz SimpleTestCase alt siniflarina; bu yuzden setUp'ta enable edilir.)"""

    def setUp(self):
        super().setUp()
        ayar = override_settings(GEMINI_API_KEY=ANAHTAR)
        ayar.enable()
        self.addCleanup(ayar.disable)
        for hedef, deger in (('_gate', tu._LocalGate()), ('_butce', gemini._LocalButce()),
                             ('GEMINI_MIN_INTERVAL', 0.0)):
            yama = mock.patch.object(gemini, hedef, deger)
            yama.start()
            self.addCleanup(yama.stop)

    def _post(self, *yanitlar, side_effect=None):
        if side_effect is not None:
            yama = mock.patch('news.gemini.requests.post', side_effect=side_effect)
        elif len(yanitlar) == 1:
            yama = mock.patch('news.gemini.requests.post', return_value=yanitlar[0])
        else:
            yama = mock.patch('news.gemini.requests.post', side_effect=list(yanitlar))
        post = yama.start()
        self.addCleanup(yama.stop)
        return post


ALANLAR = {'title': 'Attackers exploit a new flaw in the parser',
           'description': 'Unauthenticated attackers can execute arbitrary code remotely by sending a crafted request.'}
CEVIRI = {'title': 'Saldırganlar ayrıştırıcıdaki yeni bir açığı istismar ediyor',
          'description': 'Kimliği doğrulanmamış saldırganlar özel hazırlanmış bir istek göndererek uzaktan rastgele kod çalıştırabilir.'}


class GeminiHazirlikTests(GeminiTestMixin, SimpleTestCase):

    def test_anahtar_yoksa_hazir_degil_ve_istek_atilmaz(self):
        post = self._post(_yanit(govde=CEVIRI))
        with override_settings(GEMINI_API_KEY=''):
            self.assertFalse(gemini.hazir())
            self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertEqual(post.call_count, 0)

    def test_anahtar_varsa_hazir(self):
        self.assertTrue(gemini.hazir())

    def test_devre_kesici_acikken_hazir_degil(self):
        gemini._gate.start_cooldown(60)
        self.assertFalse(gemini.hazir())


class GeminiIstekTests(GeminiTestMixin, SimpleTestCase):

    def test_istek_sekli(self):
        post = self._post(_yanit(govde=CEVIRI))
        gemini.kaydi_cevir(ALANLAR)
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent')
        self.assertEqual(kwargs['headers']['x-goog-api-key'], ANAHTAR)
        self.assertEqual(kwargs['timeout'], gemini.GEMINI_TIMEOUT)
        govde = kwargs['json']
        self.assertEqual(govde['generationConfig']['responseMimeType'], 'application/json')
        self.assertEqual(set(govde['generationConfig']['responseSchema']['properties']), {'title', 'description'})
        self.assertEqual(govde['generationConfig']['responseSchema']['required'], ['title', 'description'])
        self.assertEqual(json.loads(govde['contents'][0]['parts'][0]['text']), ALANLAR)
        self.assertIn('AYNEN', govde['systemInstruction']['parts'][0]['text'])

    def test_basarili_yanit_alanlari_dondurur(self):
        self._post(_yanit(govde=CEVIRI))
        self.assertEqual(gemini.kaydi_cevir(ALANLAR), CEVIRI)

    def test_bos_alanlar_gonderilmez(self):
        post = self._post(_yanit(govde={'title': CEVIRI['title']}))
        sonuc = gemini.kaydi_cevir({'title': ALANLAR['title'], 'description': '   '})
        self.assertEqual(sonuc, {'title': CEVIRI['title']})
        self.assertEqual(set(post.call_args.kwargs['json']['generationConfig']['responseSchema']['properties']), {'title'})

    def test_hepsi_bossa_istek_yok(self):
        post = self._post(_yanit(govde={}))
        self.assertIsNone(gemini.kaydi_cevir({'title': '', 'description': ' '}))
        self.assertEqual(post.call_count, 0)

    def test_hicbir_istisna_sizmaz(self):
        self._post(side_effect=RuntimeError('beklenmeyen'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertFalse(gemini._gate.cooldown_active())


class GeminiDogrulamaTests(GeminiTestMixin, SimpleTestCase):

    def test_bos_ceviri_reddedilir(self):
        self._post(_yanit(govde={'title': CEVIRI['title'], 'description': ''}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_eksik_alan_reddedilir(self):
        self._post(_yanit(govde={'title': CEVIRI['title']}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_kirpilmis_ceviri_reddedilir(self):
        self._post(_yanit(govde={'title': CEVIRI['title'], 'description': 'Kısa.'}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_asiri_uzun_ceviri_reddedilir(self):
        self._post(_yanit(govde={'title': CEVIRI['title'], 'description': 'x' * (len(ALANLAR['description']) * 4)}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_yanki_reddedilir(self):
        self._post(_yanit(govde={'title': ALANLAR['title'].upper(), 'description': CEVIRI['description']}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_kisa_metin_ayni_kalabilir(self):
        # 'Kubernetes 1.31 released' 3 kelime: mesru olarak ayni kalabilir
        self._post(_yanit(govde={'title': 'Kubernetes 1.31 released'}))
        self.assertEqual(gemini.kaydi_cevir({'title': 'Kubernetes 1.31 released'}), {'title': 'Kubernetes 1.31 released'})

    def test_hepsi_ya_da_hicbiri(self):
        # Bir alan gecemezse gecen alan da donmez
        self._post(_yanit(govde={'title': CEVIRI['title'], 'description': ''}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))


class GeminiHataTests(GeminiTestMixin, SimpleTestCase):

    def test_429_devre_kesiciyi_acar_butceyi_geri_almaz(self):
        self._post(_yanit(durum=429, ham='{"error": {"status": "RESOURCE_EXHAUSTED"}}'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertTrue(gemini._gate.cooldown_active())
        self.assertFalse(gemini.hazir())
        self.assertEqual(gemini.butce_kullanimi(), 1)

    def test_5xx_devre_kesiciyi_acar(self):
        self._post(_yanit(durum=503))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertTrue(gemini._gate.cooldown_active())

    def test_baglanti_hatasi_devre_kesiciyi_acar(self):
        self._post(side_effect=requests.ConnectionError('kopuk'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertTrue(gemini._gate.cooldown_active())

    def test_401_devre_kesici_acmaz_butce_geri_alinir(self):
        self._post(_yanit(durum=401, ham='{"error": {"status": "UNAUTHENTICATED"}}'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertFalse(gemini._gate.cooldown_active())
        self.assertEqual(gemini.butce_kullanimi(), 0)
        self.assertTrue(gemini.hazir())

    def test_safety_finish_reason_reddedilir(self):
        self._post(_yanit(govde=CEVIRI, finish='SAFETY'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertFalse(gemini._gate.cooldown_active())

    def test_bozuk_json_reddedilir(self):
        self._post(_yanit(metin='{"title": "yarim'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertFalse(gemini._gate.cooldown_active())

    def test_json_dict_degilse_reddedilir(self):
        self._post(_yanit(metin='["liste"]'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))


class GeminiButceTests(GeminiTestMixin, SimpleTestCase):

    def test_gunluk_butce_asilmaz(self):
        with mock.patch.object(gemini, 'GEMINI_DAILY_BUDGET', 2):
            post = self._post(_yanit(govde=CEVIRI))
            self.assertEqual(gemini.kaydi_cevir(ALANLAR), CEVIRI)
            self.assertEqual(gemini.kaydi_cevir(ALANLAR), CEVIRI)
            self.assertFalse(gemini.butce_var())
            self.assertFalse(gemini.hazir())
            self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertEqual(post.call_count, 2)
        self.assertEqual(gemini.butce_kullanimi(), 2)

    def test_butce_anahtari_utc_gun(self):
        self.assertRegex(gemini.butce_anahtari(), r'^budget:\d{4}-\d{2}-\d{2}$')


class RedisButceTests(TestCase):

    def setUp(self):
        self.redis = test_redis_client()
        self.prefix = f'test-gemini-{uuid.uuid4().hex}'
        self.butce = gemini._RedisButce(self.redis, prefix=self.prefix)
        self.addCleanup(self._temizle)

    def _temizle(self):
        for anahtar in self.redis.scan_iter(f'{self.prefix}:*'):
            self.redis.delete(anahtar)

    def test_artir_azalt_oku_ve_ttl(self):
        self.assertEqual(self.butce.oku('budget:2026-09-15'), 0)
        self.assertEqual(self.butce.artir('budget:2026-09-15'), 1)
        self.assertEqual(self.butce.artir('budget:2026-09-15'), 2)
        self.butce.azalt('budget:2026-09-15')
        self.assertEqual(self.butce.oku('budget:2026-09-15'), 1)
        ttl = self.redis.ttl(f'{self.prefix}:budget:2026-09-15')
        self.assertTrue(0 < ttl <= 48 * 3600)

    def test_django_ortaminda_redis_butce_ve_kapi(self):
        with mock.patch.object(gemini, '_butce', None), mock.patch.object(gemini, '_gate', None):
            self.assertIsInstance(gemini._get_butce(), gemini._RedisButce)
            self.assertIsInstance(gemini._get_gate(), tu._RedisGate)
