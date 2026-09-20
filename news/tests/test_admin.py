"""Admin duzeltmeleri (spec 2026-09-20-a4, bolum 3.6)."""
from datetime import date

from django.contrib import admin
from django.test import TestCase

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, FetchRun, KubernetesEntry, NewsArticle, SREEntry,
)


class AdminKayitTests(TestCase):

    def test_alti_model_ve_fetchrun_kayitli(self):
        for model in (NewsArticle, CVEEntry, KubernetesEntry, SREEntry,
                      DevToolsEntry, AINewsEntry, FetchRun):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)

    def test_fetchrun_salt_okunur(self):
        admin_sinifi = admin.site._registry[FetchRun]

        self.assertFalse(admin_sinifi.has_add_permission(None))
        self.assertFalse(admin_sinifi.has_change_permission(None))
        self.assertFalse(admin_sinifi.has_delete_permission(None),
                         'Denetim tablosu silinebilir olmamali (spec: manuel silme'
                         ' vakalarindan biri budur)')

    def test_alti_modelde_ceviri_filtreleri_var(self):
        for model in (NewsArticle, CVEEntry, KubernetesEntry, SREEntry,
                      DevToolsEntry, AINewsEntry):
            with self.subTest(model=model.__name__):
                filtreler = admin.site._registry[model].list_filter
                self.assertIn('needs_translation', filtreler)
                self.assertIn('translation_provider', filtreler)

    def test_karsilastirma_alani_iki_metni_de_icerir(self):
        kayit = CVEEntry.objects.create(
            cve_id='CVE-2026-1', source='NVD', original_title='Original title',
            original_description='A remote attacker can read files.',
            turkish_description='Uzaktaki bir saldirgan dosyalari okuyabilir.',
            published_date=date(2026, 9, 12), link='https://ornek.test/1')

        html = admin.site._registry[CVEEntry].karsilastirma(kayit)

        self.assertIn('A remote attacker can read files.', html)
        self.assertIn('Uzaktaki bir saldirgan dosyalari okuyabilir.', html)

    def test_karsilastirma_xss_veriyi_kaciyor(self):
        # XSS: <script> etiketini iceren icerik kaciyor (Critical 1)
        kayit = CVEEntry.objects.create(
            cve_id='CVE-2026-2', source='NVD', original_title='<script>alert(1)</script>',
            original_description='<script>alert(1)</script>',
            turkish_description='Saldirgan etkinlestirilebilir.',
            published_date=date(2026, 9, 12), link='https://ornek.test/2')

        html = admin.site._registry[CVEEntry].karsilastirma(kayit)

        # Raw <script> etiketi olmamali; escaped form olmali
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('alert(1)', html)

    def test_karsilastirma_koseli_ayraclar_format_templateini_bozmaz(self):
        # Brace: {} iceren JSON/kod ornekleri format() cagrisini cikarmaz (Critical 2)
        kayit = CVEEntry.objects.create(
            cve_id='CVE-2026-3', source='NVD',
            original_title='Issue with JSON: {"cve": "CVE-2026-3"}',
            original_description='Example code: if (x > 5) { return y; }',
            turkish_description='Kodlama hatası burada',
            published_date=date(2026, 9, 12), link='https://ornek.test/3')

        # Hata yukseltmez; string bozulmaz (format_html_join tum karakterleri kaciriyor)
        html = admin.site._registry[CVEEntry].karsilastirma(kayit)

        # JSON ve braces iceren metin mevcut; tablo yapisi format() calismadigini kanitlar
        self.assertIn('CVE-2026-3', html)
        self.assertIn('{ return y; }', html)
        self.assertIn('<tr>', html)
        self.assertIn('<td', html)
