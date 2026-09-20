"""FetchRun modeli ve sinyal iskeleti (spec 2026-09-20-a4, bolum 3.1-3.3)."""
from django.test import TestCase
from django.utils import timezone

from news.models import FetchRun


class FetchRunModelTests(TestCase):

    def test_varsayilanlar(self):
        kayit = FetchRun.objects.create(section='cve', trigger='beat', status='running')

        self.assertEqual(kayit.fetched_count, 0)
        self.assertEqual(kayit.saved_count, 0)
        self.assertEqual(kayit.translation_failures, 0)
        self.assertEqual(kayit.total_after, 0)
        self.assertEqual(kayit.by_provider, {})
        self.assertEqual(kayit.stopped_reason, '')
        self.assertEqual(kayit.error, '')
        self.assertIsNone(kayit.finished_at)
        self.assertIsNotNone(kayit.started_at)

    def test_by_provider_sozluk_saklar(self):
        kayit = FetchRun.objects.create(section='retranslate', trigger='beat', status='success',
                                        by_provider={'gemini': 12, 'libretranslate': 3})
        kayit.refresh_from_db()

        self.assertEqual(kayit.by_provider['gemini'], 12)

    def test_siralama_en_yeni_once(self):
        eski = FetchRun.objects.create(section='cve', trigger='beat', status='success')
        FetchRun.objects.filter(pk=eski.pk).update(
            started_at=timezone.now() - timezone.timedelta(days=1))
        yeni = FetchRun.objects.create(section='cve', trigger='beat', status='success')

        self.assertEqual(list(FetchRun.objects.all())[0].pk, yeni.pk)

    def test_updated_at_alani_yok(self):
        """FetchRun v1 delta akisina girmez; updated_at tasimaz (spec 3.1)."""
        alanlar = {f.name for f in FetchRun._meta.get_fields()}

        self.assertNotIn('updated_at', alanlar)
