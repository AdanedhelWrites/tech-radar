"""Ikinci analiz maddeleri (2026-10-09): takili FetchRun, ceviri deneme sayaci, status alani.

Ayrica entrypoint/nginx/HTML-kacis gibi dosya duzeyindeki sozlesmeler (kaynak metin kontrolleri).
"""
from pathlib import Path

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from news import fetch_runs, retranslate
from news.models import AINewsEntry, FetchRun
from news.tests.base import V1TestCase
from news.tests.test_retranslate import (
    CEVIRILER, TAKILAN_BASLIK, TAKILAN_GOVDE, RetranslateTestBase,
)
from news.tests.test_translation import FakeTranslator

KOK = Path(__file__).resolve().parents[2]


class _Sender:
    def __init__(self, ad):
        self.name = ad
        self.request = {}


class TakiliTurKapatmaTests(TestCase):

    def test_yeni_tur_ayni_bolumun_takili_running_satirini_kapatir(self):
        eski = FetchRun.objects.create(section='devtools', trigger='beat', status='running')
        baska = FetchRun.objects.create(section='cve', trigger='beat', status='running')
        bitmis = FetchRun.objects.create(section='devtools', trigger='beat', status='success',
                                         finished_at=timezone.now())

        fetch_runs.tur_basladi(sender=_Sender('news.tasks.fetch_devtools_task'), task_id='y1')

        for kayit in (eski, baska, bitmis):
            kayit.refresh_from_db()
        self.assertEqual(eski.status, 'failure')
        self.assertEqual(eski.stopped_reason, 'interrupted')
        self.assertIsNotNone(eski.finished_at)
        self.assertIn('kapanmadan kesildi', eski.error)
        self.assertEqual(baska.status, 'running', 'baska bolumun satiri kapatilmamali')
        self.assertEqual(bitmis.status, 'success')
        yeni = FetchRun.objects.filter(section='devtools', status='running')
        self.assertEqual(yeni.count(), 1)
        self.assertNotEqual(yeni.get().pk, eski.pk)

    def test_takili_satir_yoksa_hicbir_sey_degismez(self):
        fetch_runs.tur_basladi(sender=_Sender('news.tasks.fetch_news_task'), task_id='y2')
        self.assertEqual(FetchRun.objects.filter(stopped_reason='interrupted').count(), 0)
        self.assertEqual(FetchRun.objects.filter(status='running').count(), 1)


class CevirmeDenemeSayaciTests(RetranslateTestBase):

    def _takilan(self):
        return self._ai(TAKILAN_BASLIK, TAKILAN_GOVDE, 'takilan')

    def test_icerik_hatasi_sayaci_artirir_updated_at_ilerlemez(self):
        self.use_translator(FakeTranslator({TAKILAN_BASLIK: TAKILAN_BASLIK, TAKILAN_GOVDE: TAKILAN_GOVDE}))
        kayit = self._takilan()
        once = kayit.updated_at

        self._calistir(batch=1)

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_attempts, 1)
        self.assertTrue(kayit.needs_translation)
        self.assertEqual(kayit.updated_at, once, 'sayac delta akisina (updated_at) girmemeli')

    def test_esige_ulasan_kayit_kuyruktan_duser(self):
        cevirmen = self.use_translator(FakeTranslator({TAKILAN_BASLIK: TAKILAN_BASLIK, TAKILAN_GOVDE: TAKILAN_GOVDE}))
        kayit = self._takilan()
        AINewsEntry.objects.filter(pk=kayit.pk).update(translation_attempts=retranslate.RETRANSLATE_MAX_ATTEMPTS)

        sonuc = self._calistir(batch=5)

        self.assertEqual(cevirmen.calls, [], 'esige ulasan kayit yeniden denenmemeli')
        self.assertEqual(sonuc['failed'], 0)
        kayit.refresh_from_db()
        self.assertTrue(kayit.needs_translation)
        self.assertEqual(kayit.translation_attempts, retranslate.RETRANSLATE_MAX_ATTEMPTS)

    def test_esige_kadar_her_turda_denenir(self):
        self.use_translator(FakeTranslator({TAKILAN_BASLIK: TAKILAN_BASLIK, TAKILAN_GOVDE: TAKILAN_GOVDE}))
        kayit = self._takilan()

        for _ in range(retranslate.RETRANSLATE_MAX_ATTEMPTS + 2):
            self.redis.delete(f'{self.prefix}:cursor:ai')
            self._calistir(batch=5)

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_attempts, retranslate.RETRANSLATE_MAX_ATTEMPTS)

    def test_basarida_sayac_sifirlanir(self):
        self.use_translator(FakeTranslator(CEVIRILER))
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'ciftci')
        AINewsEntry.objects.filter(pk=kayit.pk).update(translation_attempts=3)

        self._calistir(batch=5)

        kayit.refresh_from_db()
        self.assertFalse(kayit.needs_translation)
        self.assertEqual(kayit.translation_attempts, 0)


