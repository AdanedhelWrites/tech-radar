"""Yedek kayit cevirmenleri (spec 2026-11-02-ceviri-yayma G6): Gemini ikinci model, OpenRouter
ucretsiz model, DeepL API Free. Ag erisimi yok: HTTP mock'lanir, kapi/sayac surec icidir."""
import json
import re
import uuid
from datetime import date, datetime, timezone
from io import StringIO
from unittest import mock

import requests
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from news import gemini
from news import kayit_cevirmenleri as kc
from news import models
from news import translation_utils as tu
from news.tests.base import V1TestCase, test_redis_client
from news.tests.test_gemini import ALANLAR, CEVIRI, KAYITLAR, PAKET_CEVIRI, _yanit

ANAHTARLAR = {'GEMINI_API_KEY': 'test-gemini-anahtari', 'OPENROUTER_API_KEY': 'test-openrouter-anahtari',
              'DEEPL_API_KEY': 'test-deepl-anahtari:fx'}
UCRETSIZ_MODEL = 'meta-llama/llama-3.3-70b-instruct:free'


def _or_yanit(durum=200, govde=None, metin=None, finish='stop', ham=''):
    """OpenRouter chat/completions yaniti. govde: modelin JSON ciktisi (dict); metin: ham icerik."""
    yanit = mock.Mock(status_code=durum, text=ham)
    if durum != 200:
        yanit.json.side_effect = ValueError('JSON degil')
        return yanit
    icerik = metin if metin is not None else json.dumps(govde, ensure_ascii=False)
    yanit.json.return_value = {'choices': [{'finish_reason': finish,
                                            'message': {'role': 'assistant', 'content': icerik}}]}
    return yanit


def _deepl_yanit(metinler=(), durum=200, ham='', koru=True):
    """DeepL /v2/translate yaniti. koru: metinler yer tutuculu (korunmus) bicimde dondurulur; DeepL
    yalniz korunmus metni gorur ('Kubernetes 1.31' -> 'XTRM0002X XTRM0001X')."""
    if koru:
        metinler = [kc._terimleri_koru(metin)[0] for metin in metinler]
    yanit = mock.Mock(status_code=durum, text=ham)
    if durum != 200:
        yanit.json.side_effect = ValueError('JSON degil')
        return yanit
    yanit.json.return_value = {'translations': [{'detected_source_language': 'EN', 'text': metin}
                                                for metin in metinler]}
    return yanit


def _yerel(cevirmen):
    """Kapi ve sayac surec ici: canli Redis'e dokunulmaz."""
    cevirmen._gate = tu._LocalGate()
    cevirmen._butce = gemini._LocalButce()
    return cevirmen


class CevirmenTestMixin:
    """Anahtarlar dolu (sahte degerler), her testte taze cevirmen ornekleri, bekleme yok."""

    def setUp(self):
        super().setUp()
        ayar = override_settings(**ANAHTARLAR)
        ayar.enable()
        self.addCleanup(ayar.disable)
        self.gemini2 = _yerel(gemini.GeminiCevirmen('gemini-ikinci-model', onek='gemini2', tavan=450, aralik=0.0))
        self.openrouter = _yerel(kc.OpenRouterCevirmen(model=UCRETSIZ_MODEL, tavan=50, aralik=0.0))
        self.deepl = _yerel(kc.DeepLCevirmen(tavan=450000, aralik=0.0))
        # Birincil Gemini'nin modul durumu da surec ici (ayri sayac testleri onu okur)
        for hedef, deger in (('_gate', tu._LocalGate()), ('_butce', gemini._LocalButce()),
                             ('GEMINI_MIN_INTERVAL', 0.0)):
            yama = mock.patch.object(gemini, hedef, deger)
            yama.start()
            self.addCleanup(yama.stop)

    def _post(self, *yanitlar, side_effect=None):
        if side_effect is None and len(yanitlar) == 1:
            yama = mock.patch('news.kayit_cevirmenleri.requests.post', return_value=yanitlar[0])
        else:
            yama = mock.patch('news.kayit_cevirmenleri.requests.post',
                              side_effect=side_effect if side_effect is not None else list(yanitlar))
        post = yama.start()
        self.addCleanup(yama.stop)
        return post


