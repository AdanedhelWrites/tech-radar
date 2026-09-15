"""Retranslate testleri (spec 9.3, A3 plani netlestirme 8-10, 14).

LibreTranslate ve Gemini sahte, Redis gercek (benzersiz onek), veritabani gercek.
Hicbir Celery isi kuyruga atilmaz; fonksiyon dogrudan cagrilir.
"""
import uuid
from datetime import date
from io import StringIO
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from news import gemini
from news import translation_providers as tp
from news import translation_utils as tu
from news.models import AINewsEntry, CVEEntry, KubernetesEntry, NewsArticle
from news.tests.base import LOCMEM_CACHE, test_redis_client
from news.tests.test_translation import FakeTranslator, TranslationGateMixin
from news.tests.saglayici_yardimcilari import SahteSaglayici, SaglayiciZinciriMixin


def _google(protected):
    return 'GOOGLE ' + protected


def _libre(protected):
    return 'LIBRE ' + protected

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


def _libre_kaydi(slug, baslik='Farmers adopt new sensors', govde='Sensors measure soil moisture every hour.'):
    return AINewsEntry.objects.create(
        source='MIT Tech Review AI', original_title=baslik, turkish_title='LIBRE ' + baslik,
        original_description=govde, turkish_description='LIBRE ' + govde,
        link=f'https://ornek.test/rt/{slug}', published_date=date(2026, 9, 12),
        needs_translation=False, translation_provider='libretranslate')


@override_settings(CACHES=LOCMEM_CACHE)
class RetranslateTestBase(TranslationGateMixin, TestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        self.redis = test_redis_client()
        self.prefix = f'test-retranslate-{uuid.uuid4().hex}'
        self.addCleanup(self._anahtarlari_sil)
        self.gemini_ayarla_varsayilan()

    def gemini_ayarla_varsayilan(self):
        """Gemini kapali: mevcut zincir testleri etkilenmez. Gemini testleri kendi ayarini yapar."""
        for hedef, deger in (('hazir', lambda: False), ('butce_var', lambda: True), ('kaydi_cevir', lambda alanlar: None)):
            yama = mock.patch.object(gemini, hedef, deger)
            yama.start()
            self.addCleanup(yama.stop)

    def _anahtarlari_sil(self):
        for anahtar in self.redis.scan_iter(f'{self.prefix}:*'):
            self.redis.delete(anahtar)

    def _calistir(self, batch=8, upgrade_batch=5):
        from news.retranslate import retranslate_pending
        return retranslate_pending(redis_client=self.redis, prefix=self.prefix,
                                   batch=batch, upgrade_batch=upgrade_batch)

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
        self.assertEqual(sonuc['sections']['ai'], {'translated': 1, 'failed': 0, 'upgraded': 0})
        self.assertEqual(sonuc['by_provider'], {'gemini': 0, 'libretranslate': 1})
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(len(cevirmen.calls), 2)

    def test_erisim_hatasinda_kayda_yazilmaz_ve_durur(self):
        # Sahte saglayici gercek LibreTranslateProvider'in devre kesicisini taklit eder:
        # ilk cagrida erisilemez olur ve bir daha hazir donmez.
        saglayici = SahteSaglayici('libretranslate')

        def erisilemez(protected):
            saglayici.hazir = False
            return None

        saglayici._cevap = erisilemez
        yama = mock.patch.object(tp, 'SAGLAYICILAR', (saglayici,))
        yama.start()
        self.addCleanup(yama.stop)

        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'erisim')
        once = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertTrue(kayit.needs_translation)
        self.assertEqual(kayit.updated_at, once, 'Basarisiz deneme delta akisina degismemis kayit dusurmemeli')
        self.assertTrue(sonuc['stopped'])
        self.assertEqual(sonuc['translated'], 0)
        self.assertFalse(self.redis.exists(f'{self.prefix}:cursor:ai'),
                         'Erisim hatasinda imlec ilerlememeli; kayit bir sonraki turda once denenmeli')

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
        self.assertFalse(tp._lt_gate.cooldown_active(), 'Yanki devre kesiciyi acmamali')

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
        self.assertFalse(sonuc['stopped'])

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