class StatusVazgecilenAlaniTests(V1TestCase):

    def test_translation_given_up_esigi_asan_bekleyenleri_sayar(self):
        for i, deneme in enumerate((0, retranslate.RETRANSLATE_MAX_ATTEMPTS - 1,
                                    retranslate.RETRANSLATE_MAX_ATTEMPTS, retranslate.RETRANSLATE_MAX_ATTEMPTS + 2)):
            AINewsEntry.objects.create(
                source='MIT Tech Review AI', original_title=f't{i}', turkish_title=f't{i}',
                original_description='d', link=f'https://ornek.test/g/{i}',
                published_date=timezone.now().date(), needs_translation=True, translation_attempts=deneme)
        # esigi asmis ama artik cevrilmis kayit sayilmaz
        AINewsEntry.objects.create(
            source='MIT Tech Review AI', original_title='ok', turkish_title='ok',
            original_description='d', link='https://ornek.test/g/ok',
            published_date=timezone.now().date(), needs_translation=False,
            translation_attempts=retranslate.RETRANSLATE_MAX_ATTEMPTS)

        ai = self.client.get('/api/v1/status/', **self.token_basligi()).json()['sections']['ai']

        self.assertEqual(ai['pending_translation'], 4)
        self.assertEqual(ai['translation_given_up'], 2)

    def test_sema_alani_tasir(self):
        from news.tests.test_schema import sema_uret
        alanlar = sema_uret()['components']['schemas']['BolumDurumuV1']['properties']
        self.assertIn('translation_given_up', alanlar)


class DosyaSozlesmeleriTests(SimpleTestCase):
    """Konfig/kaynak metni duzeyinde regresyonlar (docker/nginx calistirilmadan)."""

    def test_entrypoint_migrate_sessiz_gecmez(self):
        metin = (KOK / 'entrypoint.sh').read_text(encoding='utf-8')
        for satir in metin.splitlines():
            if 'manage.py migrate' in satir or 'manage.py collectstatic' in satir:
                if satir.strip().startswith('#'):
                    continue
                self.assertNotIn('|| true', satir, f'sessiz gecis geri geldi: {satir.strip()}')
        self.assertIn('set -e', metin)

    def test_nginx_guvenlik_basliklari_spa_ve_statiklerde(self):
        conf = (KOK / 'frontend/nginx.conf').read_text(encoding='utf-8')
        snippet = (KOK / 'frontend/guvenlik_basliklari.conf').read_text(encoding='utf-8')
        self.assertIn('server_tokens off', conf)
        self.assertEqual(conf.count('include /etc/nginx/snippets/guvenlik_basliklari.conf;'), 2)
        for baslik in ('X-Content-Type-Options', 'X-Frame-Options', 'Content-Security-Policy',
                       'Referrer-Policy', 'Permissions-Policy'):
            self.assertIn(baslik, snippet)
        self.assertIn("script-src 'self'", snippet)
        self.assertNotIn("script-src 'self' 'unsafe-inline'", snippet)
        self.assertIn('guvenlik_basliklari.conf', (KOK / 'frontend/Dockerfile').read_text(encoding='utf-8'))

    def test_html_export_sablonlarinda_ham_interpolasyon_yok(self):
        """Rapor sablonundaki her item.* degeri kacis()/guvenliHref() icinden gecmeli."""
        import re
        ham = re.compile(r'\$\{(?!kacis\(|guvenliHref\(|severityColor\(|ceviriEtiketiHtml\()[^}]*\bitem\.')
        for dosya in sorted((KOK / 'frontend/src/components').glob('*Component.jsx')):
            with self.subTest(dosya=dosya.name):
                metin = dosya.read_text(encoding='utf-8')
                if '<!DOCTYPE html>' not in metin:
                    continue
                sablon = metin.split('<!DOCTYPE html>', 1)[1].split('</html>', 1)[0]
                bulunan = [s.strip() for s in sablon.splitlines() if ham.search(s) and 'kacis(' not in s]
                self.assertEqual(bulunan, [], f'kacissiz item interpolasyonu: {bulunan}')
                self.assertIn("from '../utils/html'", metin)
