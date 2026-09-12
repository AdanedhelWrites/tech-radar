"""
Ceviri dayanikliligi testleri.

Ucretsiz Google Translate ucu IP bazli kisitlama uygular. Bu testler su davranislari korur:
  - Hata sayfasi / istisna gelince yeniden denenir, denemeler tukenince orijinal metin doner
  - Denemeler tukenince devre kesici (cooldown) acilir ve Google'a hic gidilmez
  - Basarisiz ceviriler sayilir; task kaydi `needs_translation` olarak isaretler
  - Isaretli kayitlar sonraki cekimde tekrar islenir (skip_existing onlari atlamaz)
  - Hiz siniri ve cooldown Redis uzerinden tum worker process'lerince paylasilir

Google Translate harici servis oldugu icin sahte cevirmen kullanilir; Redis ve DB gercektir.
"""
import time
import uuid
from datetime import date
from unittest import mock

from django.test import TestCase, override_settings
from django_redis import get_redis_connection

from news import tasks
from news import translation_utils as tu
from news.models import AINewsEntry

ERROR_PAGE = ('Error 500 (Server Error)!!1500.That’s an error.There was an error. '
              'Please try again later.That’s all we know.')

# Task'lar sonuc listesini cache'e yazar; testler canli Redis cache'ini ezmesin
LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


class FakeTranslator:
    """GoogleTranslator yerine gecer. Girdi metnine gore yanit verir; bilinmeyen metne hata sayfasi doner."""

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
    """Her testte temiz, tek-process gate; beklemeler sifir."""

    def setUp(self):
        super().setUp()
        for target, value in (('_gate', tu._LocalGate()), ('MIN_INTERVAL', 0.0),
                              ('RETRY_DELAYS', (0.0, 0.0)), ('COOLDOWN_SECONDS', 60)):
            patcher = mock.patch.object(tu, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        tu.consume_translation_failures()

    def use_translator(self, translator):
        patcher = mock.patch.object(tu, '_make_translator', return_value=translator)
        patcher.start()
        self.addCleanup(patcher.stop)
        return translator


class TranslateTextResilienceTests(TranslationGateMixin, TestCase):

    def test_blocked_google_returns_original_text_after_retries_and_records_failure(self):
        for label, response in (('hata sayfasi', ERROR_PAGE),
                                ('istisna', Exception('No translation was found')),
                                ('bos yanit', '')):
            with self.subTest(label):
                tu._gate.start_cooldown(0)  # onceki alt testin cooldown'unu sifirla
                translator = self.use_translator(SequenceTranslator(response))

                result = tu.translate_text('Cloud security update released today.')

                self.assertEqual(result, 'Cloud security update released today.')
                self.assertEqual(len(translator.calls), 3)  # ilk deneme + 2 yeniden deneme
                self.assertEqual(tu.consume_translation_failures(), 1)

    def test_transient_error_recovers_on_retry(self):
        translator = self.use_translator(
            SequenceTranslator(ERROR_PAGE, 'Bulut güvenlik güncellemesi bugün yayınlandı.'))

        result = tu.translate_text('Cloud security update released today.')

        self.assertEqual(result, 'Bulut güvenlik güncellemesi bugün yayınlandı.')
        self.assertEqual(len(translator.calls), 2)
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_exhausted_retries_open_cooldown_and_skip_google_entirely(self):
        translator = self.use_translator(SequenceTranslator(ERROR_PAGE))
        tu.translate_text('First article body.')
        calls_after_first = len(translator.calls)

        result = tu.translate_text('Second article body.')

        self.assertEqual(result, 'Second article body.')
        self.assertEqual(len(translator.calls), calls_after_first)  # cooldown: Google'a gidilmedi
        self.assertEqual(tu.consume_translation_failures(), 2)

    def test_cooldown_expires_and_translation_resumes(self):
        with mock.patch.object(tu, 'COOLDOWN_SECONDS', 0.05):
            self.use_translator(SequenceTranslator(ERROR_PAGE, ERROR_PAGE, ERROR_PAGE, 'Tekrar çalışıyor.'))
            tu.translate_text('Blocked now.')
            time.sleep(0.1)

            result = tu.translate_text('Works again.')

        self.assertEqual(result, 'Tekrar çalışıyor.')

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

    def test_django_environment_uses_shared_redis_gate(self):
        with mock.patch.object(tu, '_gate', None):
            self.assertIsInstance(tu._get_gate(), tu._RedisGate)


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
    """Gercek MultiAINewsScraper.process_entries + gercek task; sadece ag (fetch_all) ve Google sahte."""

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
        with mock.patch.object(tu, 'COOLDOWN_SECONDS', 0):  # ikinci kayit cooldown'a takilmasin
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
