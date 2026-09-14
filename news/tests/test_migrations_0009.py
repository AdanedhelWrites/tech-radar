"""Migration 0009 veri adimi: eski cevrilmis kayitlar sessizce 'google' olur (kullanici secimi)."""
import importlib
from datetime import date

from django.apps import apps
from django.test import TestCase

from news.models import AINewsEntry, CVEEntry


class CeviriSaglayicisiMigrationTests(TestCase):

    def setUp(self):
        self.goc = importlib.import_module('news.migrations.0009_translation_provider')
        self.cevrilmis = AINewsEntry.objects.create(
            source='Test', original_title='A', turkish_title='A tr', original_description='B',
            link='https://ornek.test/goc/1', published_date=date(2026, 9, 14), needs_translation=False)
        self.bekleyen = CVEEntry.objects.create(
            cve_id='CVE-2026-9001', source='NVD', original_title='CVE-2026-9001',
            original_description='Pending body.', published_date=date(2026, 9, 14),
            link='https://ornek.test/goc/2', needs_translation=True)

    def test_cevrilmis_google_bekleyen_bos(self):
        self.goc.eski_cevirileri_google_isaretle(apps, None)

        self.cevrilmis.refresh_from_db()
        self.bekleyen.refresh_from_db()
        self.assertEqual(self.cevrilmis.translation_provider, 'google')
        self.assertEqual(self.bekleyen.translation_provider, '')

    def test_isaretleme_updated_at_ilerletmez(self):
        once = AINewsEntry.objects.get(pk=self.cevrilmis.pk).updated_at
        self.goc.eski_cevirileri_google_isaretle(apps, None)
        self.assertEqual(AINewsEntry.objects.get(pk=self.cevrilmis.pk).updated_at, once)

    def test_geri_alma_alani_bosaltir(self):
        self.goc.eski_cevirileri_google_isaretle(apps, None)
        self.goc.geri_al(apps, None)
        self.cevrilmis.refresh_from_db()
        self.assertEqual(self.cevrilmis.translation_provider, '')
