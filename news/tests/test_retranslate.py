"""Retranslate testleri (spec 9.3, A3 plani netlestirme 8-10, 14).

Google sahte, Redis gercek (benzersiz onek), veritabani gercek. Hicbir Celery
isi kuyruga atilmaz; fonksiyon dogrudan cagrilir.
"""
import uuid
from datetime import date
from io import StringIO
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from news import translation_utils as tu
from news.models import AINewsEntry, CVEEntry, KubernetesEntry
from news.tests.base import LOCMEM_CACHE, test_redis_client
from news.tests.test_translation import FakeTranslator, TranslationGateMixin

CEVIRILER = {
    'Farmers adopt new sensors': 'Çiftçiler yeni sensörler benimsiyor',
    'Sensors measure soil moisture every hour.': 'Sensörler toprak nemini her saat ölçüyor.',
    'A remote attacker can read arbitrary files from the server.':
        'Uzaktaki bir saldırgan sunucudaki rastgele dosyaları okuyabilir.',
}
for _i in range(1, 6):
    CEVIRILER[f'Story number {_i} published'] = f'{_i} numaralı haber yayımlandı'
    CEVIRILER[f'Body text for story {_i}.'] = f'{_i}. haberin gövde metni.'

# Hep yanki donen (dogrulamadan gecemeyen) kayit
TAKILAN_BASLIK = 'Robots learn to sort laundry today'
TAKILAN_GOVDE = 'The team trained robots for many months.'


