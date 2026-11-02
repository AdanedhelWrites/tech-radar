"""Gemini istemcisi (spec 2026-09-15-gemini-yukseltme, bolum 3.2). Ag erisimi yok."""
import json
import uuid
from datetime import datetime, timezone
from unittest import mock

import requests
from django.test import SimpleTestCase, TestCase, override_settings

from news import gemini
from news import translation_utils as tu
from news.tests.base import test_redis_client

ANAHTAR = 'test-anahtar'
# Google'in gecersiz anahtar yaniti (google.rpc.Status + ErrorInfo); 401 degil 400 doner
GECERSIZ_ANAHTAR_400 = json.dumps({'error': {
    'code': 400, 'message': 'API key not valid. Please pass a valid API key.', 'status': 'INVALID_ARGUMENT',
    'details': [{'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': 'API_KEY_INVALID',
                 'domain': 'googleapis.com'}]}})


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

    def test_gate_erisilemezse_hazir_false(self):
        with mock.patch.object(gemini, '_get_gate', side_effect=RuntimeError('redis erisilemedi')):
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

    def test_hicbir_istisna_sizmaz_beklenmeyen_hata_devre_kesiciyi_acar(self):
        """Beklenmeyen hata (kod hatasi) her kayitta tekrarlar: kaydin sucu degil, sistemik sayilir.
        Devre kesici acilmazsa retranslate her adayi icerik hatasi sayip kuyruktan dusururdu."""
        self._post(side_effect=RuntimeError('beklenmeyen'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertTrue(gemini._gate.cooldown_active())
        self.assertFalse(gemini.hazir())

    def test_aralik_kapisi_cagrilir(self):
        self._post(_yanit(govde=CEVIRI))
        with mock.patch.object(gemini._gate, 'wait_for_slot') as beklet:
            gemini.kaydi_cevir(ALANLAR)
        beklet.assert_called_once_with(gemini.GEMINI_MIN_INTERVAL)


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


class TurkceKarakterTests(GeminiTestMixin, SimpleTestCase):
    """2026-10-16: Gemini cevirilerinin yarisi (CVE'de %53) Turkce karaktersiz geliyordu
    ('kimligi dogrulanmamis saldirgan'). Sistem talimati diakritiksiz yazildigi icin model taklit ediyordu."""

    ASCII_GOVDE = ('Kimligi dogrulanmamis saldirganlar ozel hazirlanmis bir istek gondererek '
                   'uzaktan rastgele kod calistirabilir.')

    def test_uzun_turkce_harfsiz_ceviri_reddedilir(self):
        self._post(_yanit(govde={'title': CEVIRI['title'], 'description': self.ASCII_GOVDE}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_kisa_turkce_harfsiz_alan_kabul_edilir(self):
        # Kisa basliklar (urun adi + surum) mesru olarak Turkce harf icermeyebilir
        self._post(_yanit(govde={'title': 'Kubernetes 1.31 yayinda', 'description': CEVIRI['description']}))
        sonuc = gemini.kaydi_cevir({'title': 'Kubernetes 1.31 is out', 'description': ALANLAR['description']})
        self.assertEqual(sonuc['title'], 'Kubernetes 1.31 yayinda')

    def test_turkce_harfli_ceviri_kabul_edilir(self):
        self._post(_yanit(govde=CEVIRI))
        self.assertEqual(gemini.kaydi_cevir(ALANLAR), CEVIRI)

    def test_orijinalde_olmayan_yabanci_alfabe_reddedilir(self):
        # 2026-10-21 canli olcum: 'sunarken' yerine 'sերerken' (Ermeni harfleri) uydurulmustu
        bozuk = CEVIRI['description'].replace('istek', 'isտek')  # 'տ' Ermenice
        self._post(_yanit(govde={'title': CEVIRI['title'], 'description': bozuk}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_orijinalde_olan_yabanci_alfabe_kabul_edilir(self):
        alanlar = {'title': 'Attackers target the Привет botnet panel'}
        ceviri = {'title': 'Saldırganlar Привет botnet panelini hedef alıyor'}
        self._post(_yanit(govde=ceviri))
        self.assertEqual(gemini.kaydi_cevir(alanlar), ceviri)

    def test_talimat_turkce_karakterle_yazilmis_ve_acik_kural_var(self):
        talimat = gemini.SISTEM_TALIMATI
        for harf in 'çğıöşü':
            self.assertIn(harf, talimat, f'Talimat {harf!r} icermeli: model talimatin yazimini taklit ediyor')
        self.assertIn('Türkçe karakter', talimat)
        self.assertNotIn('dogrulanmamis', talimat, 'Ornek ceviriler ASCII olmamali')


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

    def test_401_403_404_devre_kesiciyi_acar_butce_geri_alinir(self):
        """Anahtar iptal / yetki / yanlis model sistemiktir: kayit sucu degil, devre kesici acilir
        (yoksa retranslate her adayi icerik hatasi sayip kuyruktan dusururdu). Kota harcanmadi."""
        for durum in (401, 403, 404):
            with self.subTest(durum=durum):
                gemini._gate = tu._LocalGate()
                self._post(_yanit(durum=durum, ham='{"error": {"status": "UNAUTHENTICATED"}}'))
                self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
                self.assertTrue(gemini._gate.cooldown_active())
                self.assertFalse(gemini.hazir())
                self.assertEqual(gemini.butce_kullanimi(), 0)

    def test_400_devre_kesici_acmaz_butce_geri_alinir(self):
        """Gecersiz govde kayda ozgu sayilir: devre kesici acilmaz, retranslate icerik hatasi sayar."""
        self._post(_yanit(durum=400, ham='{"error": {"status": "INVALID_ARGUMENT"}}'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertFalse(gemini._gate.cooldown_active())
        self.assertEqual(gemini.butce_kullanimi(), 0)
        self.assertTrue(gemini.hazir())

    def test_400_api_key_invalid_sistemiktir(self):
        """Generative Language API gecersiz/iptal/suresi dolmus anahtari 400 INVALID_ARGUMENT +
        details[].reason=API_KEY_INVALID ile doner. Kayit sucu sayilirsa butun yukseltme birikimi
        bir gunde deneme tavanina ulasirdi: devre kesici acilir, butce geri alinir."""
        self._post(_yanit(durum=400, ham=GECERSIZ_ANAHTAR_400))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertTrue(gemini._gate.cooldown_active())
        self.assertFalse(gemini.hazir())
        self.assertEqual(gemini.butce_kullanimi(), 0)

    def test_400_hesap_duzeyi_durumlar_sistemiktir(self):
        for durum in ('FAILED_PRECONDITION', 'PERMISSION_DENIED', 'UNAUTHENTICATED'):
            with self.subTest(durum=durum):
                gemini._gate = tu._LocalGate()
                self._post(_yanit(durum=400, ham=json.dumps(
                    {'error': {'code': 400, 'message': 'hesap sorunu', 'status': durum}})))
                self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
                self.assertTrue(gemini._gate.cooldown_active())
                self.assertEqual(gemini.butce_kullanimi(), 0)

    def test_400_baska_sebepli_invalid_argument_devre_kesici_acmaz(self):
        self._post(_yanit(durum=400, ham=json.dumps({'error': {
            'code': 400, 'status': 'INVALID_ARGUMENT',
            'details': [{'@type': 'type.googleapis.com/google.rpc.BadRequest', 'reason': 'FIELD_INVALID'}]}})))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertFalse(gemini._gate.cooldown_active())
        self.assertEqual(gemini.butce_kullanimi(), 0)

    def test_400_bozuk_govde_istisna_atmaz_devre_kesici_acmaz(self):
        """Hata govdesi JSON olmayabilir ya da beklenmedik sekilde olabilir: ayristirma asla firlatmaz."""
        for ham in ('<html>Bad Request</html>', '', '[1, 2]', '{"error": "metin"}',
                    '{"error": {"status": 5, "details": "liste degil"}}',
                    '{"error": {"details": [null, "x", {"reason": 7}]}}', None):
            with self.subTest(ham=ham):
                gemini._gate = tu._LocalGate()
                self._post(_yanit(durum=400, ham=ham))
                self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
                self.assertFalse(gemini._gate.cooldown_active())
                self.assertEqual(gemini.butce_kullanimi(), 0)

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

    def test_aday_string_ise_istisna_sizmadan_none_doner(self):
        yanit = mock.Mock(status_code=200, text='')
        yanit.json.return_value = {'candidates': ['metin']}
        self.assertIsNone(gemini._yaniti_coz(yanit))


class GeminiButceTests(GeminiTestMixin, SimpleTestCase):

    def test_gunluk_butce_asilmaz(self):
        with mock.patch.object(gemini, 'GEMINI_DAILY_BUDGET', 2):
            post = self._post(_yanit(govde=CEVIRI))
            self.assertEqual(gemini.kaydi_cevir(ALANLAR, 'cve'), CEVIRI)
            self.assertEqual(gemini.kaydi_cevir(ALANLAR, 'cve'), CEVIRI)
            self.assertFalse(gemini.butce_var())
            self.assertFalse(gemini.hazir())
            self.assertIsNone(gemini.kaydi_cevir(ALANLAR, 'cve'))
        self.assertEqual(post.call_count, 2)
        self.assertEqual(gemini.butce_kullanimi(), 2)

    def test_butce_anahtari_bicimi(self):
        self.assertRegex(gemini.butce_anahtari(), r'^budget:\d{4}-\d{2}-\d{2}$')

    def test_butce_anahtari_pasifik_gunune_gore(self):
        # UTC 15 Eylul 05:00 -> Pasifik'te 14 Eylul 22:00; anahtar Pasifik gunune gore olmali
        sabit = datetime(2026, 9, 15, 5, 0, tzinfo=timezone.utc)
        with mock.patch('news.gemini.datetime') as sahte_datetime:
            sahte_datetime.now.side_effect = lambda tz=None: sabit.astimezone(tz)
            self.assertEqual(gemini.butce_anahtari(), 'budget:2026-09-14')


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


class TekTavanTests(GeminiTestMixin, SimpleTestCase):
    """Spec 2026-11-02 G3: CVE rezervi kalkti; tum bolumler tek gunluk tavani paylasir."""

    def test_tek_tavan_tum_bolumler_icin(self):
        self.assertEqual(gemini.GEMINI_DAILY_BUDGET, 450)
        self.assertEqual(gemini.butce_tavani(), 450)
        self.assertFalse(hasattr(gemini, 'GEMINI_CVE_RESERVE'))
        self.assertFalse(hasattr(gemini, 'ONCELIKLI_BOLUM'))

    def test_bolum_adi_tavani_degistirmez(self):
        """Bolum yalniz log icindir: CVE disi bir bolum de tavana kadar istek atar."""
        post = self._post(_yanit(govde=CEVIRI))
        with mock.patch.object(gemini, 'GEMINI_DAILY_BUDGET', 3):
            for bolum in ('news', 'ai', 'cve'):
                self.assertEqual(gemini.kaydi_cevir(ALANLAR, bolum), CEVIRI)
            self.assertFalse(gemini.butce_var())
            self.assertFalse(gemini.hazir())
            self.assertIsNone(gemini.kaydi_cevir(ALANLAR, 'news'))
        self.assertEqual(post.call_count, 3)

    def test_tavana_dayaninca_kaydi_cevir_istek_atmaz_ve_sayaci_geri_alir(self):
        """hazir()/artir() arasindaki yaris: hazir() True dese de artir() tavani asarsa
        kaydi_cevir istek atmadan azalt() ile sayaci geri almali."""
        post = self._post(_yanit(govde={'title': 'Baslik'}))
        for _ in range(gemini.butce_tavani()):
            gemini._butce.artir(gemini.butce_anahtari())
        onceki = gemini.butce_kullanimi()

        with mock.patch.object(gemini, 'hazir', return_value=True):
            sonuc = gemini.kaydi_cevir({'title': 'A new flaw in the parser'}, 'news')

        self.assertIsNone(sonuc)
        post.assert_not_called()
        self.assertEqual(gemini.butce_kullanimi(), onceki,
                         'Sayac geri alinmaliydi (artir sonrasi azalt calismali)')


KAYITLAR = {
    'k0': ALANLAR,
    'k1': {'title': 'Researchers disclose a critical bug in the router firmware',
           'description': 'The vendor released a patch that fixes the memory corruption issue in the web interface.'},
    'k2': {'title': 'Kubernetes 1.31 released'},
}
PAKET_CEVIRI = {
    'k0': CEVIRI,
    'k1': {'title': 'Araştırmacılar yönlendirici yazılımında kritik bir hata açıkladı',
           'description': 'Üretici, web arayüzündeki bellek bozulması sorununu gideren bir yama yayımladı.'},
    'k2': {'title': 'Kubernetes 1.31 yayımlandı'},
}


class GeminiPaketTests(GeminiTestMixin, SimpleTestCase):
    """Spec 2026-11-02 G5: bir istekte birden cok kayit; dogrulama kayit basina."""

    def _cevap(self, **degisiklik):
        """PAKET_CEVIRI'nin kopyasi; deger None ise o kimlik yanittan cikar."""
        govde = {kimlik: dict(alanlar) for kimlik, alanlar in PAKET_CEVIRI.items()}
        for kimlik, deger in degisiklik.items():
            if deger is None:
                govde.pop(kimlik)
            else:
                govde[kimlik] = deger
        return _yanit(govde=govde)

    def test_sinir_degerleri(self):
        self.assertEqual(gemini.GEMINI_BATCH_CHARS, 10000)
        self.assertEqual(gemini.GEMINI_BATCH_MAX, 15)

    def test_paket_tek_istekte_gider(self):
        post = self._post(self._cevap())
        gemini.paket_cevir(KAYITLAR, 'news')
        self.assertEqual(post.call_count, 1)
        self.assertEqual(gemini.butce_kullanimi(), 1)
        govde = post.call_args.kwargs['json']
        self.assertEqual(json.loads(govde['contents'][0]['parts'][0]['text']), KAYITLAR)
        self.assertEqual(govde['generationConfig']['responseMimeType'], 'application/json')
        sema = govde['generationConfig']['responseSchema']
        self.assertEqual(sema['type'], 'OBJECT')
        self.assertEqual(sema['required'], ['k0', 'k1', 'k2'])
        self.assertEqual(sema['properties']['k0'], {
            'type': 'OBJECT',
            'properties': {'title': {'type': 'STRING'}, 'description': {'type': 'STRING'}},
            'required': ['title', 'description']})
        self.assertEqual(sema['properties']['k2']['required'], ['title'])

    def test_paket_basarili_kayitlari_dondurur(self):
        self._post(self._cevap())
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertEqual(sonuc.ceviriler, PAKET_CEVIRI)
        self.assertEqual(sonuc.reddedilen, set())
        self.assertFalse(sonuc.istek_hatasi)
        self.assertFalse(sonuc.kesildi)

    def test_bozuk_kayit_yalniz_kendini_dusurur(self):
        self._post(self._cevap(k1=dict(KAYITLAR['k1'])))  # yanki
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertEqual(sonuc.reddedilen, {'k1'})
        self.assertEqual(set(sonuc.ceviriler), {'k0', 'k2'})
        self.assertEqual(sonuc.ceviriler['k0'], CEVIRI)

    def test_eksik_kimlik_yalniz_o_kaydi_reddeder(self):
        self._post(self._cevap(k2=None))
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertEqual(sonuc.reddedilen, {'k2'})
        self.assertEqual(set(sonuc.ceviriler), {'k0', 'k1'})

    def test_alanlardan_biri_bozuksa_kayit_reddedilir(self):
        self._post(self._cevap(k0={'title': CEVIRI['title'], 'description': ''}))
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertEqual(sonuc.reddedilen, {'k0'})
        self.assertEqual(set(sonuc.ceviriler), {'k1', 'k2'})

    def test_eksik_alan_ya_da_nesne_olmayan_deger_reddedilir(self):
        self._post(self._cevap(k0={'title': CEVIRI['title']}, k1='metin'))
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertEqual(sonuc.reddedilen, {'k0', 'k1'})
        self.assertEqual(set(sonuc.ceviriler), {'k2'})

    def test_istenmeyen_alan_ve_kimlik_yok_sayilir(self):
        fazla = dict(PAKET_CEVIRI['k2'], description='Fazladan alan')
        govde = dict(PAKET_CEVIRI, k2=fazla, k9={'title': 'Uydurma kayıt'})
        self._post(_yanit(govde=govde))
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertEqual(sonuc.ceviriler, PAKET_CEVIRI)
        self.assertEqual(sonuc.reddedilen, set())

    def test_karisan_kimlik_alan_tutmazsa_yalniz_o_reddedilir(self):
        # Model k2'nin cevirisini k0'a koyarsa k0'in description'i eksik kalir: yalniz k0 reddedilir.
        # Alanlari ve uzunluklari tutan yer degisimini _alan_sorunu yakalamaz; onu capa capraz denetimi
        # yakalar (bkz. GeminiPaketCapaTests). Capasiz kayitlarda o da yakalanamaz.
        self._post(self._cevap(k0=PAKET_CEVIRI['k2']))
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertEqual(sonuc.reddedilen, {'k0'})
        self.assertEqual(set(sonuc.ceviriler), {'k1', 'k2'})

    def test_max_tokens_kesildi_isaretler(self):
        self._post(_yanit(metin='{"k0": {"title": "yar', finish='MAX_TOKENS'))
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertTrue(sonuc.kesildi)
        self.assertFalse(sonuc.istek_hatasi)
        self.assertFalse(sonuc.yanit_bozuk)
        self.assertEqual(sonuc.ceviriler, {})
        self.assertEqual(sonuc.reddedilen, set())
        self.assertFalse(gemini._gate.cooldown_active())
        self.assertEqual(gemini.butce_kullanimi(), 1)

    def test_safety_yanit_bozuk_hicbir_kaydi_reddetmez(self):
        """Sucun hangi kayitta oldugu bilinmez: kimse reddedilmez, cagiran boler (B2 fix 1)."""
        for sebep in ('SAFETY', 'RECITATION', 'OTHER'):
            with self.subTest(sebep=sebep):
                self._post(_yanit(govde=PAKET_CEVIRI, finish=sebep))
                sonuc = gemini.paket_cevir(KAYITLAR)
                self.assertTrue(sonuc.yanit_bozuk)
                self.assertEqual(sonuc.reddedilen, set())
                self.assertEqual(sonuc.ceviriler, {})
                self.assertFalse(sonuc.istek_hatasi)
                self.assertFalse(sonuc.kesildi)
                self.assertFalse(gemini._gate.cooldown_active())

    def test_bozuk_ya_da_nesne_olmayan_json_yanit_bozuk(self):
        for metin in ('{"k0": yarim', '["liste"]'):
            with self.subTest(metin=metin):
                self._post(_yanit(metin=metin))
                sonuc = gemini.paket_cevir(KAYITLAR)
                self.assertTrue(sonuc.yanit_bozuk)
                self.assertEqual(sonuc.reddedilen, set())
                self.assertEqual(sonuc.ceviriler, {})
                self.assertFalse(sonuc.istek_hatasi)
                self.assertFalse(sonuc.kesildi)
                self.assertFalse(gemini._gate.cooldown_active())

    def test_429_istek_hatasi(self):
        self._post(_yanit(durum=429, ham='{"error": {"status": "RESOURCE_EXHAUSTED"}}'))
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertTrue(sonuc.istek_hatasi)
        self.assertEqual(sonuc.reddedilen, set())
        self.assertEqual(sonuc.ceviriler, {})
        self.assertTrue(gemini._gate.cooldown_active())
        self.assertEqual(gemini.butce_kullanimi(), 1)

    def test_ag_hatasi_5xx_ve_beklenmeyen_hata_istek_hatasi(self):
        for etki in (requests.Timeout('zaman asimi'), RuntimeError('beklenmeyen'), None):
            with self.subTest(etki=etki):
                gemini._gate = tu._LocalGate()
                if etki is None:
                    self._post(_yanit(durum=503))
                else:
                    self._post(side_effect=etki)
                sonuc = gemini.paket_cevir(KAYITLAR)
                self.assertTrue(sonuc.istek_hatasi)
                self.assertEqual(sonuc.reddedilen, set())
                self.assertTrue(gemini._gate.cooldown_active())

    def test_sistemik_400_istek_hatasi_butce_geri_alinir(self):
        self._post(_yanit(durum=400, ham=GECERSIZ_ANAHTAR_400))
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertTrue(sonuc.istek_hatasi)
        self.assertEqual(sonuc.reddedilen, set())
        self.assertTrue(gemini._gate.cooldown_active())
        self.assertEqual(gemini.butce_kullanimi(), 0)

    def test_kayda_ozgu_400_istek_hatasi_devre_kesici_acmaz(self):
        self._post(_yanit(durum=400, ham='{"error": {"status": "INVALID_ARGUMENT"}}'))
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertTrue(sonuc.istek_hatasi)
        self.assertEqual(sonuc.reddedilen, set())
        self.assertFalse(gemini._gate.cooldown_active())
        self.assertEqual(gemini.butce_kullanimi(), 0)

    def test_hazir_degilse_istek_yok(self):
        post = self._post(self._cevap())
        gemini._gate.start_cooldown(60)
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertTrue(sonuc.istek_hatasi)
        self.assertEqual(sonuc.ceviriler, {})
        self.assertEqual(sonuc.reddedilen, set())
        post.assert_not_called()
        self.assertEqual(gemini.butce_kullanimi(), 0)

    def test_tavana_dayaninca_istek_atmaz_ve_sayaci_geri_alir(self):
        post = self._post(self._cevap())
        for _ in range(gemini.butce_tavani()):
            gemini._butce.artir(gemini.butce_anahtari())
        with mock.patch.object(gemini, 'hazir', return_value=True):
            sonuc = gemini.paket_cevir(KAYITLAR, 'news')
        self.assertTrue(sonuc.istek_hatasi)
        post.assert_not_called()
        self.assertEqual(gemini.butce_kullanimi(), gemini.butce_tavani())

    def test_aralik_kapisi_cagrilir(self):
        self._post(self._cevap())
        with mock.patch.object(gemini._gate, 'wait_for_slot') as beklet:
            gemini.paket_cevir(KAYITLAR)
        beklet.assert_called_once_with(gemini.GEMINI_MIN_INTERVAL)

    def test_bos_girdi_istek_atmaz(self):
        post = self._post(self._cevap())
        sonuc = gemini.paket_cevir({})
        self.assertEqual((sonuc.ceviriler, sonuc.reddedilen, sonuc.istek_hatasi, sonuc.kesildi),
                         ({}, set(), False, False))
        post.assert_not_called()

    def test_bos_alanlar_ve_bos_kayit_istege_girmez(self):
        post = self._post(_yanit(govde={'k0': {'title': CEVIRI['title']}}))
        sonuc = gemini.paket_cevir({'k0': {'title': ALANLAR['title'], 'description': ' '},
                                    'k1': {'title': '', 'description': None}})
        gonderilen = json.loads(post.call_args.kwargs['json']['contents'][0]['parts'][0]['text'])
        self.assertEqual(gonderilen, {'k0': {'title': ALANLAR['title']}})
        self.assertEqual(sonuc.ceviriler, {'k0': {'title': CEVIRI['title']}})
        self.assertEqual(sonuc.reddedilen, {'k1'})

    def test_hepsi_bos_kayitsa_istek_yok(self):
        post = self._post(self._cevap())
        sonuc = gemini.paket_cevir({'k0': {'title': ' '}})
        post.assert_not_called()
        self.assertFalse(sonuc.istek_hatasi)
        self.assertEqual(sonuc.reddedilen, {'k0'})
        self.assertEqual(gemini.butce_kullanimi(), 0)

    def test_talimat_paket_kuralini_icerir(self):
        kural = ("- Girdi, kimlik anahtarlı kayıtlardan oluşan bir JSON nesnesidir; her kaydı ayrı çevir, "
                 "aynı kimlik ve alan anahtarlarıyla döndür. Kayıtları birleştirme, sırasını ya da kimliğini "
                 "değiştirme.")
        post = self._post(self._cevap())
        gemini.paket_cevir(KAYITLAR)
        talimat = post.call_args.kwargs['json']['systemInstruction']['parts'][0]['text']
        self.assertIn(kural, talimat)
        self.assertIn('Türkçe karakter', talimat)
        self.assertTrue(talimat.endswith('- Yalnızca JSON döndür.'))
        # Tek kayit yolunun talimati degismez: onun girdisi kimlik anahtarli degil
        self.assertNotIn(kural, gemini.SISTEM_TALIMATI)


CVE_KAYITLARI = {
    'k0': {'description': 'A heap overflow in libfoo before 2.4.1 allows remote attackers to execute '
                          'arbitrary code (CVE-2026-1111).'},
    'k1': {'description': 'A heap overflow in libbar before 3.1.7 allows remote attackers to execute '
                          'arbitrary code (CVE-2026-2222).'},
}
CVE_CEVIRILERI = {
    'k0': {'description': "libfoo 2.4.1'den önceki sürümlerdeki bir yığın taşması, uzaktaki saldırganların "
                          'rastgele kod çalıştırmasına izin verir (CVE-2026-1111).'},
    'k1': {'description': "libbar 3.1.7'den önceki sürümlerdeki bir yığın taşması, uzaktaki saldırganların "
                          'rastgele kod çalıştırmasına izin verir (CVE-2026-2222).'},
}


class GeminiPaketCapaTests(GeminiTestMixin, SimpleTestCase):
    """Ayni bicimli (sablon CVE, benzer uzunluk) yer degisimini _alan_sorunu yakalamaz; capa capraz
    denetimi baska kaydin CVE/surum/URL/kod capasini tasiyan ceviriyi reddeder."""

    def test_yer_degistiren_cve_cevirileri_reddedilir(self):
        self._post(_yanit(govde={'k0': CVE_CEVIRILERI['k1'], 'k1': CVE_CEVIRILERI['k0']}))
        sonuc = gemini.paket_cevir(CVE_KAYITLARI, 'cve')
        self.assertEqual(sonuc.reddedilen, {'k0', 'k1'})
        self.assertEqual(sonuc.ceviriler, {})
        self.assertFalse(sonuc.istek_hatasi)

    def test_dogru_capali_paket_kabul_edilir(self):
        self._post(_yanit(govde=CVE_CEVIRILERI))
        sonuc = gemini.paket_cevir(CVE_KAYITLARI, 'cve')
        self.assertEqual(sonuc.ceviriler, CVE_CEVIRILERI)
        self.assertEqual(sonuc.reddedilen, set())

    def test_ondalik_virgulle_yazilsa_da_kabul_edilir(self):
        kayitlar = dict(CVE_KAYITLARI, k0={
            'description': 'The flaw in libfoo 2.4.1 has a CVSS score of 9.8 and is tracked as CVE-2026-1111.'})
        cevap = dict(CVE_CEVIRILERI, k0={
            'description': "libfoo 2.4.1'deki açığın CVSS puanı 9,8 olup CVE-2026-1111 olarak izleniyor."})
        self._post(_yanit(govde=cevap))
        sonuc = gemini.paket_cevir(kayitlar)
        self.assertEqual(sonuc.ceviriler, cevap)
        self.assertEqual(sonuc.reddedilen, set())

    def test_iki_capasini_da_kaybeden_kayit_reddedilir(self):
        cevap = dict(CVE_CEVIRILERI, k0={
            'description': 'Bir kütüphanedeki yığın taşması, uzaktaki saldırganların rastgele kod '
                           'çalıştırmasına izin verir.'})
        self._post(_yanit(govde=cevap))
        sonuc = gemini.paket_cevir(CVE_KAYITLARI)
        self.assertEqual(sonuc.reddedilen, {'k0'})
        self.assertEqual(set(sonuc.ceviriler), {'k1'})

    def test_capasiz_kayitlar_eskisi_gibi(self):
        self._post(_yanit(govde=PAKET_CEVIRI))
        sonuc = gemini.paket_cevir(KAYITLAR)
        self.assertEqual(sonuc.ceviriler, PAKET_CEVIRI)

    def test_capalar_desenleri(self):
        durumlar = (
            ('see cve-2026-12345 and GHSA-abcd-1234-efgh.', {'CVE-2026-12345', 'GHSA-ABCD-1234-EFGH'}),
            ('Details (see https://example.com/advisory/1).', {'HTTPS://EXAMPLE.COM/ADVISORY/1'}),
            ("Kaynak: 'https://example.com/a?b=1';", {'HTTPS://EXAMPLE.COM/A?B=1'}),
            ('call `parse_header()` now', {'`PARSE_HEADER()`'}),
            ('bkz. `https://x/a`', {'`HTTPS://X/A`', 'HTTPS://X/A'}),
            ("2.4.1'den önceki sürümler", {'2.4.1'}),
            ('v1.31 and v1.31.0.', {'V1.31', 'V1.31.0'}),
            ('Kubernetes v1.31.0 yayında', {'V1.31.0'}),
            ('CVSS 9.8, Kubernetes 1.31 ve 9,8', set()),
            ('Hiç çapa yok.', set()),
        )
        for metin, beklenen in durumlar:
            with self.subTest(metin=metin):
                self.assertEqual(gemini._capalar(metin), beklenen)

    def test_kendi_capasinin_parcasi_karisma_sayilmaz(self):
        # k1'in 1.2.3'u yalniz k0'in kendi 1.2.3.4'unun icinde geciyor: k0 reddedilmez
        self._post(_yanit(govde=self.ICERIK_CEVAP))
        sonuc = gemini.paket_cevir(self.ICERIK_KAYIT)
        self.assertEqual(sonuc.ceviriler, self.ICERIK_CEVAP)
        self.assertEqual(sonuc.reddedilen, set())

    # Tek capali kayitlar, capalardan biri digerinin onegi (lost-anchor kurali >=2 ister)
    ICERIK_KAYIT = {
        'k0': {'title': 'Router firmware 1.2.3.4 fixes the authentication bypass'},
        'k1': {'title': 'Router firmware 1.2.3 fixes the authentication bypass'},
    }
    ICERIK_CEVAP = {
        'k0': {'title': 'Yönlendirici yazılımı 1.2.3.4 kimlik doğrulama atlatmasını gideriyor'},
        'k1': {'title': 'Yönlendirici yazılımı 1.2.3 kimlik doğrulama atlatmasını gideriyor'},
    }

    def test_onek_capali_yer_degisimi_iki_yonde_reddedilir(self):
        for kisa, uzun in (('1.2.3', '1.2.3.4'), ('v1.31.1', 'v1.31.10'), ('CVE-2026-1234', 'CVE-2026-12345')):
            with self.subTest(kisa=kisa, uzun=uzun):
                gemini._gate = tu._LocalGate()
                kayitlar = {k: {'title': v['title'].replace('1.2.3.4', uzun).replace('1.2.3 ', kisa + ' ')}
                            for k, v in self.ICERIK_KAYIT.items()}
                cevap = {k: {'title': v['title'].replace('1.2.3.4', uzun).replace('1.2.3 ', kisa + ' ')}
                         for k, v in self.ICERIK_CEVAP.items()}
                self.assertIn(uzun, kayitlar['k0']['title'])
                self.assertIn(kisa + ' ', kayitlar['k1']['title'])
                self._post(_yanit(govde=cevap))
                dogru = gemini.paket_cevir(kayitlar)
                self.assertEqual(dogru.reddedilen, set(), 'yer degisimi yokken kabul edilmeli')
                self._post(_yanit(govde={'k0': cevap['k1'], 'k1': cevap['k0']}))
                sonuc = gemini.paket_cevir(kayitlar)
                self.assertEqual(sonuc.reddedilen, {'k0', 'k1'})
                self.assertEqual(sonuc.ceviriler, {})