class OrtakArayuzTests(CevirmenTestMixin, SimpleTestCase):

    def test_anahtar_yoksa_hazir_degil(self):
        post = self._post(_or_yanit(govde=CEVIRI))
        for cevirmen, ayar in ((self.gemini2, 'GEMINI_API_KEY'), (self.openrouter, 'OPENROUTER_API_KEY'),
                               (self.deepl, 'DEEPL_API_KEY')):
            with self.subTest(cevirmen=cevirmen.name), override_settings(**{ayar: ''}):
                self.assertFalse(cevirmen.hazir())
                self.assertIsNone(cevirmen.kaydi_cevir(ALANLAR))
                self.assertTrue(cevirmen.paket_cevir(KAYITLAR).istek_hatasi)
                self.assertFalse(cevirmen.butce_ozeti()['available'])
        self.assertEqual(post.call_count, 0)

    def test_anahtar_varsa_hazir(self):
        for cevirmen in (self.gemini2, self.openrouter, self.deepl):
            with self.subTest(cevirmen=cevirmen.name):
                self.assertTrue(cevirmen.hazir())

    def test_db_adlari(self):
        self.assertEqual((self.gemini2.name, self.openrouter.name, self.deepl.name),
                         ('gemini', 'openrouter', 'deepl'))
        self.assertEqual(gemini.BIRINCIL.name, 'gemini')

    def test_butce_ozeti_bicimi(self):
        for cevirmen, donem in ((self.gemini2, 'day'), (self.openrouter, 'day'), (self.deepl, 'month')):
            with self.subTest(cevirmen=cevirmen.name):
                ozet = cevirmen.butce_ozeti()
                self.assertEqual(set(ozet), {'used', 'limit', 'period', 'available', 'cooldown'})
                self.assertEqual(ozet['period'], donem)
                self.assertTrue(ozet['available'])
                self.assertFalse(ozet['cooldown'])

    def test_butce_ozeti_redis_dusunce_cokmez(self):
        class Bozuk:
            def oku(self, anahtar):
                raise ConnectionError('redis yok')

            def cooldown_active(self):
                raise ConnectionError('redis yok')

        for cevirmen in (self.gemini2, self.openrouter, self.deepl):
            with self.subTest(cevirmen=cevirmen.name):
                cevirmen._gate, cevirmen._butce = Bozuk(), Bozuk()
                ozet = cevirmen.butce_ozeti()
                self.assertEqual((ozet['used'], ozet['available'], ozet['cooldown']), (0, False, False))

    def test_devre_kesici_acikken_hazir_degil(self):
        for cevirmen in (self.gemini2, self.openrouter, self.deepl):
            with self.subTest(cevirmen=cevirmen.name):
                cevirmen._gate.start_cooldown(60)
                self.assertFalse(cevirmen.hazir())
                self.assertTrue(cevirmen.butce_ozeti()['cooldown'])