@override_settings(CACHES=LOCMEM_CACHE)
class RetranslateTestBase(TranslationGateMixin, TestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        self.redis = test_redis_client()
        self.prefix = f'test-retranslate-{uuid.uuid4().hex}'
        self.addCleanup(self._anahtarlari_sil)

    def _anahtarlari_sil(self):
        for anahtar in self.redis.scan_iter(f'{self.prefix}:*'):
            self.redis.delete(anahtar)

    def _calistir(self, batch=8):
        from news.retranslate import retranslate_pending
        return retranslate_pending(redis_client=self.redis, prefix=self.prefix, batch=batch)

    def _ai(self, baslik, govde, slug):
        return AINewsEntry.objects.create(
            source='MIT Tech Review AI', original_title=baslik, turkish_title=baslik,
            original_description=govde, turkish_description=govde,
            link=f'https://ornek.test/rt/{slug}', published_date=date(2026, 9, 12),
            needs_translation=True)


class RetranslatePendingTests(RetranslateTestBase):

    def test_bekleyen_kayit_feede_bakmadan_cevrilir(self):
        cevirmen = self.use_translator(FakeTranslator(CEVIRILER))
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'ciftci')
        once = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertFalse(kayit.needs_translation)
        self.assertEqual(kayit.turkish_title, 'Çiftçiler yeni sensörler benimsiyor')
        self.assertEqual(kayit.turkish_description, 'Sensörler toprak nemini her saat ölçüyor.')
        self.assertGreater(kayit.updated_at, once, 'Basarida updated_at ilerlemeli: delta akisina dusmeli')
        self.assertEqual(sonuc['translated'], 1)
        self.assertEqual(sonuc['sections']['ai'], {'translated': 1, 'failed': 0})
        self.assertEqual(len(cevirmen.calls), 2)

    def test_erisim_hatasinda_kayda_yazilmaz_ve_durur(self):
        self.use_translator(FakeTranslator())  # hata sayfasi -> devre kesici acilir
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'erisim')
        once = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertTrue(kayit.needs_translation)
        self.assertEqual(kayit.updated_at, once, 'Basarisiz deneme delta akisina degismemis kayit dusurmemeli')
        self.assertTrue(sonuc['stopped_by_cooldown'])
        self.assertEqual(sonuc['translated'], 0)
        self.assertFalse(self.redis.exists(f'{self.prefix}:cursor:ai'),
                         'Erisim hatasinda imlec ilerlememeli; kayit bir sonraki turda once denenmeli')

    def test_devre_kesici_acikken_googlea_gidilmez(self):
        cevirmen = self.use_translator(FakeTranslator(CEVIRILER))
        self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'kesici')
        tu._gate.start_cooldown(60)

        sonuc = self._calistir()

        self.assertEqual(cevirmen.calls, [])
        self.assertTrue(sonuc['stopped_by_cooldown'])

    def test_bolum_basina_batch_siniri(self):
        self.use_translator(FakeTranslator(CEVIRILER))
        for i in range(1, 6):
            self._ai(f'Story number {i} published', f'Body text for story {i}.', f'batch-{i}')

        sonuc = self._calistir(batch=2)

        self.assertEqual(sonuc['translated'], 2)
        self.assertEqual(AINewsEntry.objects.filter(needs_translation=True).count(), 3)

    def test_hep_basarisiz_kayit_kuyrugu_tikamaz(self):
        """En-eski-once siralamada takilan kayit her turda ayni yeri isgal ederdi."""
        cevirmen = self.use_translator(FakeTranslator({
            **CEVIRILER, TAKILAN_BASLIK: TAKILAN_BASLIK, TAKILAN_GOVDE: TAKILAN_GOVDE}))
        takilan = self._ai(TAKILAN_BASLIK, TAKILAN_GOVDE, 'takilan')
        birinci = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'birinci')
        ikinci = self._ai('Story number 2 published', 'Body text for story 2.', 'ikinci')

        for _ in range(3):
            self._calistir(batch=1)

        for kayit in (takilan, birinci, ikinci):
            kayit.refresh_from_db()
        self.assertTrue(takilan.needs_translation)
        self.assertFalse(birinci.needs_translation)
        self.assertFalse(ikinci.needs_translation)
        self.assertFalse(tu._gate.cooldown_active(), 'Yanki devre kesiciyi acmamali')

    def test_sona_gelince_imlec_silinir_ve_bastan_baslar(self):
        cevirmen = self.use_translator(FakeTranslator({
            TAKILAN_BASLIK: TAKILAN_BASLIK, TAKILAN_GOVDE: TAKILAN_GOVDE}))
        self._ai(TAKILAN_BASLIK, TAKILAN_GOVDE, 'tek')

        self._calistir(batch=1)                     # takilan denendi, imlec onun uzerinde
        self.assertTrue(self.redis.exists(f'{self.prefix}:cursor:ai'))
        self._calistir(batch=1)                     # imlecten sonra kayit yok -> imlec silinir
        self.assertFalse(self.redis.exists(f'{self.prefix}:cursor:ai'))
        cagri_sayisi = len(cevirmen.calls)
        self._calistir(batch=1)                     # bastan: takilan tekrar denenir
        self.assertGreater(len(cevirmen.calls), cagri_sayisi)

    def test_bozuk_imlec_yok_sayilip_bastan_baslanir(self):
        self.use_translator(FakeTranslator(CEVIRILER))
        self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'bozuk-imlec')
        self.redis.set(f'{self.prefix}:cursor:ai', 'bozuk!!')

        sonuc = self._calistir()

        self.assertEqual(sonuc['translated'], 1)

    def test_basarida_liste_cache_yenilenir(self):
        self.use_translator(FakeTranslator(CEVIRILER))
        self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'cache')

        self._calistir()

        self.assertEqual(cache.get('ai_entries')[0]['turkish_title'], 'Çiftçiler yeni sensörler benimsiyor')

    def test_bekleyen_kayit_yoksa_googlea_gidilmez(self):
        cevirmen = self.use_translator(FakeTranslator(CEVIRILER))
        sonuc = self._calistir()
        self.assertEqual(cevirmen.calls, [])
        self.assertEqual(sonuc['translated'], 0)
        self.assertFalse(sonuc['stopped_by_cooldown'])

    def test_cve_basligi_cevrilmez_kisa_olmayan_aciklama_cevrilir(self):
        """cve_scraper.process_cves ile ayni kural."""
        cevirmen = self.use_translator(FakeTranslator(CEVIRILER))
        cve = CVEEntry.objects.create(
            cve_id='CVE-2026-5000', source='NVD', original_title='CVE-2026-5000 - Guvenlik Acigi',
            original_description='A remote attacker can read arbitrary files from the server.',
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/5000', needs_translation=True)

        self._calistir()

        cve.refresh_from_db()
        self.assertFalse(cve.needs_translation)
        self.assertEqual(cve.turkish_title, 'CVE-2026-5000 - Guvenlik Acigi')
        self.assertEqual(cve.turkish_description, 'Uzaktaki bir saldırgan sunucudaki rastgele dosyaları okuyabilir.')
        self.assertEqual(len(cevirmen.calls), 1)

    def test_kubernetes_yapisal_changelog_ozel_yoldan_cevrilir(self):
        """k8s_scraper.process_entries ile ayni ayrim."""
        baslik = 'Kubernetes v1.32 released'
        korunmus_baslik, _ = tu._protect_terms(baslik)
        self.use_translator(FakeTranslator({korunmus_baslik: korunmus_baslik.replace('released', 'yayımlandı')}))
        k8s = KubernetesEntry.objects.create(
            source='GitHub Releases', original_title=baslik,
            original_description='===SECTION: Feature\n---ITEM---\nAdds a flag.',
            link='https://ornek.test/k8s/132', published_date=date(2026, 9, 12),
            category='release', needs_translation=True)

        from news.k8s_scraper import MultiK8sScraper
        with mock.patch.object(MultiK8sScraper, '_translate_structured_changelog',
                               return_value='YAPISAL CEVIRI') as yapisal:
            self._calistir()

        k8s.refresh_from_db()
        yapisal.assert_called_once()
        self.assertEqual(k8s.turkish_description, 'YAPISAL CEVIRI')
        self.assertEqual(k8s.turkish_title, 'Kubernetes v1.32 yayımlandı')
        self.assertFalse(k8s.needs_translation)


class RetranslateGoreviTests(SimpleTestCase):

    def test_gorev_retranslate_pending_cagirir(self):
        from news import tasks
        with mock.patch('news.retranslate.retranslate_pending',
                        return_value={'translated': 3}) as sahte:
            self.assertEqual(tasks.retranslate_pending_task(), {'translated': 3})
        sahte.assert_called_once_with()

    def test_beat_takvimi_tek_saatlerde_bes_gece(self):
        giris = settings.CELERY_BEAT_SCHEDULE['retranslate-pending-every-2h']
        self.assertEqual(giris['task'], 'news.tasks.retranslate_pending_task')
        self.assertEqual(giris['schedule'].minute, {5})
        self.assertEqual(giris['schedule'].hour, set(range(1, 24, 2)))

    def test_cekim_saatleriyle_cakismaz(self):
        """Fetch task'lari 00/06/12/18'de calisir; retranslate o saatlere dusmemeli."""
        cekim_saatleri = set()
        for giris in settings.CELERY_BEAT_SCHEDULE.values():
            if giris['task'].startswith('news.tasks.fetch_'):
                cekim_saatleri |= giris['schedule'].hour
        self.assertEqual(cekim_saatleri, {0, 6, 12, 18})
        retranslate_saatleri = settings.CELERY_BEAT_SCHEDULE['retranslate-pending-every-2h']['schedule'].hour
        self.assertEqual(cekim_saatleri & retranslate_saatleri, set())


class BozukCevirileriIsaretleTests(TestCase):

    def setUp(self):
        self.bozuk = CVEEntry.objects.create(
            cve_id='CVE-2026-7001', source='NVD', original_title='CVE-2026-7001',
            original_description='Uses `secret()` in code.', turkish_description='XTRM0021X kullanır.',
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/7001')
        self.bosluklu = AINewsEntry.objects.create(
            source='Test', original_title='T', turkish_title='xtrm 0003x modeli',
            original_description='D', turkish_description='Gövde',
            link='https://ornek.test/ai/7002', published_date=date(2026, 9, 12))
        self.temiz = CVEEntry.objects.create(
            cve_id='CVE-2026-7003', source='NVD', original_title='CVE-2026-7003',
            original_description='Clean.', turkish_description='Temiz çeviri.',
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/7003')
        self.zaten_bekleyen = CVEEntry.objects.create(
            cve_id='CVE-2026-7004', source='NVD', original_title='CVE-2026-7004',
            original_description='Pending.', turkish_description='XTRM0001X bekliyor.',
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/7004', needs_translation=True)

    def _komut(self, *args):
        cikti = StringIO()
        call_command('bozuk_cevirileri_isaretle', *args, stdout=cikti)
        return cikti.getvalue()

    def test_varsayilan_yalnizca_raporlar(self):
        cikti = self._komut()
        self.assertIn('TOPLAM: 2', cikti)
        self.bozuk.refresh_from_db()
        self.assertFalse(self.bozuk.needs_translation)

    def test_uygula_yalnizca_bozuklari_isaretler(self):
        once = CVEEntry.objects.get(pk=self.bozuk.pk).updated_at

        cikti = self._komut('--uygula')

        self.assertIn('TOPLAM: 2', cikti)
        for kayit in (self.bozuk, self.bosluklu, self.temiz):
            kayit.refresh_from_db()
        self.assertTrue(self.bozuk.needs_translation)
        self.assertTrue(self.bosluklu.needs_translation, 'Bosluklu/kucuk harfli kalinti da bozuktur')
        self.assertFalse(self.temiz.needs_translation)
        self.assertEqual(self.bozuk.updated_at, once,
                         'Isaretleme updated_at ilerletmemeli; duzgun ceviri yazilinca ilerleyecek')

    def test_ikinci_calistirmada_bulunacak_bir_sey_kalmaz(self):
        self._komut('--uygula')
        self.assertIn('TOPLAM: 0', self._komut())
