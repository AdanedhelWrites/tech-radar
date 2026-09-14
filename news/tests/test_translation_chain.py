"""Ceviri saglayici zinciri testleri (spec 4.2, 4.4)."""
from django.test import SimpleTestCase

from news import translation_utils as tu
from news.tests.saglayici_yardimcilari import SahteSaglayici, SaglayiciZinciriMixin

METIN = 'Attackers can read arbitrary files.'  # 5 kelime: yanki kontrolune tabi


def google_eki(protected):
    return 'GOOGLE ' + protected


def libre_eki(protected):
    return 'LIBRE ' + protected


class SaglayiciZinciriTests(SaglayiciZinciriMixin, SimpleTestCase):

    def setUp(self):
        super().setUp()
        tu.consume_translation_failures()
        tu.consume_translation_providers()

    def test_google_basariliysa_libretranslate_cagrilmaz(self):
        google, libre = self.saglayicilari_ayarla(
            SahteSaglayici('google', google_eki), SahteSaglayici('libretranslate', libre_eki))

        self.assertEqual(tu.translate_text(METIN), 'GOOGLE ' + METIN)
        self.assertEqual(libre.cagrilar, [])
        self.assertEqual(tu.consume_translation_providers(), {'google'})
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_google_erisilemezse_libretranslate(self):
        _, libre = self.saglayicilari_ayarla(
            SahteSaglayici('google', None), SahteSaglayici('libretranslate', libre_eki))

        self.assertEqual(tu.translate_text(METIN), 'LIBRE ' + METIN)
        self.assertEqual(len(libre.cagrilar), 1)
        self.assertEqual(tu.consume_translation_providers(), {'libretranslate'})

    def test_google_dogrulamaya_takilirsa_libretranslate(self):
        self.saglayicilari_ayarla(
            SahteSaglayici('google', lambda p: p),  # yanki
            SahteSaglayici('libretranslate', libre_eki))

        self.assertEqual(tu.translate_text(METIN), 'LIBRE ' + METIN)
        self.assertEqual(tu.consume_translation_providers(), {'libretranslate'})
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_hicbiri_basarisizsa_orijinal_ve_sayac(self):
        self.saglayicilari_ayarla(
            SahteSaglayici('google', None), SahteSaglayici('libretranslate', lambda p: p))

        self.assertEqual(tu.translate_text(METIN), METIN)
        self.assertEqual(tu.consume_translation_failures(), 1)
        self.assertEqual(tu.consume_translation_providers(), set())

    def test_hazir_olmayan_saglayici_cagrilmaz(self):
        google, _ = self.saglayicilari_ayarla(
            SahteSaglayici('google', google_eki, hazir=False), SahteSaglayici('libretranslate', libre_eki))

        self.assertEqual(tu.translate_text(METIN), 'LIBRE ' + METIN)
        self.assertEqual(google.cagrilar, [])

    def test_saglayici_istisnasi_zinciri_kesmez(self):
        def patlayan(_):
            raise RuntimeError('beklenmeyen')
        self.saglayicilari_ayarla(
            SahteSaglayici('google', patlayan), SahteSaglayici('libretranslate', libre_eki))

        self.assertEqual(tu.translate_text(METIN), 'LIBRE ' + METIN)

    def test_yalnizca_google_kisiti(self):
        _, libre = self.saglayicilari_ayarla(
            SahteSaglayici('google', None), SahteSaglayici('libretranslate', libre_eki))

        with tu.yalnizca_saglayicilar('google'):
            self.assertEqual(tu.translate_text(METIN), METIN)
        self.assertEqual(libre.cagrilar, [])
        self.assertEqual(tu.consume_translation_failures(), 1)
        # Kisit baglam disinda kalkar
        self.assertEqual(tu.translate_text(METIN), 'LIBRE ' + METIN)

    def test_herhangi_saglayici_hazir(self):
        google, libre = self.saglayicilari_ayarla(
            SahteSaglayici('google', hazir=False), SahteSaglayici('libretranslate', hazir=True))
        self.assertTrue(tu.herhangi_saglayici_hazir())
        with tu.yalnizca_saglayicilar('google'):
            self.assertFalse(tu.herhangi_saglayici_hazir())
        libre.hazir = False
        self.assertFalse(tu.herhangi_saglayici_hazir())

    def test_uzun_metnin_parcalari_farkli_saglayicilardan_gelebilir(self):
        birinci, ikinci = 'First sentence is right here.', 'Second sentence is right here.'
        self.saglayicilari_ayarla(
            SahteSaglayici('google', {birinci: 'Birinci cümle tam burada.'}),
            SahteSaglayici('libretranslate', libre_eki))

        tu.translate_long_text(f'{birinci} {ikinci}', chunk_size=35)

        self.assertEqual(tu.consume_translation_providers(), {'google', 'libretranslate'})

    def test_consume_translation_providers_sifirlar(self):
        self.saglayicilari_ayarla(SahteSaglayici('google', google_eki))
        tu.translate_text(METIN)
        self.assertEqual(tu.consume_translation_providers(), {'google'})
        self.assertEqual(tu.consume_translation_providers(), set())


class KayitSaglayicisiTests(SimpleTestCase):

    def test_en_dusuk_kalite_belirleyicidir(self):
        self.assertEqual(tu.kayit_saglayicisi({'google', 'libretranslate'}), 'libretranslate')
        self.assertEqual(tu.kayit_saglayicisi({'libretranslate'}), 'libretranslate')
        self.assertEqual(tu.kayit_saglayicisi({'google'}), 'google')
        self.assertEqual(tu.kayit_saglayicisi(set()), '')