class ZincirTests(SimpleTestCase):

    def test_zincir_sirasi(self):
        ikinci = gemini.GeminiCevirmen('gemini-ikinci-model', onek='gemini2')
        zincir = kc._zinciri_kur(ikinci)
        self.assertIs(zincir[0], gemini.BIRINCIL)
        self.assertIs(zincir[1], ikinci)
        self.assertEqual([c.name for c in zincir], ['gemini', 'gemini', 'openrouter', 'deepl'])
        self.assertEqual((zincir[2], zincir[3]), (kc.OPENROUTER, kc.DEEPL))

    def test_ikinci_model_bossa_zincirde_yok(self):
        for model in ('', '  '):
            with self.subTest(model=model):
                zincir = kc._zinciri_kur(gemini.GeminiCevirmen(model, onek='gemini2'))
                self.assertEqual([c.name for c in zincir], ['gemini', 'openrouter', 'deepl'])

    def test_gemini2_ornegi_ayarlardan(self):
        self.assertEqual(kc.GEMINI2.onek, 'gemini2')
        self.assertEqual(kc.GEMINI2.tavan(), kc.GEMINI_FALLBACK_DAILY_BUDGET)
        self.assertEqual(kc.GEMINI2.model, kc.GEMINI_FALLBACK_MODEL)

    def test_varsayilanlar(self):
        self.assertEqual(kc.GEMINI_FALLBACK_MODEL, '')
        self.assertEqual(kc.GEMINI_FALLBACK_DAILY_BUDGET, 450)
        self.assertEqual(kc.OPENROUTER_MODEL, '')
        self.assertEqual(kc.OPENROUTER_DAILY_BUDGET, 50)
        self.assertEqual(kc.OPENROUTER_MIN_INTERVAL, 4.0)
        self.assertEqual(kc.DEEPL_MONTHLY_CHARS, 450000)
        self.assertEqual([c.name for c in kc.ZINCIR], ['gemini', 'openrouter', 'deepl'])
        self.assertIs(kc.ZINCIR[0], gemini.BIRINCIL)

    def test_testlerde_yedek_anahtarlar_bos_ve_durum_surec_ici(self):
        self.assertEqual(settings.OPENROUTER_API_KEY, '')
        self.assertEqual(settings.DEEPL_API_KEY, '')
        for cevirmen in kc.YEDEKLER:
            with self.subTest(cevirmen=cevirmen.onek):
                self.assertIsInstance(cevirmen._kapi(), tu._LocalGate)
                self.assertIsInstance(cevirmen._sayac(), gemini._LocalButce)


class Gemini2Tests(CevirmenTestMixin, SimpleTestCase):

    def test_gemini2_ayri_sayac_kullanir(self):
        yama = mock.patch('news.gemini.requests.post', return_value=_yanit(govde=CEVIRI))
        post = yama.start()
        self.addCleanup(yama.stop)

        self.assertEqual(self.gemini2.kaydi_cevir(ALANLAR, 'news'), CEVIRI)

        self.assertEqual(self.gemini2.butce_kullanimi(), 1)
        self.assertEqual(gemini.butce_kullanimi(), 0, 'Birincil modelin sayaci degismemeli')
        self.assertIn('/models/gemini-ikinci-model:generateContent', post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs['headers']['x-goog-api-key'], ANAHTARLAR['GEMINI_API_KEY'])
        # Devre kesici de ayri: ikinci modelin 429'u birincili durdurmaz
        post.return_value = _yanit(durum=429)
        self.assertIsNone(self.gemini2.kaydi_cevir(ALANLAR))
        self.assertFalse(self.gemini2.hazir())
        self.assertTrue(gemini.hazir())

    def test_gemini2_redis_anahtarlari_kendi_onekinde(self):
        istemci = mock.Mock()
        istemci.incrby.return_value = 1
        cevirmen = gemini.GeminiCevirmen('gemini-ikinci-model', onek='gemini2')
        with mock.patch.object(gemini, '_redis_client', return_value=istemci):
            self.assertEqual(cevirmen._kapi().cooldown_key, 'gemini2:cooldown')
            cevirmen._sayac().artir(gemini.butce_anahtari())
        istemci.incrby.assert_called_once_with(f'gemini2:{gemini.butce_anahtari()}', 1)

    def test_gemini2_kendi_tavani(self):
        cevirmen = _yerel(gemini.GeminiCevirmen('gemini-ikinci-model', onek='gemini2', tavan=1, aralik=0.0))
        yama = mock.patch('news.gemini.requests.post', return_value=_yanit(govde=CEVIRI))
        post = yama.start()
        self.addCleanup(yama.stop)
        self.assertEqual(cevirmen.kaydi_cevir(ALANLAR), CEVIRI)
        self.assertFalse(cevirmen.hazir())
        self.assertIsNone(cevirmen.kaydi_cevir(ALANLAR))
        self.assertEqual(post.call_count, 1)
        self.assertTrue(gemini.hazir())

    def test_birincil_modul_arayuzu_ayni_ornek(self):
        self.assertEqual(gemini.BIRINCIL.onek, 'gemini')
        self.assertEqual(gemini.BIRINCIL.model_adi(), gemini.GEMINI_MODEL)
        self.assertEqual(gemini.BIRINCIL.butce_ozeti(), gemini.butce_ozeti())


