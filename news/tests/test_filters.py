"""v1 serializer bicimi ve filtre testleri."""
from datetime import date

from django.test import TestCase

from news.api_v1.serializers import AINewsEntryV1Serializer, CVEEntryV1Serializer
from news.models import AINewsEntry, CVEEntry
from news.tests.base import V1TestCase


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
            'published_date', 'needs_translation', 'updated_at', 'translation_provider',
        })
        self.assertEqual(veri['type'], 'ai')
        self.assertEqual(veri['title'], {'original': 'Model released', 'tr': 'Model yayinlandi'})
        self.assertEqual(veri['description'], {'original': 'Long text', 'tr': 'Uzun metin'})

    def test_saglayici_bos_ise_null(self):
        entry = AINewsEntry.objects.create(
            source='Test', original_title='T', original_description='D',
            link='https://ornek.test/ai/saglayici-bos', published_date=date(2026, 9, 14))
        self.assertIsNone(AINewsEntryV1Serializer(entry).data['translation_provider'])

    def test_saglayici_degeri_doner(self):
        entry = AINewsEntry.objects.create(
            source='Test', original_title='T', original_description='D',
            link='https://ornek.test/ai/saglayici-lt', published_date=date(2026, 9, 14),
            translation_provider='libretranslate')
        self.assertEqual(AINewsEntryV1Serializer(entry).data['translation_provider'], 'libretranslate')

    def test_eski_api_serializeri_alani_icerir(self):
        from news.serializers import AINewsEntrySerializer
        entry = AINewsEntry.objects.create(
            source='Test', original_title='T', original_description='D',
            link='https://ornek.test/ai/eski-api', published_date=date(2026, 9, 14),
            translation_provider='google')
        self.assertEqual(AINewsEntrySerializer(entry).data['translation_provider'], 'google')

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


from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from news.models import DevToolsEntry, KubernetesEntry


class FiltreTests(V1TestCase):
    """Filtreler tuketicinin gereksiz veri cekmesini onler."""

    def setUp(self):
        super().setUp()
        kullanici = User.objects.create_user('filtre-test', password='parola-yok-test')
        self.baslik = {'HTTP_AUTHORIZATION': f'Token {Token.objects.create(user=kullanici).key}'}
        for i, (siddet, kaynak) in enumerate([
            ('Kritik', 'NVD'), ('Yüksek', 'NVD'), ('Orta', 'CISA'),
            ('Düşük', 'CISA'), ('Bilinmiyor', 'NVD'),
        ], start=1):
            CVEEntry.objects.create(
                cve_id=f'CVE-2026-20{i:02d}', source=kaynak, original_title='X',
                original_description='Body', severity=siddet,
                published_date=date(2026, 9, 12), link=f'https://ornek.test/cve/20{i:02d}',
            )

    def _kodlar(self, sorgu):
        govde = self.client.get(f'/api/v1/cve/?{sorgu}', **self.baslik).json()
        return sorted(k['severity']['code'] or 'none' for k in govde['results'])

    def test_min_severity_high_kritik_ve_yuksek_getirir(self):
        self.assertEqual(self._kodlar('min_severity=high'), ['critical', 'high'])

    def test_min_severity_low_bilinmeyeni_disarida_birakir(self):
        """Bilinmeyen siddet siralamaya girmez; sessizce dahil edilmemeli."""
        self.assertEqual(self._kodlar('min_severity=low'), ['critical', 'high', 'low', 'medium'])

    def test_severity_tam_liste(self):
        self.assertEqual(self._kodlar('severity=critical,low'), ['critical', 'low'])

    def test_gecersiz_severity_400(self):
        yanit = self.client.get('/api/v1/cve/?min_severity=cok-kotu', **self.baslik)
        self.assertEqual(yanit.status_code, 400)
        self.assertEqual(yanit.json()['error']['code'], 'invalid_parameter')

    def test_source_filtresi(self):
        govde = self.client.get('/api/v1/cve/?source=CISA', **self.baslik).json()
        self.assertEqual({k['source'] for k in govde['results']}, {'CISA'})

    def test_needs_translation_filtresi(self):
        CVEEntry.objects.filter(cve_id='CVE-2026-2001').update(needs_translation=True)
        govde = self.client.get('/api/v1/cve/?needs_translation=true', **self.baslik).json()
        self.assertEqual([k['cve_id'] for k in govde['results']], ['CVE-2026-2001'])

    def test_limit_tavani_uygulanir(self):
        govde = self.client.get('/api/v1/cve/?limit=9999', **self.baslik).json()
        self.assertLessEqual(govde['count'], 500)

    def test_gecersiz_limit_400(self):
        yanit = self.client.get('/api/v1/cve/?limit=sifir', **self.baslik)
        self.assertEqual(yanit.status_code, 400)

    def test_kubernetes_kategori_filtresi(self):
        for i, kategori in enumerate(['security', 'release', 'blog'], start=1):
            KubernetesEntry.objects.create(
                source='Kubernetes Blog', original_title='X', original_description='B',
                link=f'https://ornek.test/k8s/{i}', published_date=date(2026, 9, 12),
                category=kategori,
            )
        govde = self.client.get('/api/v1/kubernetes/?category=security', **self.baslik).json()
        self.assertEqual([k['category'] for k in govde['results']], ['security'])

    def test_devtools_entry_type_filtresi(self):
        for i, tur in enumerate(['release', 'blog'], start=1):
            DevToolsEntry.objects.create(
                source='Terraform', original_title='X', original_description='B',
                link=f'https://ornek.test/dt/{i}', published_date=date(2026, 9, 12),
                entry_type=tur,
            )
        govde = self.client.get('/api/v1/devtools/?entry_type=release', **self.baslik).json()
        self.assertEqual([k['entry_type'] for k in govde['results']], ['release'])
