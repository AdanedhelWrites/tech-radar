"""v1 serializer bicimi ve filtre testleri."""
from datetime import date

from django.test import TestCase

from news.api_v1.serializers import AINewsEntryV1Serializer, CVEEntryV1Serializer
from news.models import AINewsEntry, CVEEntry


class SerializerBicimTests(TestCase):
    """Yanit bicimi sozlesmedir: alan adlari ve ic ice dil yapisi korunmali."""

    def test_ortak_alanlar_ve_ic_ice_dil(self):
        entry = AINewsEntry.objects.create(
            source='MIT Tech Review AI', original_title='Model released',
            turkish_title='Model yayinlandi', original_description='Long text',
            turkish_description='Uzun metin', link='https://ornek.test/ai/1',
            published_date=date(2026, 9, 12),
        )
        veri = AINewsEntryV1Serializer(entry).data
        self.assertEqual(set(veri.keys()), {
            'id', 'type', 'source', 'title', 'description', 'link',
            'published_date', 'needs_translation', 'updated_at',
        })
        self.assertEqual(veri['type'], 'ai')
        self.assertEqual(veri['title'], {'original': 'Model released', 'tr': 'Model yayinlandi'})
        self.assertEqual(veri['description'], {'original': 'Long text', 'tr': 'Uzun metin'})

    def test_ceviri_bekleyende_tr_bos_gelir(self):
        """Tuketici title.tr || title.original ile Ingilizceye dusebilmeli."""
        entry = AINewsEntry.objects.create(
            source='Test', original_title='Only english', original_description='Body',
            link='https://ornek.test/ai/2', published_date=date(2026, 9, 12),
            needs_translation=True,
        )
        veri = AINewsEntryV1Serializer(entry).data
        self.assertEqual(veri['title']['tr'], '')
        self.assertEqual(veri['title']['original'], 'Only english')
        self.assertTrue(veri['needs_translation'])

    def test_cve_siddeti_normalize_edilir(self):
        cve = CVEEntry.objects.create(
            cve_id='CVE-2026-1000', source='NVD', original_title='RCE',
            original_description='Body', severity='Yüksek', cvss_score=8.8,
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/1000',
        )
        veri = CVEEntryV1Serializer(cve).data
        self.assertEqual(veri['severity'], {'code': 'high', 'label': 'Yüksek'})
        self.assertEqual(veri['cve_id'], 'CVE-2026-1000')
        self.assertEqual(veri['type'], 'cve')

    def test_bilinmeyen_siddet_kodu_none_olur(self):
        """Task'lar siddeti bulamayinca 'Bilinmiyor' yaziyor; sozlesmede kod None olur."""
        cve = CVEEntry.objects.create(
            cve_id='CVE-2026-1001', source='NVD', original_title='X',
            original_description='Body', severity='Bilinmiyor',
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/1001',
        )
        veri = CVEEntryV1Serializer(cve).data
        self.assertEqual(veri['severity'], {'code': None, 'label': 'Bilinmiyor'})