class OpenRouterTests(CevirmenTestMixin, SimpleTestCase):

    def _cevap(self, **degisiklik):
        govde = {kimlik: dict(alanlar) for kimlik, alanlar in PAKET_CEVIRI.items()}
        for kimlik, deger in degisiklik.items():
            if deger is None:
                govde.pop(kimlik)
            else:
                govde[kimlik] = deger
        return _or_yanit(govde=govde)

    def test_openrouter_ucretli_model_reddedilir(self):
        post = self._post(self._cevap())
        ucretli = _yerel(kc.OpenRouterCevirmen(model='openai/gpt-4o', tavan=50, aralik=0.0))
        with self.assertLogs('news.kayit_cevirmenleri', level='WARNING') as kayit:
            self.assertFalse(ucretli.hazir())
            self.assertFalse(ucretli.hazir())
            self.assertTrue(ucretli.paket_cevir(KAYITLAR).istek_hatasi)
            self.assertIsNone(ucretli.kaydi_cevir(ALANLAR))
        self.assertEqual(len([s for s in kayit.output if ':free' in s]), 1, 'Uyari surec basina bir kez')
        self.assertFalse(ucretli.butce_ozeti()['available'])
        post.assert_not_called()

    def test_openrouter_model_bossa_hazir_degil(self):
        post = self._post(self._cevap())
        bos = _yerel(kc.OpenRouterCevirmen(model='', tavan=50, aralik=0.0))
        self.assertFalse(bos.hazir())
        self.assertIsNone(bos.kaydi_cevir(ALANLAR))
        post.assert_not_called()

    def test_openrouter_paket_istek_sekli(self):
        post = self._post(self._cevap())
        self.openrouter.paket_cevir(KAYITLAR, 'news')
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://openrouter.ai/api/v1/chat/completions')
        self.assertEqual(kwargs['headers']['Authorization'], f"Bearer {ANAHTARLAR['OPENROUTER_API_KEY']}")
        govde = kwargs['json']
        self.assertEqual(govde['model'], UCRETSIZ_MODEL)
        self.assertEqual(govde['response_format'], {'type': 'json_object'})
        self.assertEqual(govde['messages'][0], {'role': 'system', 'content': gemini.PAKET_TALIMATI})
        self.assertEqual(govde['messages'][1]['role'], 'user')
        self.assertEqual(json.loads(govde['messages'][1]['content']), KAYITLAR)
        self.assertEqual(self.openrouter.butce_kullanimi(), 1, 'Butce istek basina bir artar')

    def test_openrouter_tek_kayit_istek_sekli(self):
        post = self._post(_or_yanit(govde=CEVIRI))
        self.assertEqual(self.openrouter.kaydi_cevir(ALANLAR, 'cve'), CEVIRI)
        govde = post.call_args.kwargs['json']
        self.assertEqual(govde['messages'][0]['content'], gemini.SISTEM_TALIMATI)
        self.assertEqual(json.loads(govde['messages'][1]['content']), ALANLAR)

    def test_openrouter_basarili_paket(self):
        self._post(self._cevap())
        sonuc = self.openrouter.paket_cevir(KAYITLAR)
        self.assertEqual(sonuc.ceviriler, PAKET_CEVIRI)
        self.assertEqual(sonuc.reddedilen, set())

    def test_openrouter_bozuk_kayit_yalniz_kendini_dusurur(self):
        # k1 yanki (cevrilmemis), k2 yanitta yok: yalniz onlar reddedilir, k0 yazilir
        self._post(self._cevap(k1=dict(KAYITLAR['k1']), k2=None))
        sonuc = self.openrouter.paket_cevir(KAYITLAR)
        self.assertEqual(sonuc.ceviriler, {'k0': PAKET_CEVIRI['k0']})
        self.assertEqual(sonuc.reddedilen, {'k1', 'k2'})
        self.assertFalse(sonuc.istek_hatasi or sonuc.kesildi or sonuc.yanit_bozuk)

    def test_openrouter_capa_karismasi_reddedilir(self):
        kayitlar = {'k0': {'description': 'A flaw tracked as CVE-2026-1111 lets attackers read files on the server.'},
                    'k1': {'description': 'A flaw tracked as CVE-2026-2222 lets attackers read files on the server.'}}
        self._post(_or_yanit(govde={
            'k0': {'description': 'CVE-2026-2222 olarak izlenen açık, saldırganların sunucudaki dosyaları okumasına izin verir.'},
            'k1': {'description': 'CVE-2026-2222 olarak izlenen açık, saldırganların sunucudaki dosyaları okumasına izin verir.'}}))
        sonuc = self.openrouter.paket_cevir(kayitlar)
        self.assertEqual(set(sonuc.ceviriler), {'k1'})
        self.assertEqual(sonuc.reddedilen, {'k0'})

    def test_openrouter_kesik_yanit(self):
        self._post(_or_yanit(metin='{"k0": {"title": "Sald', finish='length'))
        sonuc = self.openrouter.paket_cevir(KAYITLAR)
        self.assertTrue(sonuc.kesildi)
        self.assertEqual((sonuc.ceviriler, sonuc.reddedilen), ({}, set()))

    def test_openrouter_bozuk_yanit(self):
        for yanit in (_or_yanit(metin='JSON degil'), _or_yanit(govde=PAKET_CEVIRI, finish='content_filter'),
                      _or_yanit(metin='["dizi"]')):
            with self.subTest(yanit=yanit.json.return_value):
                self._post(yanit)
                self.assertTrue(self.openrouter.paket_cevir(KAYITLAR).yanit_bozuk)

    def test_openrouter_kod_citlu_json_cozulur(self):
        self._post(_or_yanit(metin='```json\n' + json.dumps(CEVIRI, ensure_ascii=False) + '\n```'))
        self.assertEqual(self.openrouter.kaydi_cevir(ALANLAR), CEVIRI)

    def test_openrouter_429_5xx_devre_kesici_butce_geri_alinmaz(self):
        for durum in (429, 502):
            with self.subTest(durum=durum):
                cevirmen = _yerel(kc.OpenRouterCevirmen(model=UCRETSIZ_MODEL, tavan=50, aralik=0.0))
                self._post(_or_yanit(durum=durum))
                self.assertTrue(cevirmen.paket_cevir(KAYITLAR).istek_hatasi)
                self.assertTrue(cevirmen._gate.cooldown_active())
                self.assertEqual(cevirmen.butce_kullanimi(), 1)

    def test_openrouter_sistemik_4xx_devre_kesici_butce_geri_alinir(self):
        for durum in (401, 402, 403):
            with self.subTest(durum=durum):
                cevirmen = _yerel(kc.OpenRouterCevirmen(model=UCRETSIZ_MODEL, tavan=50, aralik=0.0))
                self._post(_or_yanit(durum=durum, ham='{"error": {"message": "yok"}}'))
                self.assertIsNone(cevirmen.kaydi_cevir(ALANLAR))
                self.assertTrue(cevirmen._gate.cooldown_active())
                self.assertEqual(cevirmen.butce_kullanimi(), 0)

    def test_openrouter_400_devre_kesici_acmaz_butce_geri_alinir(self):
        self._post(_or_yanit(durum=400, ham='{"error": {"message": "bad request"}}'))
        self.assertTrue(self.openrouter.paket_cevir(KAYITLAR).istek_hatasi)
        self.assertFalse(self.openrouter._gate.cooldown_active())
        self.assertEqual(self.openrouter.butce_kullanimi(), 0)

    def test_openrouter_ag_hatasi_devre_kesici(self):
        self._post(side_effect=requests.ConnectionError('ag yok'))
        self.assertIsNone(self.openrouter.kaydi_cevir(ALANLAR))
        self.assertTrue(self.openrouter._gate.cooldown_active())

    def test_openrouter_gunluk_tavan(self):
        cevirmen = _yerel(kc.OpenRouterCevirmen(model=UCRETSIZ_MODEL, tavan=2, aralik=0.0))
        post = self._post(_or_yanit(govde=CEVIRI))
        self.assertEqual(cevirmen.kaydi_cevir(ALANLAR), CEVIRI)
        self.assertEqual(cevirmen.kaydi_cevir(ALANLAR), CEVIRI)
        self.assertFalse(cevirmen.hazir())
        self.assertIsNone(cevirmen.kaydi_cevir(ALANLAR))
        self.assertEqual(post.call_count, 2)

    def test_openrouter_aralik_kapisi_cagrilir(self):
        cevirmen = _yerel(kc.OpenRouterCevirmen(model=UCRETSIZ_MODEL, tavan=50, aralik=4.0))
        self._post(_or_yanit(govde=CEVIRI))
        with mock.patch.object(cevirmen._gate, 'wait_for_slot') as beklet:
            cevirmen.kaydi_cevir(ALANLAR)
        beklet.assert_called_once_with(4.0)

    def test_openrouter_gun_anahtari_utc(self):
        # UTC 15 Eylul 05:00 -> Pasifik'te 14 Eylul; OpenRouter gunluk siniri UTC gunune gore sifirlanir
        sabit = datetime(2026, 9, 15, 5, 0, tzinfo=timezone.utc)
        with mock.patch('news.kayit_cevirmenleri.datetime') as sahte_datetime:
            sahte_datetime.now.side_effect = lambda tz=None: sabit.astimezone(tz)
            self.assertEqual(self.openrouter._donem_anahtari(), 'budget:2026-09-15')
            self.assertEqual(self.deepl._donem_anahtari(), 'budget:2026-09')


