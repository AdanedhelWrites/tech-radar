"""Ceviri saglayicisi testleri (spec 4.1). Ag erisimi yok; HTTP mock'lanir."""
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from news import translation_providers as tp
from news import translation_utils as tu

LT_ADRES = 'http://lt-test:5000'


class ParcalamaTests(SimpleTestCase):

    def test_satirlar_ve_bos_satir_korunur(self):
        self.assertEqual(tp.parcala('First line.\n\nSecond line here.', 160),
                         [['First line.'], [], ['Second line here.']])

    def test_cumle_sonlarindan_bolunur(self):
        self.assertEqual(tp.parcala('One sentence. Two sentence! Three?', 160),
                         [['One sentence.', 'Two sentence!', 'Three?']])

    def test_uzun_cumle_virgulden_bolunur_ve_virgul_kaybolmaz(self):
        metin = 'a' * 50 + ', ' + 'b' * 40
        self.assertEqual(tp.parcala(metin, 80), [['a' * 50 + ',', 'b' * 40]])

    def test_uzun_cumle_bosluktan_bolunur(self):
        metin = ('word ' * 30).strip()
        parcalar = tp.parcala(metin, 40)[0]
        self.assertTrue(all(len(p) <= 40 for p in parcalar))
        self.assertEqual(' '.join(parcalar), metin)

    def test_sert_kesim_yer_tutucuyu_bolmez(self):
        metin = 'x' * 35 + 'XTRM0001X' + 'y' * 20
        parcalar = tp.parcala(metin, 40)[0]
        self.assertTrue(any('XTRM0001X' in p for p in parcalar))
        self.assertEqual(''.join(parcalar), metin)

    def test_bosluksuz_metin_sinirdan_kesilir(self):
        self.assertEqual([len(p) for p in tp.parcala('z' * 100, 40)[0]], [40, 40, 20])

    def test_birlestir_satir_yapisini_korur(self):
        self.assertEqual(tp.birlestir([['a', 'b'], [], ['c']], ['A', 'B', 'C']), 'A B\n\nC')


class LibreTranslateTestMixin:

    def setUp(self):
        super().setUp()
        yama = mock.patch.object(tp, '_lt_gate', tu._LocalGate())
        yama.start()
        self.addCleanup(yama.stop)

    def _yanit(self, durum=200, govde=None):
        yanit = mock.Mock(status_code=durum)
        yanit.json.return_value = govde
        return yanit


class LibreTranslateHazirlikTests(LibreTranslateTestMixin, SimpleTestCase):

    def test_adres_yoksa_hazir_degil(self):
        with override_settings(LIBRETRANSLATE_URL=''):
            self.assertFalse(tp.LibreTranslateProvider().available())

    @override_settings(LIBRETRANSLATE_URL=LT_ADRES)
    def test_adres_varsa_hazir(self):
        self.assertTrue(tp.LibreTranslateProvider().available())

    @override_settings(LIBRETRANSLATE_URL=LT_ADRES)
    def test_devre_kesici_acikken_hazir_degil(self):
        tp._get_lt_gate().start_cooldown(60)
        self.assertFalse(tp.LibreTranslateProvider().available())


