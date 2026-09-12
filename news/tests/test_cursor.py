"""Imlec (cursor) tabanli delta cekme testleri."""
from datetime import date

from django.test import TestCase
from django.utils import timezone

from news.api_v1.cursor import InvalidCursor, apply_cursor, decode_cursor, encode_cursor
from news.models import AINewsEntry, CVEEntry
from news.tests.base import V1TestCase


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


from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


class DeltaAkisiTests(V1TestCase):
    """Delta akisi hicbir kaydi atlamamali ve tekrar etmemeli."""

    def setUp(self):
        super().setUp()
        kullanici = User.objects.create_user('delta-test', password='parola-yok-test')
        self.baslik = {'HTTP_AUTHORIZATION': f'Token {Token.objects.create(user=kullanici).key}'}
        for i in range(1, 8):
            AINewsEntry.objects.create(
                source='Test', original_title=f'Baslik {i}', original_description='X',
                link=f'https://ornek.test/delta/{i}', published_date=date(2026, 9, 12),
            )

    def _sayfala(self, limit):
        """Imleci takip ederek tum sayfalari gezer, gorulen id listesini dondurur."""
        gorulen, imlec = [], None
        for _ in range(20):  # sonsuz donguye karsi emniyet
            yol = f'/api/v1/ai/?limit={limit}'
            if imlec:
                yol += f'&since_cursor={imlec}'
            govde = self.client.get(yol, **self.baslik).json()
            gorulen += [k['id'] for k in govde['results']]
            imlec = govde['next_cursor']
            if not govde['has_more']:
                return gorulen
        self.fail('Sayfalama bitmedi')

    def test_tum_kayitlar_tam_bir_kez_gelir(self):
        gorulen = self._sayfala(limit=3)
        beklenen = list(AINewsEntry.objects.order_by('updated_at', 'id').values_list('id', flat=True))
        self.assertEqual(gorulen, beklenen)
        self.assertEqual(len(gorulen), len(set(gorulen)), 'Ayni kayit birden fazla geldi')

    def test_sayfalama_sirasinda_eklenen_kayit_atlanmaz(self):
        """Beat sayfalama ortasinda yazarsa yeni kayit akisin sonuna eklenir."""
        ilk = self.client.get('/api/v1/ai/?limit=3', **self.baslik).json()
        AINewsEntry.objects.create(
            source='Test', original_title='Sonradan', original_description='X',
            link='https://ornek.test/delta/sonradan', published_date=date(2026, 9, 12),
        )
        gorulen = [k['id'] for k in ilk['results']]
        imlec = ilk['next_cursor']
        while True:
            govde = self.client.get(f'/api/v1/ai/?limit=3&since_cursor={imlec}', **self.baslik).json()
            gorulen += [k['id'] for k in govde['results']]
            imlec = govde['next_cursor']
            if not govde['has_more']:
                break
        self.assertEqual(len(gorulen), 8)
        self.assertEqual(len(gorulen), len(set(gorulen)))

    def test_bos_sayfada_imlec_geri_doner(self):
        """Sonuc bos olsa bile tuketicinin saklayacak bir degeri olmali."""
        tumu = self.client.get('/api/v1/ai/?limit=100', **self.baslik).json()
        imlec = tumu['next_cursor']
        bos = self.client.get(f'/api/v1/ai/?since_cursor={imlec}', **self.baslik).json()
        self.assertEqual(bos['results'], [])
        self.assertFalse(bos['has_more'])
        self.assertEqual(bos['next_cursor'], imlec)

    def test_count_sayfadaki_kayit_sayisidir(self):
        govde = self.client.get('/api/v1/ai/?limit=3', **self.baslik).json()
        self.assertEqual(govde['count'], 3)
        self.assertEqual(len(govde['results']), 3)

    def test_bozuk_imlec_400_doner(self):
        yanit = self.client.get('/api/v1/ai/?since_cursor=bozuk!!', **self.baslik)
        self.assertEqual(yanit.status_code, 400)

    def test_since_ile_baslangic(self):
        from datetime import timedelta

        from django.utils import timezone
        yarin = (timezone.now() + timedelta(days=1)).date().isoformat()
        govde = self.client.get(f'/api/v1/ai/?since={yarin}', **self.baslik).json()
        self.assertEqual(govde['results'], [])

    def test_gecersiz_takvim_gunu_400_doner(self):
        """since deseni tutar ama takvimde olmayan bir gunu adlandirirsa parse_date ValueError firlatir."""
        yanit = self.client.get('/api/v1/ai/?since=2026-02-30', **self.baslik)
        self.assertEqual(yanit.status_code, 400)
        govde = yanit.json()
        self.assertEqual(govde['error']['code'], 'invalid_parameter')

    def test_since_cursor_since_parametresini_ezer(self):
        """Ikisi birden verilirse since_cursor kazanir (spec 4.1)."""
        from datetime import timedelta

        from django.utils import timezone
        tumu = self.client.get('/api/v1/ai/?limit=100', **self.baslik).json()
        imlec = tumu['next_cursor']
        dun = (timezone.now() - timedelta(days=1)).date().isoformat()
        govde = self.client.get(
            f'/api/v1/ai/?since_cursor={imlec}&since={dun}', **self.baslik).json()
        self.assertEqual(govde['results'], [],
                         'since_cursor yok sayilip since uygulanmis')

    def test_alti_bolum_de_yanit_verir(self):
        for bolum in ['news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai']:
            with self.subTest(bolum=bolum):
                yanit = self.client.get(f'/api/v1/{bolum}/', **self.baslik)
                self.assertEqual(yanit.status_code, 200)
                self.assertIn('next_cursor', yanit.json())