class DeepLTests(CevirmenTestMixin, SimpleTestCase):

    @staticmethod
    def _sahte_deepl(cevir):
        """DeepL taklidi: her text'e cevir() uygular; ham CVE/urun adini bozar (korunmadiysa gorunur)."""
        def post(url, headers=None, json=None, timeout=None):
            metinler = [cevir(metin).replace('libxml2', 'libxml 2').replace('CVE-2026-1234', 'CVE 2026-1234')
                        for metin in json['text']]
            return _deepl_yanit(metinler, koru=False)
        return post

    def test_deepl_istek_sekli(self):
        post = self._post(_deepl_yanit([CEVIRI['title'], CEVIRI['description']]))
        self.assertEqual(self.deepl.kaydi_cevir(ALANLAR), CEVIRI)
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://api-free.deepl.com/v2/translate')
        self.assertEqual(kwargs['headers']['Authorization'], f"DeepL-Auth-Key {ANAHTARLAR['DEEPL_API_KEY']}")
        govde = kwargs['json']
        self.assertEqual((govde['source_lang'], govde['target_lang']), ('EN', 'TR'))
        self.assertEqual(govde['text'], [ALANLAR['title'], ALANLAR['description']])
        self.assertNotIn('tag_handling', govde)

    def test_deepl_paket_tek_istek_sirayla_eslenir(self):
        sirali = [metin for alanlar in PAKET_CEVIRI.values() for metin in alanlar.values()]
        post = self._post(_deepl_yanit(sirali))
        sonuc = self.deepl.paket_cevir(KAYITLAR, 'news')
        self.assertEqual(post.call_count, 1)
        self.assertEqual(len(post.call_args.kwargs['json']['text']), 5)
        self.assertEqual(sonuc.ceviriler, PAKET_CEVIRI)
        self.assertEqual(sonuc.reddedilen, set())

    def test_deepl_bozuk_kayit_yalniz_kendini_dusurur(self):
        sirali = [PAKET_CEVIRI['k0']['title'], PAKET_CEVIRI['k0']['description'],
                  KAYITLAR['k1']['title'], KAYITLAR['k1']['description'],   # yanki
                  PAKET_CEVIRI['k2']['title']]
        self._post(_deepl_yanit(sirali))
        sonuc = self.deepl.paket_cevir(KAYITLAR)
        self.assertEqual(set(sonuc.ceviriler), {'k0', 'k2'})
        self.assertEqual(sonuc.reddedilen, {'k1'})

    def test_deepl_ceviri_sayisi_tutmazsa_yanit_bozuk(self):
        self._post(_deepl_yanit([CEVIRI['title']]))
        self.assertTrue(self.deepl.paket_cevir(KAYITLAR).yanit_bozuk)

    def test_deepl_terimler_korunur(self):
        alanlar = {'title': 'CVE-2026-1234: heap overflow in libxml2 parser',
                   'description': 'A heap overflow in libxml2 allows remote attackers to crash applications.'}
        ceviriler = {
            'title': lambda m: m.replace('heap overflow in', 'yığın taşması:').replace('parser', 'ayrıştırıcısında'),
            'description': lambda m: m.replace('A heap overflow in', 'Yığın taşması,').replace(
                'allows remote attackers to crash applications.', 'uzaktaki saldırganların uygulamaları çökertmesine izin veriyor.'),
        }

        def cevir(metin):
            for donustur in ceviriler.values():
                metin = donustur(metin)
            return metin
        post = self._post(side_effect=self._sahte_deepl(cevir))

        sonuc = self.deepl.kaydi_cevir(alanlar, 'cve')

        gonderilen = ' '.join(post.call_args.kwargs['json']['text'])
        self.assertNotIn('CVE-2026-1234', gonderilen)
        self.assertNotIn('libxml2', gonderilen)
        self.assertRegex(gonderilen, r'XTRM\d{4}X')
        self.assertIsNotNone(sonuc)
        self.assertIn('CVE-2026-1234', sonuc['title'])
        self.assertIn('libxml2', sonuc['title'])
        self.assertIn('libxml2', sonuc['description'])
        self.assertNotRegex(' '.join(sonuc.values()), r'XTRM')

    def test_deepl_yer_tutucu_kaybolursa_kayit_reddedilir(self):
        alanlar = {'description': 'A heap overflow in libxml2 allows remote attackers to crash applications.'}
        self._post(side_effect=self._sahte_deepl(
            lambda m: re.sub(r'XTRM\d{4}X', '', m).replace(
                'A heap overflow in', 'Yığın taşması').replace(
                'allows remote attackers to crash applications.', 'uzaktaki saldırganların uygulamaları çökertmesine izin veriyor.')))
        self.assertIsNone(self.deepl.kaydi_cevir(alanlar))

    def test_deepl_aylik_karakter_tavani(self):
        cevirmen = _yerel(kc.DeepLCevirmen(tavan=150, aralik=0.0))
        post = self._post(_deepl_yanit([CEVIRI['title'], CEVIRI['description']]))
        self.assertEqual(cevirmen.kaydi_cevir(ALANLAR), CEVIRI)
        gonderilen = sum(len(metin) for metin in post.call_args.kwargs['json']['text'])
        self.assertEqual(cevirmen.butce_kullanimi(), gonderilen, 'Sayac istek basina degil karakter kadar artar')
        self.assertTrue(cevirmen.hazir(), 'Tavanin altinda: hazir')

        # Ikinci istek tavani asar: gonderilmez, sayac geri alinir
        self.assertIsNone(cevirmen.kaydi_cevir(ALANLAR))
        self.assertEqual(post.call_count, 1)
        self.assertEqual(cevirmen.butce_kullanimi(), gonderilen)
        ozet = cevirmen.butce_ozeti()
        self.assertEqual((ozet['limit'], ozet['period']), (150, 'month'))

    def test_deepl_ay_anahtari(self):
        self.assertRegex(self.deepl._donem_anahtari(), r'^budget:\d{4}-\d{2}$')
        istemci = mock.Mock()
        istemci.incrby.return_value = 10
        cevirmen = kc.DeepLCevirmen()
        with mock.patch.object(gemini, '_redis_client', return_value=istemci):
            cevirmen._sayac().artir(cevirmen._donem_anahtari(), 10)
        istemci.incrby.assert_called_once_with(f'deepl:{cevirmen._donem_anahtari()}', 10)

    def test_deepl_456_ve_429_devre_kesici(self):
        for durum in (456, 429, 503):
            with self.subTest(durum=durum):
                cevirmen = _yerel(kc.DeepLCevirmen(tavan=450000, aralik=0.0))
                self._post(_deepl_yanit(durum=durum))
                self.assertTrue(cevirmen.paket_cevir(KAYITLAR).istek_hatasi)
                self.assertTrue(cevirmen._gate.cooldown_active())
                self.assertGreater(cevirmen.butce_kullanimi(), 0, 'Kota harcanmis sayilir')

    def test_deepl_4xx_butce_geri_alinir(self):
        for durum, sistemik in ((400, False), (413, False), (403, True)):
            with self.subTest(durum=durum):
                cevirmen = _yerel(kc.DeepLCevirmen(tavan=450000, aralik=0.0))
                self._post(_deepl_yanit(durum=durum, ham='{"message": "hata"}'))
                self.assertIsNone(cevirmen.kaydi_cevir(ALANLAR))
                self.assertEqual(cevirmen.butce_kullanimi(), 0)
                self.assertEqual(cevirmen._gate.cooldown_active(), sistemik)


