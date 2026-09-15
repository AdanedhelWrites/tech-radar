"""
Ceviri dayanikliligi testleri.

Cekim aninda tek saglayici LibreTranslate'tir (Google 2026-09-15'te kaldirildi). Bu testler
su davranislari korur:
  - Saglayici erisilemez/hata verirse metin orijinal kalir ve basarisizlik sayilir
  - Basarisiz ceviriler sayilir; task kaydi `needs_translation` olarak isaretler
  - Isaretli kayitlar sonraki cekimde tekrar islenir (skip_existing onlari atlamaz)
  - Aralik kapisi ve devre kesici Redis uzerinden tum worker process'lerince paylasilir

Dis servisler icin sahte cevirmen kullanilir; Redis ve DB gercektir.
"""
import time
import uuid
from datetime import date
from unittest import mock

from django.test import TestCase, override_settings
from django_redis import get_redis_connection

from news import tasks
from news import translation_providers as tp
from news import translation_utils as tu
from news.models import AINewsEntry
from news.tests.saglayici_yardimcilari import SahteSaglayici

ERROR_PAGE = ('Error 500 (Server Error)!!1500.That’s an error.There was an error. '
              'Please try again later.That’s all we know.')

# Task'lar sonuc listesini cache'e yazar; testler canli Redis cache'ini ezmesin
LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


class FakeTranslator:
    """Gercek saglayici yerine gecer. Girdi metnine gore yanit verir; bilinmeyen metne hata sayfasi doner."""

    def __init__(self, answers=None, default=ERROR_PAGE):
        self.answers = answers or {}
        self.default = default
        self.calls = []

    def translate(self, text):
        self.calls.append(text)
        answer = self.answers.get(text, self.default)
        if isinstance(answer, Exception):
            raise answer
        return answer


class SequenceTranslator(FakeTranslator):
    """Sirayla verilen yanitlari dondurur; son yanit tekrar eder."""

    def __init__(self, *responses):
        super().__init__()
        self.responses = list(responses)

    def translate(self, text):
        self.calls.append(text)
        answer = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


class TranslationGateMixin:
    """Her testte temiz, tek-process kapi; zincirde sahte LibreTranslate."""

    def setUp(self):
        super().setUp()
        yama = mock.patch.object(tp, '_lt_gate', tu._LocalGate())
        yama.start()
        self.addCleanup(yama.stop)
        tu.consume_translation_failures()
        tu.consume_translation_providers()

    def use_translator(self, translator):
        """FakeTranslator'i zincirdeki tek saglayici (libretranslate) olarak takar.

        FakeTranslator sozlesmesi korunur: bilinmeyen metne ERROR_PAGE (=> saglayici
        erisilemedi, None), Exception degerine istisna (zincir yakalar, orijinal kalir).
        """
        def cevap(protected):
            yanit = translator.translate(protected)
            return None if yanit == ERROR_PAGE else yanit

        yama = mock.patch.object(tp, 'SAGLAYICILAR', (SahteSaglayici('libretranslate', cevap),))
        yama.start()
        self.addCleanup(yama.stop)
        return translator


class TranslateTextResilienceTests(TranslationGateMixin, TestCase):

    def test_saglayici_erisilemezse_orijinal_doner_ve_basarisizlik_sayilir(self):
        self.use_translator(FakeTranslator())  # her metne hata sayfasi => erisilemedi
        self.assertEqual(tu.translate_text('Farmers adopt new sensors'), 'Farmers adopt new sensors')
        self.assertEqual(tu.consume_translation_failures(), 1)

    def test_saglayici_istisnasi_orijinal_birakir(self):
        self.use_translator(FakeTranslator({'Farmers adopt new sensors': RuntimeError('patladi')}))
        self.assertEqual(tu.translate_text('Farmers adopt new sensors'), 'Farmers adopt new sensors')
        self.assertEqual(tu.consume_translation_failures(), 1)

    def test_failed_chunk_in_long_text_is_recorded_and_kept_in_original(self):
        self.use_translator(FakeTranslator({'First sentence is here.': 'Birinci cümle burada.'}))

        result = tu.translate_long_text('First sentence is here. Second sentence is here.', chunk_size=30)

        self.assertIn('Birinci cümle burada.', result)
        self.assertIn('Second sentence is here.', result)
        self.assertEqual(tu.consume_translation_failures(), 1)

    def test_consume_translation_failures_resets_counter(self):
        self.use_translator(SequenceTranslator(ERROR_PAGE))
        tu.translate_text('Blocked text.')

        self.assertEqual(tu.consume_translation_failures(), 1)
        self.assertEqual(tu.consume_translation_failures(), 0)