class RetranslateSaglayiciTests(SaglayiciZinciriMixin, RetranslateTestBase):
    """Spec 2026-09-15: bekleyenler Gemini-once, sonra zincir; yukseltme yalniz Gemini."""

    def test_varsayilan_sinirlar(self):
        from news import retranslate
        self.assertEqual(retranslate.RETRANSLATE_BATCH, 100)
        self.assertEqual(retranslate.RETRANSLATE_UPGRADE_BATCH, 40)

    def test_google_kapaliyken_libretranslate_ile_devam_eder(self):
        self.saglayicilari_ayarla(SahteSaglayici('google', _google, hazir=False),
                                  SahteSaglayici('libretranslate', _libre))
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'lt')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertFalse(kayit.needs_translation)
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(kayit.turkish_title, 'LIBRE Farmers adopt new sensors')
        self.assertFalse(sonuc['stopped'])
        self.assertEqual(sonuc['by_provider'], {'gemini': 0, 'libretranslate': 1})

    def test_hicbir_saglayici_yoksa_durur(self):
        google, libre = self.saglayicilari_ayarla(SahteSaglayici('google', _google, hazir=False),
                                                  SahteSaglayici('libretranslate', _libre, hazir=False))
        self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'yok')

        sonuc = self._calistir()

        self.assertTrue(sonuc['stopped'])
        self.assertEqual(google.cagrilar + libre.cagrilar, [])

    def test_karisik_bekleyen_kayit_libretranslate_sayilir(self):
        self.saglayicilari_ayarla(
            SahteSaglayici('google', {'Farmers adopt new sensors': 'Çiftçiler yeni sensörler benimsiyor'}),
            SahteSaglayici('libretranslate', _libre))
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'karisik')

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(kayit.turkish_title, 'Çiftçiler yeni sensörler benimsiyor')


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


class GeminiSahteMixin:
    """gemini modulunu ag erisimi olmadan taklit eder."""

    def gemini_ayarla(self, cevap=None, hazir=True, butce=True):
        """cevap: alanlar sozlugunu alan fonksiyon, sabit sozluk ya da None (cevrilemedi).
        hazir: sabit bool ya da parametresiz bir fonksiyon (cagri sirasinda degisebilir)."""
        self.gemini_cagrilar = []
        hazir_fn = hazir if callable(hazir) else (lambda: hazir)

        def kaydi_cevir(alanlar):
            self.gemini_cagrilar.append(dict(alanlar))
            return cevap(alanlar) if callable(cevap) else cevap

        for hedef, deger in (('hazir', lambda: hazir_fn() and butce), ('butce_var', lambda: butce),
                             ('kaydi_cevir', kaydi_cevir)):
            yama = mock.patch.object(gemini, hedef, deger)
            yama.start()
            self.addCleanup(yama.stop)


def _gemini_cevirisi(alanlar):
    return {ad: 'GEMINI ' + metin for ad, metin in alanlar.items()}