class RedisSayacTtlTests(TestCase):

    def setUp(self):
        self.redis = test_redis_client()
        self.prefix = f'test-deepl-{uuid.uuid4().hex}'
        self.addCleanup(self._temizle)

    def _temizle(self):
        for anahtar in self.redis.scan_iter(f'{self.prefix}:*'):
            self.redis.delete(anahtar)

    def test_aylik_sayac_ay_boyunca_yasar_ve_miktar_kadar_artar(self):
        butce = gemini._RedisButce(self.redis, prefix=self.prefix, ttl=kc.AYLIK_SAYAC_TTL)
        self.assertEqual(butce.artir('budget:2026-11', 120), 120)
        butce.azalt('budget:2026-11', 20)
        self.assertEqual(butce.oku('budget:2026-11'), 100)
        self.assertGreater(self.redis.ttl(f'{self.prefix}:budget:2026-11'), 31 * 24 * 3600)


class SaglikAnahtarTests(CevirmenTestMixin, V1TestCase):

    def test_saglik_anahtar_degeri_yanitta_yok(self):
        gizli = {'GEMINI_API_KEY': 'gizli-gemini-degeri', 'OPENROUTER_API_KEY': 'gizli-openrouter-degeri',
                 'DEEPL_API_KEY': 'gizli-deepl-degeri:fx'}
        with override_settings(**gizli):
            ozetler = [c.butce_ozeti() for c in (gemini.BIRINCIL, self.gemini2, self.openrouter, self.deepl)]
            ham = self.client.get('/api/saglik/').content.decode()
        metin = json.dumps(ozetler) + ham
        for deger in gizli.values():
            self.assertNotIn(deger, metin)
        self.assertTrue(all(ozet['available'] for ozet in ozetler))


class MigrationTests(TestCase):

    def test_migration_yeni_degerleri_kabul_eder(self):
        kayit = models.CVEEntry(cve_id='CVE-2026-0001', source='nvd', original_title='Baslik',
                                original_description='Aciklama', published_date=date(2026, 11, 2),
                                link='https://example.com/cve', translation_provider='deepl')
        kayit.full_clean()
        kayit.translation_provider = 'openrouter'
        kayit.full_clean()

    def test_alti_modelde_yeni_secenekler(self):
        modeller = [m for m in apps.get_app_config('news').get_models()
                    if any(f.name == 'translation_provider' for f in m._meta.fields)]
        self.assertEqual(len(modeller), 6)
        for model in modeller:
            with self.subTest(model=model.__name__):
                secenekler = dict(model._meta.get_field('translation_provider').choices)
                self.assertEqual(secenekler.get('openrouter'), 'OpenRouter')
                self.assertEqual(secenekler.get('deepl'), 'DeepL')

    def test_migration_modellerle_uyumlu(self):
        call_command('makemigrations', 'news', '--check', '--dry-run', stdout=StringIO())
