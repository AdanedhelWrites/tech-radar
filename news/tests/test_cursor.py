"""Imlec (cursor) tabanli delta cekme testleri."""
from datetime import date

from django.test import TestCase
from django.utils import timezone

from news.api_v1.cursor import InvalidCursor, apply_cursor, decode_cursor, encode_cursor
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


class CursorCodecTests(TestCase):
    """Imlec kodlanip cozuldugunde ayni degeri vermeli; bozuk girdi net hata uretmeli."""

    def test_kodla_coz_ayni_degeri_verir(self):
        moment = timezone.now()
        deger = encode_cursor(moment, 42)
        cozulen_moment, cozulen_id = decode_cursor(deger)
        self.assertEqual(cozulen_moment, moment)
        self.assertEqual(cozulen_id, 42)

    def test_imlec_opak_gorunur(self):
        """Imlec duz metin sizdirmamali; tuketici icini acmaya calismamali."""
        deger = encode_cursor(timezone.now(), 42)
        self.assertNotIn('updated_at', deger)
        self.assertNotIn('{', deger)

    def test_bozuk_imlec_hata_firlatir(self):
        for bozuk in ['', 'bu-base64-degil!!', 'YWJj', 'eyJ1IjogImdlY2Vyc2l6IiwgImkiOiAxfQ']:
            with self.subTest(bozuk=bozuk):
                with self.assertRaises(InvalidCursor):
                    decode_cursor(bozuk)


class ApplyCursorTests(TestCase):
    """apply_cursor, imlecten sonraki kayitlari dondurmeli; ayni damgada id ayirt edici olmali."""

    def setUp(self):
        self.moment = timezone.now()
        for i in range(1, 4):
            AINewsEntry.objects.create(
                source='Test', original_title=f'Baslik {i}', original_description='X',
                link=f'https://ornek.test/apply/{i}', published_date=date(2026, 9, 12),
            )
        # auto_now degerlerini elle esitle: ayni damga senaryosunu kurmak icin
        AINewsEntry.objects.all().update(updated_at=self.moment)
        self.kayitlar = list(AINewsEntry.objects.order_by('id'))

    def test_ayni_damgada_id_ayirt_eder(self):
        ilk = self.kayitlar[0]
        sonuc = apply_cursor(AINewsEntry.objects.all(), self.moment, ilk.id).order_by('id')
        self.assertEqual([k.id for k in sonuc], [self.kayitlar[1].id, self.kayitlar[2].id])

    def test_son_kayittan_sonra_bos_doner(self):
        son = self.kayitlar[-1]
        sonuc = apply_cursor(AINewsEntry.objects.all(), self.moment, son.id)
        self.assertEqual(list(sonuc), [])