class RetranslateGeminiTests(GeminiSahteMixin, SaglayiciZinciriMixin, RetranslateTestBase):

    def setUp(self):
        super().setUp()
        self.libre = self.saglayicilari_ayarla(SahteSaglayici('libretranslate', _libre))[0]

    # --- Asama 1: bekleyenler ---

    def test_gemini_reddeder_zincir_kapali_icerik_hatasi_sayilir(self):
        self.libre.hazir = False
        self.gemini_ayarla(None)
        self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'ic1')
        self._ai('Story number 2 published', 'Body text for story 2.', 'ic2')

        sonuc = self._calistir()

        self.assertEqual(sonuc['failed'], 2)
        self.assertFalse(sonuc['stopped'])
        self.assertIsNone(sonuc['stopped_reason'])
        for kayit in AINewsEntry.objects.all():
            self.assertTrue(kayit.needs_translation)

    def test_gemini_reddi_diger_bolumlerin_yukseltmesini_engellemez(self):
        self.libre.hazir = False

        def cevap(alanlar):
            if 'Story number' in alanlar.get('title', ''):
                return None
            return _gemini_cevirisi(alanlar)

        self.gemini_ayarla(cevap)
        self._ai('Story number 1 published', 'Body text for story 1.', 'r1')
        kayit2 = _libre_kaydi('r2')

        sonuc = self._calistir()

        self.assertGreaterEqual(sonuc['failed'], 1)
        self.assertEqual(sonuc['upgraded'], 1)
        kayit2.refresh_from_db()
        self.assertEqual(kayit2.translation_provider, 'gemini')

    def test_bekleyen_once_gemini_ile_cevrilir(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'g1')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.turkish_title, 'GEMINI Farmers adopt new sensors')
        self.assertEqual(kayit.turkish_description, 'GEMINI Sensors measure soil moisture every hour.')
        self.assertEqual(kayit.translation_provider, 'gemini')
        self.assertFalse(kayit.needs_translation)
        self.assertEqual(sonuc['by_provider']['gemini'], 1)
        self.assertEqual(self.libre.cagrilar, [])
        self.assertEqual(self.gemini_cagrilar, [{'title': 'Farmers adopt new sensors',
                                                'description': 'Sensors measure soil moisture every hour.'}])

    def test_gemini_cevrilemezse_zincire_duser(self):
        self.gemini_ayarla(None)
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'g2')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertTrue(kayit.turkish_title.startswith('LIBRE'))
        self.assertEqual(sonuc['by_provider'], {'gemini': 0, 'libretranslate': 1})

    def test_gemini_hazir_degilse_asama_durmaz(self):
        self.gemini_ayarla(_gemini_cevirisi, hazir=False)
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'g3')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertFalse(sonuc['stopped'])
        self.assertIsNone(sonuc['stopped_reason'])

    def test_zincir_kapali_gemini_acik_bekleyen_cevrilir(self):
        self.libre.hazir = False
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'g4')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'gemini')
        self.assertFalse(sonuc['stopped'])

    def test_hicbiri_yoksa_durur_ve_sebep_yazilir(self):
        self.libre.hazir = False
        self.gemini_ayarla(None, hazir=False)
        self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'g5')

        sonuc = self._calistir()

        self.assertTrue(sonuc['stopped'])
        self.assertEqual(sonuc['stopped_reason'], 'no_provider')

    def test_cve_kisa_aciklama_gemini_adayi_degil(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = CVEEntry.objects.create(
            cve_id='CVE-2026-0001', source='NVD', original_title='CVE-2026-0001 - Guvenlik Acigi',
            turkish_title='CVE-2026-0001 - Guvenlik Acigi', original_description='Short text.',
            turkish_description='Short text.', link='https://ornek.test/cve/1',
            published_date=date(2026, 9, 12), severity='Orta', needs_translation=True)

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertEqual(kayit.turkish_description, 'Short text.')
        self.assertFalse(kayit.needs_translation)

    def test_cve_uzun_aciklama_yalniz_description_ile_gider(self):
        self.gemini_ayarla(_gemini_cevirisi)
        govde = 'A remote attacker can read arbitrary files from the server.'
        kayit = CVEEntry.objects.create(
            cve_id='CVE-2026-0002', source='NVD', original_title='CVE-2026-0002 - Guvenlik Acigi',
            turkish_title='CVE-2026-0002 - Guvenlik Acigi', original_description=govde,
            turkish_description=govde, link='https://ornek.test/cve/2',
            published_date=date(2026, 9, 12), severity='Yuksek', needs_translation=True)

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [{'description': govde}])
        self.assertEqual(kayit.turkish_title, 'CVE-2026-0002 - Guvenlik Acigi')
        self.assertEqual(kayit.turkish_description, 'GEMINI ' + govde)
        self.assertEqual(kayit.translation_provider, 'gemini')

    def test_kubernetes_yapisal_changelog_tek_alan_olarak_gider(self):
        self.gemini_ayarla(_gemini_cevirisi)
        govde = '===SECTION:Features===\n- Add new scheduler flag.\n===SECTION:Bug Fixes===\n- Fix kubelet crash.'
        kayit = KubernetesEntry.objects.create(
            source='GitHub Releases', category='release', version='v1.31.0',
            original_title='Kubernetes v1.31.0 released', turkish_title='Kubernetes v1.31.0 released',
            original_description=govde, turkish_description=govde, link='https://ornek.test/k8s/1',
            published_date=date(2026, 9, 12), needs_translation=True)

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [{'title': 'Kubernetes v1.31.0 released', 'description': govde}])
        self.assertEqual(kayit.turkish_description, 'GEMINI ' + govde)

    def test_cok_uzun_kayit_gemini_atlanir_zincire_duser(self):
        self.gemini_ayarla(_gemini_cevirisi)
        govde = 'A' * 13000
        kayit = self._ai('Farmers adopt new sensors', govde, 'uzun1')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertFalse(kayit.needs_translation)
        self.assertEqual(kayit.translation_provider, 'libretranslate')

    def test_cok_uzun_kayit_yukseltmede_atlanir(self):
        self.gemini_ayarla(_gemini_cevirisi)
        govde = 'B' * 13000
        kayit = _libre_kaydi('uzun2', govde=govde)
        eski = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(kayit.updated_at, eski)

    def test_haber_bos_orijinal_aciklama_gonderilmez(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = NewsArticle.objects.create(
            source='The Hacker News', original_title='Story number 1 published',
            turkish_title='Story number 1 published', original_description='',
            turkish_description='Mevcut Türkçe gövde.', link='https://ornek.test/haber/g1',
            date=date(2026, 9, 14), original_date='2026-09-14', needs_translation=True)

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [{'title': 'Story number 1 published'}])
        self.assertEqual(kayit.turkish_title, 'GEMINI Story number 1 published')
        self.assertEqual(kayit.turkish_description, 'Mevcut Türkçe gövde.')

    # --- Asama 2: yukseltme ---

    def test_transport_hatasinda_yukseltme_imleci_ilerlemez(self):
        durum = {'hazir': True}

        def cevap(alanlar):
            durum['hazir'] = False
            return None

        self.gemini_ayarla(cevap, hazir=lambda: durum['hazir'])
        kayit1 = _libre_kaydi('t1')
        kayit2 = _libre_kaydi('t2')

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 0)
        kayit1.refresh_from_db()
        kayit2.refresh_from_db()
        self.assertEqual(kayit1.translation_provider, 'libretranslate')
        self.assertEqual(kayit2.translation_provider, 'libretranslate')
        self.assertFalse(self.redis.exists(f'{self.prefix}:upgrade-cursor:ai'),
                         'Ilk kayitta durdu; imlec set edilmemis olmali')

    def test_libretranslate_kaydi_gemini_ile_yukseltilir(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _libre_kaydi('y1')
        eski = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'gemini')
        self.assertEqual(kayit.turkish_title, 'GEMINI Farmers adopt new sensors')
        self.assertEqual(kayit.turkish_description, 'GEMINI Sensors measure soil moisture every hour.')
        self.assertGreater(kayit.updated_at, eski)
        self.assertEqual(sonuc['upgraded'], 1)
        self.assertEqual(sonuc['sections']['ai']['upgraded'], 1)

    def test_gemini_cevrilemezse_yukseltme_yazilmaz(self):
        self.gemini_ayarla(None)
        kayit = _libre_kaydi('y2')
        eski = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(kayit.updated_at, eski)
        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(len(self.gemini_cagrilar), 1)

    def test_gemini_hazir_degilse_yukseltme_baslamaz(self):
        self.gemini_ayarla(_gemini_cevirisi, hazir=False)
        _libre_kaydi('y3')

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertIsNone(sonuc['stopped_reason'])

    def test_butce_bitince_yukseltme_durur_ve_sebep_yazilir(self):
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        _libre_kaydi('y4')

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 0)
        self.assertFalse(sonuc['stopped'])           # LibreTranslate zinciri hala calisir
        self.assertEqual(sonuc['stopped_reason'], 'gemini_budget')

    def test_butce_asama_ortasinda_bitince_imlec_ilerlemez(self):
        durum = {'kalan': 1}

        def cevap(alanlar):
            durum['kalan'] -= 1
            return _gemini_cevirisi(alanlar)

        self.gemini_ayarla(cevap)
        # hazir() ikinci kayittan once False'a dusmeli
        yama = mock.patch.object(gemini, 'hazir', lambda: durum['kalan'] > 0)
        yama.start()
        self.addCleanup(yama.stop)
        for i in range(3):
            _libre_kaydi(f'y5-{i}', baslik=f'Story number {i + 1} published')

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 1)
        self.assertEqual(AINewsEntry.objects.filter(translation_provider='libretranslate').count(), 2)
        # Imlec ilk kaydin arkasinda kaldi: bir sonraki tur ikinci kayittan devam eder
        self.assertTrue(self.redis.exists(f'{self.prefix}:upgrade-cursor:ai'))

    def test_yukseltme_bolum_siniri(self):
        self.gemini_ayarla(_gemini_cevirisi)
        for i in range(4):
            _libre_kaydi(f'y6-{i}', baslik=f'Story number {i + 1} published')

        sonuc = self._calistir(upgrade_batch=3)

        self.assertEqual(sonuc['upgraded'], 3)
        self.assertEqual(AINewsEntry.objects.filter(translation_provider='libretranslate').count(), 1)

    def test_kubernetes_isaretler_esitse_yazilir(self):
        self.gemini_ayarla(_gemini_cevirisi)
        govde = '===SECTION: Features===\n---ITEM---\nAdds a flag.\n<<<PR#123|@kisi|sig>>>'
        kayit = KubernetesEntry.objects.create(
            source='GitHub Releases', category='release', version='v1.33.0',
            original_title='Kubernetes v1.33.0 released', turkish_title='Kubernetes v1.33.0 released',
            original_description=govde, turkish_description=govde, link='https://ornek.test/k8s/isaret1',
            published_date=date(2026, 9, 12), needs_translation=True)

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'gemini')
        self.assertFalse(kayit.needs_translation)

    def test_kubernetes_isaret_kaybi_yukseltmede_yazilmaz(self):
        govde = ('===SECTION: Features===\n---ITEM---\nAdds a flag.\n<<<PR#123|@kisi|sig>>>\n'
                 '---ITEM---\nFix x.\n<<<PR#124|@kisi2|sig2>>>')

        def cevap(alanlar):
            sonuc = _gemini_cevirisi(alanlar)
            if 'description' in sonuc:
                sonuc['description'] = sonuc['description'].replace('<<<PR#124|@kisi2|sig2>>>', '', 1)
            return sonuc

        self.gemini_ayarla(cevap)
        kayit = KubernetesEntry.objects.create(
            source='GitHub Releases', category='release', version='v1.34.0',
            original_title='Kubernetes v1.34.0 released', turkish_title='GEMINI Kubernetes v1.34.0 released',
            original_description=govde, turkish_description='LIBRE ' + govde, link='https://ornek.test/k8s/isaret2',
            published_date=date(2026, 9, 12), needs_translation=False, translation_provider='libretranslate')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(kayit.translation_provider, 'libretranslate')

    def test_google_kayitlari_yukseltilmez(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _libre_kaydi('y7')
        kayit.translation_provider = 'google'
        kayit.save(update_fields=['translation_provider'])

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(self.gemini_cagrilar, [])
