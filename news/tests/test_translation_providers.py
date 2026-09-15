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


class SaglayiciZinciriSirasiTests(SimpleTestCase):

    def test_zincirde_yalniz_libretranslate_var(self):
        self.assertEqual([s.name for s in tp.SAGLAYICILAR], ['libretranslate'])
