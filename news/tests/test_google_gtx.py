"""Google'in `translate_a/single?client=gtx` JSON ucu, tarayici TLS'iyle.

2026-09-14 bulgusu: Google bu IP'den gelen Python/OpenSSL TLS parmak izini
"automated queries" sayip 429 donuyor (once `/m` sayfasinda, sonra JSON ucta);
ayni konteynerden Chrome TLS taklidi (curl_cffi impersonate) 200 donuyor.
Basliklar, GET/POST, IPv4/IPv6 fark etmiyor. Bu yuzden Google'a curl_cffi ile
gidilir; deep-translator kaldirildi.
"""
from unittest import mock

from django.test import SimpleTestCase

from news import translation_utils as tu


def _gtx_yanit(durum=200, segmentler=None, ham_metin=''):
    """Google'in gtx yaniti: [[["ceviri", "orijinal", null, null, 3], ...], null, "en", ...]"""
    yanit = mock.Mock(status_code=durum, text=ham_metin)
    if segmentler is None:
        yanit.json.side_effect = ValueError('JSON degil')
    else:
        yanit.json.return_value = [[[c, o, None, None, 3] for c, o in segmentler], None, 'en']
    return yanit


class GtxTranslatorTests(SimpleTestCase):

    def test_make_translator_gtx_dondurur(self):
        self.assertIsInstance(tu._make_translator(), tu.GtxTranslator)

    def test_segmentler_birlestirilir(self):
        yanit = _gtx_yanit(segmentler=[('Ilk cumle. ', 'First sentence. '), ('Ikinci cumle.', 'Second sentence.')])
        with mock.patch('news.translation_utils.requests.post', return_value=yanit):
            self.assertEqual(tu.GtxTranslator().translate('First sentence. Second sentence.'),
                             'Ilk cumle. Ikinci cumle.')

    def test_istek_gtx_ucuna_post_ile_gider(self):
        yanit = _gtx_yanit(segmentler=[('Merhaba', 'Hello')])
        with mock.patch('news.translation_utils.requests.post', return_value=yanit) as post:
            tu.GtxTranslator().translate('Hello')
        self.assertEqual(post.call_count, 1)
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://translate.googleapis.com/translate_a/single')
        self.assertEqual(kwargs['params']['client'], 'gtx')
        self.assertEqual(kwargs['params']['tl'], 'tr')
        # Uzun metin URL'e sigmasin: govdede gider
        self.assertEqual(kwargs['data'], {'q': 'Hello'})
        self.assertIn('timeout', kwargs)
        # Python/OpenSSL parmak izi Google'da damgali; tarayici TLS'i taklit edilir
        self.assertEqual(kwargs['impersonate'], 'chrome')

    def test_satir_sonlari_korunur(self):
        yanit = _gtx_yanit(segmentler=[('Ilk satir.\n', 'First line.\n'), ('Ikinci satir.', 'Second line.')])
        with mock.patch('news.translation_utils.requests.post', return_value=yanit):
            self.assertEqual(tu.GtxTranslator().translate('First line.\nSecond line.'),
                             'Ilk satir.\nIkinci satir.')

    def test_captcha_sayfasi_istisna_firlatir(self):
        # 429 + HTML: _translate_via_google bunu "hata" sayip yeniden dener / devre kesici acar
        yanit = _gtx_yanit(durum=429, ham_metin='<html>unusual traffic</html>')
        with mock.patch('news.translation_utils.requests.post', return_value=yanit):
            with self.assertRaises(Exception):
                tu.GtxTranslator().translate('Hello')

    def test_json_olmayan_200_istisna_firlatir(self):
        yanit = _gtx_yanit(durum=200, ham_metin='<html>consent</html>')
        with mock.patch('news.translation_utils.requests.post', return_value=yanit):
            with self.assertRaises(Exception):
                tu.GtxTranslator().translate('Hello')

    def test_baglanti_hatasi_istisna_olarak_yukselir(self):
        with mock.patch('news.translation_utils.requests.post', side_effect=OSError('kopuk')):
            with self.assertRaises(Exception):
                tu.GtxTranslator().translate('Hello')

    def test_bos_segment_atlanir(self):
        # Google bazen son segmenti null dondurur
        yanit = mock.Mock(status_code=200, text='')
        yanit.json.return_value = [[['Merhaba', 'Hello', None, None, 3], [None, None, None, None, 0]], None, 'en']
        with mock.patch('news.translation_utils.requests.post', return_value=yanit):
            self.assertEqual(tu.GtxTranslator().translate('Hello'), 'Merhaba')


class TranslateViaGoogleGtxTests(SimpleTestCase):
    """Mevcut hiz siniri / devre kesici sarmalayicisi yeni istemciyle ayni sozlesmeyi korur."""

    def setUp(self):
        super().setUp()
        yama = mock.patch.object(tu, '_gate', tu._LocalGate())
        yama.start()
        self.addCleanup(yama.stop)
        # Testte bekleme olmasin
        for ad, deger in (('MIN_INTERVAL', 0), ('RETRY_DELAYS', (0, 0))):
            y = mock.patch.object(tu, ad, deger)
            y.start()
            self.addCleanup(y.stop)

    def test_captcha_uc_denemede_devre_kesiciyi_acar(self):
        yanit = _gtx_yanit(durum=429, ham_metin='<html>unusual traffic</html>')
        with mock.patch('news.translation_utils.requests.post', return_value=yanit) as post:
            self.assertIsNone(tu._translate_via_google('Hello'))
        self.assertEqual(post.call_count, 3)
        self.assertTrue(tu._get_gate().cooldown_active())

    def test_basarili_yanit_aynen_doner(self):
        yanit = _gtx_yanit(segmentler=[('Merhaba', 'Hello')])
        with mock.patch('news.translation_utils.requests.post', return_value=yanit):
            self.assertEqual(tu._translate_via_google('Hello'), 'Merhaba')
