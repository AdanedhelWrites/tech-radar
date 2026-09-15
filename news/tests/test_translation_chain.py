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
    # Adlar temsili: zincir saglayici adindan bagimsizdir; canlida yalniz libretranslate var.

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

    def test_herhangi_saglayici_hazir(self):
        google, libre = self.saglayicilari_ayarla(
            SahteSaglayici('google', hazir=False), SahteSaglayici('libretranslate', hazir=True))
        self.assertTrue(tu.herhangi_saglayici_hazir())
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


from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from news import tasks
from news.models import AINewsEntry
from news.tests.base import LOCMEM_CACHE
from news.tests.test_translation import TranslationGateMixin


def _ham_ai(baslik, govde, slug):
    return {'title': baslik, 'description': govde, 'link': f'https://ornek.test/zincir/{slug}',
            'date': '2026-09-14', 'source': 'MIT Tech Review AI'}


@override_settings(CACHES=LOCMEM_CACHE)
class FetchTaskSaglayiciTests(SaglayiciZinciriMixin, TranslationGateMixin, TestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        tu.consume_translation_providers()

    def _cek(self, girdiler):
        with mock.patch.object(tasks.MultiAINewsScraper, 'fetch_all', return_value=girdiler):
            return tasks.fetch_ai_news_task(days=30)

    def test_task_kayit_saglayicisini_yazar(self):
        self.saglayicilari_ayarla(
            SahteSaglayici('google', {
                'Only google title': 'Yalnızca google başlığı',
                'Google body text for this story.': 'Bu haberin google gövde metni.',
                'Mixed story title': 'Karışık haber başlığı',
            }),
            SahteSaglayici('libretranslate', libre_eki))

        self._cek([
            _ham_ai('Only google title', 'Google body text for this story.', 'google'),
            _ham_ai('Mixed story title', 'Body text that only libre translates.', 'karisik'),
        ])

        google = AINewsEntry.objects.get(link='https://ornek.test/zincir/google')
        karisik = AINewsEntry.objects.get(link='https://ornek.test/zincir/karisik')
        self.assertEqual(google.translation_provider, 'google')
        self.assertFalse(google.needs_translation)
        self.assertEqual(karisik.translation_provider, 'libretranslate')
        self.assertFalse(karisik.needs_translation)

    def test_hicbir_saglayici_yoksa_bos_ve_bekleyen(self):
        self.saglayicilari_ayarla(
            SahteSaglayici('google', hazir=False), SahteSaglayici('libretranslate', hazir=False))

        self._cek([_ham_ai('Nothing translates this title', 'Nothing translates this body.', 'yok')])

        kayit = AINewsEntry.objects.get(link='https://ornek.test/zincir/yok')
        self.assertEqual(kayit.translation_provider, '')
        self.assertTrue(kayit.needs_translation)
