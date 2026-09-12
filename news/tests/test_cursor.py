"""Imlec (cursor) tabanli delta cekme testleri."""
from datetime import date

from django.test import TestCase

from news.models import AINewsEntry, CVEEntry


class UpdatedAtFieldTests(TestCase):
    """updated_at her kayitta dolu olmali ve her kayitta ilerlemeli."""

    def test_updated_at_kayit_olusturulunca_dolar(self):
        entry = AINewsEntry.objects.create(
            source='Test', original_title='A', original_description='B',
            link='https://ornek.test/1', published_date=date(2026, 9, 12),
        )
        self.assertIsNotNone(entry.updated_at)

    def test_updated_at_her_kayitta_ilerler(self):
        entry = AINewsEntry.objects.create(
            source='Test', original_title='A', original_description='B',
            link='https://ornek.test/2', published_date=date(2026, 9, 12),
        )
        once = entry.updated_at
        entry.turkish_title = 'A tercume'
        entry.save()
        entry.refresh_from_db()
        self.assertGreater(entry.updated_at, once)

    def test_cve_modelinde_de_var(self):
        cve = CVEEntry.objects.create(
            cve_id='CVE-2026-0001', source='NVD', original_title='A',
            original_description='B', published_date=date(2026, 9, 12),
            link='https://ornek.test/cve/1',
        )
        self.assertIsNotNone(cve.updated_at)