class RedisGateTests(TestCase):
    """Hiz siniri ve cooldown'un process'ler arasi paylasildigini gercek Redis ile dogrular."""

    def setUp(self):
        self.client = get_redis_connection('default')
        self.prefix = f'test-translate-{uuid.uuid4().hex}'
        self.addCleanup(lambda: [self.client.delete(k) for k in self.client.keys(f'{self.prefix}:*')])

    def test_second_process_waits_for_shared_interval(self):
        first, second = tu._RedisGate(self.client, self.prefix), tu._RedisGate(self.client, self.prefix)
        first.wait_for_slot(0.4)
        started = time.monotonic()

        second.wait_for_slot(0.4)

        self.assertGreaterEqual(time.monotonic() - started, 0.3)

    def test_cooldown_started_by_one_process_blocks_the_other(self):
        first, second = tu._RedisGate(self.client, self.prefix), tu._RedisGate(self.client, self.prefix)
        unrelated = tu._RedisGate(self.client, f'{self.prefix}-other')

        first.start_cooldown(5)

        self.assertTrue(second.cooldown_active())
        self.assertFalse(unrelated.cooldown_active())


class DropExistingTests(TestCase):

    def test_rows_awaiting_translation_are_processed_again(self):
        today = date.today()
        AINewsEntry.objects.create(source='S', original_title='a', turkish_title='a-tr', original_description='d',
                                   link='https://example.com/a', published_date=today, needs_translation=False)
        AINewsEntry.objects.create(source='S', original_title='b', turkish_title='b', original_description='d',
                                   link='https://example.com/b', published_date=today, needs_translation=True)
        entries = [{'link': 'https://example.com/a'}, {'link': 'https://example.com/b'},
                   {'link': 'https://example.com/c'}]

        result = tasks._drop_existing(entries, AINewsEntry, 'link')

        self.assertEqual([e['link'] for e in result], ['https://example.com/b', 'https://example.com/c'])


@override_settings(CACHES=LOCMEM_CACHE)
class FetchAINewsTaskTranslationTests(TranslationGateMixin, TestCase):
    """Gercek MultiAINewsScraper.process_entries + gercek task; sadece ag (fetch_all) ve saglayici sahte."""

    def raw(self, title, description, slug):
        return {'title': title, 'description': description, 'link': f'https://example.com/{slug}',
                'date': date.today().strftime('%Y-%m-%d'), 'source': 'MIT Tech Review AI'}

    def run_task(self, raw_entries):
        with mock.patch.object(tasks.MultiAINewsScraper, 'fetch_all', return_value=raw_entries):
            return tasks.fetch_ai_news_task(days=30)

    def test_only_the_entry_whose_translation_failed_is_flagged(self):
        self.use_translator(FakeTranslator({
            'Farmers adopt new sensors': 'Çiftçiler yeni sensörler benimsiyor',
            'Sensors measure soil moisture every hour.': 'Sensörler toprak nemini her saat ölçüyor.',
        }))
        result = self.run_task([
            self.raw('Robots learn to sort laundry', 'The team trained robots for months.', 'robots'),
            self.raw('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'farmers'),
        ])

        self.assertEqual(result, {'success': True, 'count': 2})
        failed = AINewsEntry.objects.get(link='https://example.com/robots')
        translated = AINewsEntry.objects.get(link='https://example.com/farmers')
        self.assertTrue(failed.needs_translation)
        self.assertEqual(failed.turkish_title, 'Robots learn to sort laundry')
        self.assertFalse(translated.needs_translation)

    def test_pending_row_is_translated_and_unflagged_on_next_fetch(self):
        AINewsEntry.objects.create(
            source='MIT Tech Review AI', original_title='Farmers adopt new sensors',
            turkish_title='Farmers adopt new sensors', original_description='Sensors measure soil moisture every hour.',
            turkish_description='Sensors measure soil moisture every hour.',
            link='https://example.com/farmers', published_date=date.today(), needs_translation=True)
        self.use_translator(FakeTranslator({
            'Farmers adopt new sensors': 'Çiftçiler yeni sensörler benimsiyor',
            'Sensors measure soil moisture every hour.': 'Sensörler toprak nemini her saat ölçüyor.',
        }))

        self.run_task([self.raw('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'farmers')])

        entry = AINewsEntry.objects.get(link='https://example.com/farmers')
        self.assertFalse(entry.needs_translation)
        self.assertNotEqual(entry.turkish_title, 'Farmers adopt new sensors')
