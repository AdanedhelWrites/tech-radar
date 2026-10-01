"""news/veri_tasima.py ve veri_tasi_dump / veri_ozeti komutlari (Faz B1, spec 5.3).

Testler PostgreSQL'de kosar (CI ve scripts/pg_test.sh). Gidis-donus testi Task 4'te
eklenir: yazilan dosya standart loaddata ile yuklenince ozet birebir ayni kalmali.
"""
import io
import json
import os
import tempfile
from datetime import date, datetime, timezone

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.serializers.json import DjangoJSONEncoder
from django.test import SimpleTestCase, TestCase
from rest_framework.authtoken.models import Token

from news.models import CVEEntry, FetchRun, NewsArticle
from news.veri_tasima import TamHassasKodlayici, ozet, tasinacak_modeller

AN = datetime(2026, 9, 18, 12, 41, 6, 25667, tzinfo=timezone.utc)


def cve_olustur(cve_id='CVE-2026-0001', aciklama='Satir bir\r\n \r\nSatir iki '):
    return CVEEntry.objects.create(
        cve_id=cve_id, source='NVD', original_title=f'{cve_id} - ornek',
        original_description=aciklama, published_date=date(2026, 9, 18),
        link=f'https://nvd.example/{cve_id}', cwe_ids=['CWE-79'],
        references=['https://a.example', 'https://b.example'])


class KodlayiciTests(SimpleTestCase):

    def test_mikrosaniye_korunur(self):
        self.assertEqual(json.dumps(AN, cls=TamHassasKodlayici),
                         '"2026-09-18T12:41:06.025667+00:00"')

    def test_django_kodlayicisi_kirpar(self):
        """Ayri kodlayicinin nedeni: Django'nunki milisaniyeye kirpar (spec 2.3)."""
        self.assertEqual(json.dumps(AN, cls=DjangoJSONEncoder), '"2026-09-18T12:41:06.025Z"')


class ModelKumesiTests(SimpleTestCase):

    def test_haric_ve_proxy_modeller_yok(self):
        etiketler = {m._meta.label_lower for m in tasinacak_modeller()}
        for haric in ('contenttypes.contenttype', 'auth.permission', 'sessions.session',
                      'admin.logentry', 'authtoken.tokenproxy'):
            self.assertNotIn(haric, etiketler)
        for gerekli in ('auth.user', 'authtoken.token', 'news.cveentry', 'news.fetchrun',
                        'news.newsarticle', 'news.ainewsentry'):
            self.assertIn(gerekli, etiketler)

    def test_bagimlilik_sirasi(self):
        sira = [m._meta.label_lower for m in tasinacak_modeller()]
        self.assertLess(sira.index('auth.user'), sira.index('authtoken.token'))


class OzetTests(TestCase):

    def setUp(self):
        self.cve = cve_olustur()
        self.run = FetchRun.objects.create(section='cve', status='success',
                                           by_provider={'a': 1, 'b': 2})

    def _delta(self, etiket):
        return {e: d for e, _, _, d in ozet()}[etiket]

    def test_ayni_veride_ayni_ozet(self):
        self.assertEqual(ozet(), ozet())

    def test_metin_degisikligini_yakalar(self):
        once = ozet()
        CVEEntry.objects.filter(pk=self.cve.pk).update(original_description='degisti')
        self.assertNotEqual(ozet(), once)

    def test_mikrosaniye_degisikligini_delta_ozetinde_yakalar(self):
        CVEEntry.objects.filter(pk=self.cve.pk).update(updated_at=AN)
        once = self._delta('news.CVEEntry')
        CVEEntry.objects.filter(pk=self.cve.pk).update(updated_at=AN.replace(microsecond=25000))
        self.assertNotEqual(self._delta('news.CVEEntry'), once)

    def test_json_anahtar_sirasina_duyarsiz(self):
        """PostgreSQL jsonb nesne anahtar sirasini korumaz; ozet bunu fark saymamali."""
        once = ozet()
        FetchRun.objects.filter(pk=self.run.pk).update(by_provider={'b': 2, 'a': 1})
        self.assertEqual(ozet(), once)

    def test_updated_at_olmayan_modelde_delta_tire(self):
        self.assertEqual(self._delta('news.FetchRun'), '-')
        self.assertNotEqual(self._delta('news.CVEEntry'), '-')

    def test_komut_cikti_bicimi(self):
        cikti = io.StringIO()
        call_command('veri_ozeti', stdout=cikti)
        satirlar = cikti.getvalue().strip().splitlines()
        self.assertEqual(len(satirlar), len(tasinacak_modeller()))
        for satir in satirlar:
            self.assertEqual(len(satir.split(' ')), 4, satir)
        self.assertIn('news.CVEEntry 1 ', cikti.getvalue())


class GidisDonusTests(TestCase):
    """dump -> tabloyu bosalt -> loaddata: ozet birebir ayni (spec 2.4)."""

    def setUp(self):
        kullanici = get_user_model().objects.create_user('tasima')
        Token.objects.create(user=kullanici)
        NewsArticle.objects.create(
            source='Ornek', original_title='Baslik ', turkish_title='Baslik',
            link='https://ornek.com/haber-1', date=date(2026, 9, 18), original_date='18 Sep 2026')
        cve = cve_olustur()
        CVEEntry.objects.filter(pk=cve.pk).update(updated_at=AN)
        FetchRun.objects.create(section='cve', status='success',
                                by_provider={'libretranslate': 2, 'gemini': 1})

    def _dump(self):
        yol = os.path.join(tempfile.mkdtemp(), 'dump.json')
        call_command('veri_tasi_dump', yol, stderr=io.StringIO())
        return yol

    def _hepsini_sil(self):
        for model in reversed(tasinacak_modeller()):
            model._default_manager.all().delete()

    def test_gidis_donus_ozet_birebir(self):
        once = ozet()
        yol = self._dump()
        self._hepsini_sil()
        self.assertEqual(CVEEntry.objects.count(), 0)
        call_command('loaddata', yol, verbosity=0)
        self.assertEqual(ozet(), once)

    def test_metin_ve_mikrosaniye_aynen_doner(self):
        yol = self._dump()
        with open(yol, encoding='utf-8') as dosya:
            self.assertIn('2026-09-18T12:41:06.025667+00:00', dosya.read())
        self._hepsini_sil()
        call_command('loaddata', yol, verbosity=0)
        cve = CVEEntry.objects.get(cve_id='CVE-2026-0001')
        self.assertEqual(cve.original_description, 'Satir bir\r\n \r\nSatir iki ')
        self.assertEqual(cve.updated_at, AN)
        self.assertEqual(cve.cwe_ids, ['CWE-79'])
        self.assertEqual(NewsArticle.objects.get().original_title, 'Baslik ')

    def test_kullanici_pk_ve_token_korunur(self):
        kullanici = get_user_model().objects.get(username='tasima')
        pk, anahtar = kullanici.pk, Token.objects.get(user=kullanici).key
        yol = self._dump()
        self._hepsini_sil()
        call_command('loaddata', yol, verbosity=0)
        self.assertEqual(get_user_model().objects.get(username='tasima').pk, pk)
        self.assertEqual(Token.objects.get(user__username='tasima').key, anahtar)

    def test_komut_sayilari_stderr_e_yazar(self):
        hata = io.StringIO()
        yol = os.path.join(tempfile.mkdtemp(), 'alt', 'dump.json')
        call_command('veri_tasi_dump', yol, stderr=hata)
        self.assertTrue(os.path.exists(yol))
        self.assertIn('news.CVEEntry 1', hata.getvalue())
        self.assertIn('toplam ', hata.getvalue())