@override_settings(LIBRETRANSLATE_URL=LT_ADRES)
class LibreTranslateCeviriTests(LibreTranslateTestMixin, SimpleTestCase):

    def test_parcalar_tek_istekte_gider_ve_satirlar_korunur(self):
        metin = 'First sentence. Second sentence.\nThird line.'
        with mock.patch('news.translation_providers.requests.post', return_value=self._yanit(
                govde={'translatedText': ['Birinci cümle.', 'İkinci cümle.', 'Üçüncü satır.']})) as post:
            sonuc = tp.LibreTranslateProvider().translate(metin)

        self.assertEqual(sonuc, 'Birinci cümle. İkinci cümle.\nÜçüncü satır.')
        post.assert_called_once()
        adres = post.call_args.args[0]
        self.assertEqual(adres, f'{LT_ADRES}/translate')
        self.assertEqual(post.call_args.kwargs['json'], {
            'q': ['First sentence.', 'Second sentence.', 'Third line.'],
            'source': 'en', 'target': 'tr', 'format': 'text'})
        self.assertEqual(post.call_args.kwargs['timeout'], tp.LIBRETRANSLATE_TIMEOUT)

    def test_baglanti_hatasi_none_ve_devre_kesici(self):
        with mock.patch('news.translation_providers.requests.post',
                        side_effect=requests.ConnectionError('baglanti yok')):
            self.assertIsNone(tp.LibreTranslateProvider().translate('Some text here.'))
        self.assertTrue(tp._get_lt_gate().cooldown_active())

    def test_zaman_asimi_none_ve_devre_kesici(self):
        with mock.patch('news.translation_providers.requests.post',
                        side_effect=requests.Timeout('yavas')):
            self.assertIsNone(tp.LibreTranslateProvider().translate('Some text here.'))
        self.assertTrue(tp._get_lt_gate().cooldown_active())

    def test_5xx_none_ve_devre_kesici(self):
        with mock.patch('news.translation_providers.requests.post', return_value=self._yanit(503)):
            self.assertIsNone(tp.LibreTranslateProvider().translate('Some text here.'))
        self.assertTrue(tp._get_lt_gate().cooldown_active())

    def test_4xx_none_ama_devre_kesici_acilmaz(self):
        with mock.patch('news.translation_providers.requests.post', return_value=self._yanit(400)):
            self.assertIsNone(tp.LibreTranslateProvider().translate('Some text here.'))
        self.assertFalse(tp._get_lt_gate().cooldown_active())

    def test_liste_uzunlugu_uyusmazsa_none(self):
        with mock.patch('news.translation_providers.requests.post', return_value=self._yanit(
                govde={'translatedText': ['Tek parça.']})):
            self.assertIsNone(tp.LibreTranslateProvider().translate('One. Two.'))
        self.assertFalse(tp._get_lt_gate().cooldown_active())

    def test_bozuk_json_none(self):
        yanit = self._yanit()
        yanit.json.side_effect = ValueError('json degil')
        with mock.patch('news.translation_providers.requests.post', return_value=yanit):
            self.assertIsNone(tp.LibreTranslateProvider().translate('Some text here.'))


