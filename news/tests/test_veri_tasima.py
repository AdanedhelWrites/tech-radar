"""news/veri_tasima.py ve veri_tasi_dump / veri_ozeti komutlari (Faz B1, spec 5.3).

Testler PostgreSQL'de kosar (CI ve scripts/pg_test.sh). Gidis-donus testi Task 4'te
eklenir: yazilan dosya standart loaddata ile yuklenince ozet birebir ayni kalmali.
"""
import io
import json
from datetime import date, datetime, timezone

from django.core.management import call_command
from django.core.serializers.json import DjangoJSONEncoder
from django.test import SimpleTestCase, TestCase

from news.models import CVEEntry, FetchRun
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