@override_settings(LIBRETRANSLATE_URL=LT_ADRES)
class ParcaOnarimiTests(LibreTranslateTestMixin, SimpleTestCase):
    """2026-10-21 bulgu 9: yer tutucu basina kayip %4.4 ama 4500 karakterlik parca ~20 yer tutucu
    tasidigi icin parcalarin %37'si, cok parcali makalelerin neredeyse hepsi reddediliyordu. Baslik
    bicimli (Title Case) basliklar ozel ad sanilip aynen donuyordu (yanki). Onarim parca duzeyinde."""

    def _sirali(self, *govdeler):
        return mock.patch('news.translation_providers.requests.post',
                          side_effect=[self._yanit(govde={'translatedText': g}) for g in govdeler])

    def test_yer_tutucu_kaybeden_parca_yer_tutucu_arasi_metinlerle_yeniden_cevrilir(self):
        metin = 'Scores of XTRM0001X and XTRM0002X were reported. Second sentence.'
        with self._sirali(['XTRM0001X puanları bildirildi.', 'İkinci cümle.'],
                          ['Puanları', 've', 'bildirildi.']) as post:
            sonuc = tp.LibreTranslateProvider().translate(metin)

        self.assertEqual(sonuc, 'Puanları XTRM0001X ve XTRM0002X bildirildi. İkinci cümle.')
        self.assertEqual(post.call_count, 2)
        self.assertEqual(post.call_args.kwargs['json']['q'], ['Scores of', 'and', 'were reported.'])

    def test_yinelenen_yer_tutucu_da_bozuk_sayilir(self):
        metin = 'See XTRM0001X then XTRM0002X now.'
        with self._sirali(['Bakın XTRM0001X sonra XTRM0001X şimdi.'], ['Bakın', 'sonra', 'şimdi.']):
            sonuc = tp.LibreTranslateProvider().translate(metin)
        self.assertEqual(sonuc, 'Bakın XTRM0001X sonra XTRM0002X şimdi.')

    def test_harfsiz_parcalar_gonderilmez(self):
        # Tablo/sayi dizisi: yer tutucular arasi yalniz isaret ve sayi; ikinci istege gerek yok
        metin = 'XTRM0001X% / XTRM0002X% 45 XTRM0003X%'
        with self._sirali(['XTRM0001X% / XTRM00% 45']) as post:
            sonuc = tp.LibreTranslateProvider().translate(metin)
        self.assertEqual(sonuc, metin)
        self.assertEqual(post.call_count, 1)

    def test_saglam_ceviride_ikinci_istek_yok(self):
        with self._sirali(['XTRM0001X sürümü yayımlandı.']) as post:
            tp.LibreTranslateProvider().translate('XTRM0001X version released.')
        self.assertEqual(post.call_count, 1)

    def test_onarim_istegi_basarisizsa_ilk_ceviri_doner(self):
        metin = 'Scores of XTRM0001X and XTRM0002X were reported.'
        with mock.patch('news.translation_providers.requests.post', side_effect=[
                self._yanit(govde={'translatedText': ['XTRM0001X puanları bildirildi.']}),
                self._yanit(400)]):
            sonuc = tp.LibreTranslateProvider().translate(metin)
        self.assertEqual(sonuc, 'XTRM0001X puanları bildirildi.')  # dogrulama yine reddeder

    def test_baslik_bicimli_yanki_cumle_bicimiyle_yeniden_denenir(self):
        baslik = 'Browsers Block eMudhra Intermediate CAs Over Microsoft Keys'
        with self._sirali([baslik], ['Tarayıcılar microsoft anahtarları nedeniyle eMudhra ara CA\'larını engelliyor']) as post:
            sonuc = tp.LibreTranslateProvider().translate(baslik)

        self.assertEqual(post.call_args.kwargs['json']['q'],
                         ['Browsers block eMudhra intermediate CAs over microsoft keys'])
        self.assertEqual(sonuc, 'Tarayıcılar Microsoft anahtarları nedeniyle eMudhra ara CA\'larını engelliyor')

    def test_cumle_bicimi_yer_tutucuyu_kelime_saymaz(self):
        self.assertEqual(tp._cumle_bicimi('XTRM0001X Utility Powers Modern ClickFix Attack'),
                         ('XTRM0001X Utility powers modern ClickFix attack',
                          {'powers': 'Powers', 'modern': 'Modern', 'attack': 'Attack'}))

    def test_kisa_ya_da_cumle_bicimli_yanki_yeniden_denenmez(self):
        for metin in ('Spotlight on XTRM0001X', 'kubectl get pods output is unchanged here'):
            with self.subTest(metin=metin), self._sirali([metin]) as post:
                tp.LibreTranslateProvider().translate(metin)
            self.assertEqual(post.call_count, 1)

    def test_translate_text_onarilan_parcayla_dogrulamadan_gecer(self):
        metin = 'The flaw has a CVSS score of 9.8 and affects PHP 8.3.1 servers.'
        korunmus, _ = tu._protect_terms(metin)
        self.assertEqual(korunmus.count('XTRM'), 3)

        def cevap(adres, json, timeout):
            q = json['q']
            if len(q) == 1 and 'XTRM' in q[0]:  # ilk istek: bir yer tutucuyu dusur
                return self._yanit(govde={'translatedText': ['Kusurun XTRM0003X puanı var ve sunucuları etkiliyor.']})
            return self._yanit(govde={'translatedText': [f'<{p}>' for p in q]})

        tu.consume_translation_failures()
        with mock.patch('news.translation_providers.requests.post', side_effect=cevap):
            sonuc = tu.translate_text(metin)

        self.assertEqual(tu.consume_translation_failures(), 0, 'Onarilan parca dogrulamadan gecmeli')
        self.assertNotEqual(sonuc, metin)
        self.assertIn('<', sonuc)
        self.assertNotIn('XTRM', sonuc)
        self.assertIn('CVSS', sonuc)
        self.assertIn('9.8', sonuc)
        self.assertIn('8.3.1', sonuc)


class SaglayiciZinciriSirasiTests(SimpleTestCase):

    def test_zincirde_yalniz_libretranslate_var(self):
        self.assertEqual([s.name for s in tp.SAGLAYICILAR], ['libretranslate'])
