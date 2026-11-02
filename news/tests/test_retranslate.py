"""Retranslate testleri (spec 9.3, A3 plani netlestirme 8-10, 14).

LibreTranslate ve Gemini sahte, Redis gercek (benzersiz onek), veritabani gercek.
Hicbir Celery isi kuyruga atilmaz; fonksiyon dogrudan cagrilir.
"""
import uuid
from datetime import date, datetime, timedelta
from io import StringIO
from unittest import mock

from celery.schedules import crontab
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings

from news import gemini
from news import translation_providers as tp
from news import translation_utils as tu
from news.models import AINewsEntry, CVEEntry, KubernetesEntry, NewsArticle
from news.tests.base import LOCMEM_CACHE, RetranslateKilitMixin, test_redis_client
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
        # _butce: tur payi (G4) gunluk sayaci okur; her test bos bir surec ici sayacla baslar.
        for hedef, deger in (('hazir', lambda: False), ('butce_var', lambda: True),
                             ('kaydi_cevir', lambda alanlar, bolum=None: None),
                             ('paket_cevir', lambda kayitlar, bolum=None: gemini.PaketSonucu(istek_hatasi=True)),
                             ('_butce', gemini._LocalButce())):
            yama = mock.patch.object(gemini, hedef, deger)
            yama.start()
            self.addCleanup(yama.stop)

    def _anahtarlari_sil(self):
        for anahtar in self.redis.scan_iter(f'{self.prefix}:*'):
            self.redis.delete(anahtar)

    def _calistir(self, batch=8, upgrade_batch=5, tur=None):
        from news.retranslate import retranslate_pending
        return retranslate_pending(redis_client=self.redis, prefix=self.prefix,
                                   batch=batch, upgrade_batch=upgrade_batch, tur=tur)

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
        self.use_translator(FakeTranslator({
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


class ZehirliKayitTests(RetranslateTestBase):
    """2026-10-16: 102k karakterlik bir haber her turda LibreTranslate'i zaman asimina dusurup devre
    kesiciyi aciyordu; erisim sorunu sayildigi icin deneme sayaci artmiyor, imlec ilerlemiyordu ve
    retranslate 3 gun ayni kayitta takili kaldi (haberden sonraki bolumlere hic ulasilmadi)."""

    def _devre_kesen_saglayici(self, zehirli_metin):
        """Zehirli metinde devre kesiciyi acar (gercek LibreTranslate ReadTimeout'u gibi); digerlerini cevirir."""
        saglayici = SahteSaglayici('libretranslate')

        def cevap(protected):
            if zehirli_metin in protected:
                saglayici.hazir = False
                return None
            return 'LIBRE ' + protected

        saglayici._cevap = cevap
        yama = mock.patch.object(tp, 'SAGLAYICILAR', (saglayici,))
        yama.start()
        self.addCleanup(yama.stop)
        return saglayici

    def test_devre_kesiciyi_acan_kayit_deneme_sayar(self):
        self._devre_kesen_saglayici('Poison body')
        zehirli = self._ai('Poison headline for the queue', 'Poison body ' * 5, 'zehir-1')

        sonuc = self._calistir()

        zehirli.refresh_from_db()
        self.assertTrue(sonuc['stopped'])
        self.assertTrue(zehirli.needs_translation)
        self.assertEqual(zehirli.translation_attempts, 1,
                         'Devre kesiciyi acan kayit sayac artirmali; yoksa kuyrugu sonsuza dek kilitler')

    def test_zehirli_kayit_esikten_sonra_kuyrugu_birakir(self):
        from news.retranslate import RETRANSLATE_MAX_ATTEMPTS
        saglayici = self._devre_kesen_saglayici('Poison body')
        zehirli = self._ai('Poison headline for the queue', 'Poison body ' * 5, 'zehir-2')
        sonraki = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'zehir-2b')

        for _ in range(RETRANSLATE_MAX_ATTEMPTS + 1):
            saglayici.hazir = True  # devre kesicinin suresi turlar arasinda dolar (60 sn < 2 sa)
            self._calistir()

        zehirli.refresh_from_db()
        sonraki.refresh_from_db()
        self.assertEqual(zehirli.translation_attempts, RETRANSLATE_MAX_ATTEMPTS)
        self.assertFalse(sonraki.needs_translation, 'Zehirli kayit esige ulasinca siradaki kayit cevrilmeli')
        self.assertEqual(sonraki.turkish_title, 'LIBRE Farmers adopt new sensors')


class SureButcesiTests(RetranslateTestBase):
    """2026-10-21: elle tetiklenen tur 30 dk calisip sert sinirda olduruldu. SoftTimeLimitExceeded
    siradan bir Exception'dir; ceviri katmanindaki genis except'ler onu yutuyor, tur durmuyordu.
    Tur kendi sure butcesini izler ve yumusak sinirdan once temiz biter."""

    def test_butce_dolunca_tur_temiz_biter_ve_imlec_ilerlemez(self):
        self.use_translator(FakeTranslator(CEVIRILER))
        ilk = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'butce-1')
        ikinci = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'butce-2')

        # Ilk kayit cevrilince butce dolmus sayilir
        with mock.patch('news.retranslate._sure_doldu',
                        side_effect=lambda bitis: AINewsEntry.objects.filter(needs_translation=False).exists()):
            sonuc = self._calistir()

        ilk.refresh_from_db()
        ikinci.refresh_from_db()
        self.assertFalse(ilk.needs_translation)
        self.assertTrue(ikinci.needs_translation)
        self.assertEqual(ikinci.translation_attempts, 0, 'Butce dolmasi kaydin hatasi degil')
        self.assertTrue(sonuc['stopped'])
        self.assertEqual(sonuc['stopped_reason'], 'time_budget')

        # Sonraki tur kaldigi yerden: ikinci kayit cevrilir
        self._calistir()
        ikinci.refresh_from_db()
        self.assertFalse(ikinci.needs_translation)

    def test_sifir_butcede_hic_kayit_islenmez(self):
        self.use_translator(FakeTranslator(CEVIRILER))
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'butce-0')
        from news.retranslate import retranslate_pending

        sonuc = retranslate_pending(redis_client=self.redis, prefix=self.prefix, sure_butcesi=0)

        kayit.refresh_from_db()
        self.assertTrue(kayit.needs_translation)
        self.assertEqual(sonuc['stopped_reason'], 'time_budget')
        self.assertEqual(sonuc['sections'], {})

    def test_varsayilan_butce_yumusak_sinirin_altinda(self):
        from django.conf import settings
        from news.retranslate import RETRANSLATE_TIME_BUDGET
        self.assertLess(RETRANSLATE_TIME_BUDGET, settings.CELERY_TASK_SOFT_TIME_LIMIT)
        self.assertGreater(RETRANSLATE_TIME_BUDGET, 0)


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


class RetranslateGoreviTests(RetranslateKilitMixin, SimpleTestCase):
    """Kilit izolasyonu mixin'den gelir: canli retranslate:kilit anahtarina dokunulmaz."""

    def test_gorev_retranslate_pending_cagirir(self):
        from news import tasks
        with mock.patch('news.retranslate.retranslate_pending',
                        return_value={'translated': 3}) as sahte:
            self.assertEqual(tasks.retranslate_pending_task(), {'translated': 3})
        sahte.assert_called_once_with()

    # --- Tekil calisma kilidi (spec 2026-11-02 G4): saatlik turlar ust uste binmemeli ---

    def test_kilit_tutuluyken_ikinci_tur_atlar(self):
        from news import tasks
        redis_client, anahtar = self.kilit_redis, self.kilit_anahtari
        redis_client.set(anahtar, 'baska-turun-jetonu', ex=300)
        with mock.patch('news.retranslate.retranslate_pending') as sahte:
            sonuc = tasks.retranslate_pending_task()
        self.assertEqual(sonuc, {'skipped': 'locked'})
        sahte.assert_not_called()
        self.assertEqual(redis_client.get(anahtar), b'baska-turun-jetonu',
                         'sahibi olmayan tur kilidi silmemeli / degistirmemeli')

    def test_tur_calisirken_kilit_tutulur_ve_omru_vardir(self):
        from news.retranslate import RETRANSLATE_TIME_BUDGET
        from news import tasks
        redis_client, anahtar = self.kilit_redis, self.kilit_anahtari
        gorulen = {}

        def sahte_tur():
            gorulen['deger'] = redis_client.get(anahtar)
            gorulen['ttl'] = redis_client.ttl(anahtar)
            return {'translated': 1}

        with mock.patch('news.retranslate.retranslate_pending', side_effect=sahte_tur):
            tasks.retranslate_pending_task()
        self.assertTrue(gorulen['deger'], 'tur calisirken kilit tutulmali')
        self.assertGreater(gorulen['ttl'], RETRANSLATE_TIME_BUDGET)
        self.assertLessEqual(gorulen['ttl'], RETRANSLATE_TIME_BUDGET + 600)

    def test_kilit_omru_sert_sinir_arti_60_sn_i_asmaz(self):
        """Butce env ile buyutulse de olu worker'in kilidi sert sinirdan (+60 sn) uzun yasamaz;
        yoksa sonraki saatlik tur atlanabilirdi."""
        from news import tasks
        redis_client, anahtar = self.kilit_redis, self.kilit_anahtari
        gorulen = {}

        def sahte_tur():
            gorulen['ttl'] = redis_client.ttl(anahtar)
            return {'translated': 0}

        with mock.patch('news.retranslate.RETRANSLATE_TIME_BUDGET', 3500), \
                mock.patch('news.retranslate.retranslate_pending', side_effect=sahte_tur):
            tasks.retranslate_pending_task()
        self.assertLessEqual(gorulen['ttl'], settings.CELERY_TASK_TIME_LIMIT + 60)
        self.assertGreater(gorulen['ttl'], settings.CELERY_TASK_TIME_LIMIT)

    def test_tur_bitince_kilit_birakilir(self):
        from news import tasks
        redis_client, anahtar = self.kilit_redis, self.kilit_anahtari
        with mock.patch('news.retranslate.retranslate_pending', return_value={'translated': 2}):
            self.assertEqual(tasks.retranslate_pending_task(), {'translated': 2})
        self.assertFalse(redis_client.exists(anahtar))

    def test_tur_istisnayla_bitse_de_kilit_birakilir(self):
        from news import tasks
        redis_client, anahtar = self.kilit_redis, self.kilit_anahtari
        with mock.patch('news.retranslate.retranslate_pending', side_effect=RuntimeError('patladi')):
            with self.assertRaises(RuntimeError):
                tasks.retranslate_pending_task()
        self.assertFalse(redis_client.exists(anahtar))

    def test_sure_asiminda_baskasinin_kilidi_silinmez(self):
        """Kilit TTL ile dusup baska tur yeni kilit aldiysa, eski tur bitince onu silmemeli."""
        from news import tasks
        redis_client, anahtar = self.kilit_redis, self.kilit_anahtari

        def sahte_tur():
            redis_client.set(anahtar, 'yeni-turun-jetonu', ex=300)
            return {'translated': 0}

        with mock.patch('news.retranslate.retranslate_pending', side_effect=sahte_tur):
            tasks.retranslate_pending_task()
        self.assertEqual(redis_client.get(anahtar), b'yeni-turun-jetonu')

    def test_redis_ulasilamazsa_tur_yine_de_kosar(self):
        """Kilit yuzunden tur kaybedilmez: Redis yoksa uyarilir ve tur kosulur."""
        from news import tasks
        with mock.patch('news.retranslate._canli_redis', side_effect=ConnectionError('redis yok')), \
                mock.patch('news.retranslate.retranslate_pending',
                           return_value={'translated': 5}) as sahte:
            self.assertEqual(tasks.retranslate_pending_task(), {'translated': 5})
        sahte.assert_called_once_with()

    def test_beat_takvimi_saatlik_cekim_saatleri_haric(self):
        """Spec 2026-11-02 G4: saatlik tur, cekim saatleri (00/06/12/18) haric; gunde 20 tur."""
        self.assertNotIn('retranslate-pending-every-2h', settings.CELERY_BEAT_SCHEDULE)
        giris = settings.CELERY_BEAT_SCHEDULE['retranslate-pending-hourly']
        self.assertEqual(giris['task'], 'news.tasks.retranslate_pending_task')
        self.assertEqual(giris['schedule'].minute, {5})
        self.assertEqual(giris['schedule'].hour, set(range(24)) - {0, 6, 12, 18})

    def test_cekim_saatleriyle_cakismaz(self):
        """Fetch task'lari 00/06/12/18'de calisir; retranslate o saatlere dusmemeli."""
        cekim_saatleri = set()
        for giris in settings.CELERY_BEAT_SCHEDULE.values():
            if giris['task'].startswith('news.tasks.fetch_'):
                cekim_saatleri |= giris['schedule'].hour
        self.assertEqual(cekim_saatleri, {0, 6, 12, 18})
        retranslate_saatleri = settings.CELERY_BEAT_SCHEDULE['retranslate-pending-hourly']['schedule'].hour
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
        self.assertGreater(self.bozuk.updated_at, once,
                           'Isaretleme updated_at ilerletmeli; aksi halde saklama suzgeci '
                           'yeniden cevrilmeyi bekleyen kaydi silebilir')

    def test_ikinci_calistirmada_bulunacak_bir_sey_kalmaz(self):
        self._komut('--uygula')
        self.assertIn('TOPLAM: 0', self._komut())


class GeminiSahteMixin:
    """gemini modulunu ag erisimi olmadan taklit eder."""

    def gemini_ayarla(self, cevap=None, hazir=True, butce=True, istek_say=False, paket=None):
        """cevap: alanlar sozlugunu alan fonksiyon, sabit sozluk ya da None (cevrilemedi).
        hazir: sabit bool ya da parametresiz bir fonksiyon (cagri sirasinda degisebilir).
        istek_say: her istek (kaydi_cevir cagrisi ya da paket) gercek istemci gibi gunluk sayaci artirir.
        paket: paket_cevir'in senaryosu; kayitlar sozlugunu alip PaketSonucu donen fonksiyon ya da
          PaketSonucu listesi (sirayla). Verilmezse her kayit icin cevap uygulanir (None -> reddedilen).

        Kayitlar: gemini_cagrilar Gemini'ye giden her kaydin alanlari (iki yol), tekil_cagrilar
        kaydi_cevir cagrilari, paket_cagrilar paket_cevir istekleri (kimlik -> alanlar), paket_bolumleri
        her paketin bolum adi."""
        self.gemini_cagrilar, self.tekil_cagrilar, self.paket_cagrilar, self.paket_bolumleri = [], [], [], []
        hazir_fn = hazir if callable(hazir) else (lambda: hazir)
        hazir_mi = (lambda: hazir_fn() and butce)
        senaryo = iter(paket) if isinstance(paket, (list, tuple)) else None

        def istegi_say():
            if istek_say:
                gemini._get_butce().artir(gemini.butce_anahtari())

        def kaydi_cevir(alanlar, bolum=None):
            self.gemini_cagrilar.append(dict(alanlar))
            self.tekil_cagrilar.append(dict(alanlar))
            istegi_say()
            return cevap(alanlar) if callable(cevap) else cevap

        def paket_cevir(kayitlar, bolum=None):
            if not hazir_mi():  # gercek istemci gibi: istek atilmaz
                return gemini.PaketSonucu(istek_hatasi=True)
            self.paket_cagrilar.append({kimlik: dict(alanlar) for kimlik, alanlar in kayitlar.items()})
            self.paket_bolumleri.append(bolum)
            self.gemini_cagrilar.extend(dict(alanlar) for alanlar in kayitlar.values())
            istegi_say()
            if senaryo is not None:
                return next(senaryo)
            if callable(paket):
                return paket(kayitlar)
            sonuc = gemini.PaketSonucu()
            for kimlik, alanlar in kayitlar.items():
                ceviri = cevap(alanlar) if callable(cevap) else cevap
                if ceviri is None:
                    sonuc.reddedilen.add(kimlik)
                else:
                    sonuc.ceviriler[kimlik] = ceviri
            return sonuc

        for hedef, deger in (('hazir', hazir_mi), ('butce_var', lambda: butce),
                             ('kaydi_cevir', kaydi_cevir), ('paket_cevir', paket_cevir)):
            yama = mock.patch.object(gemini, hedef, deger)
            yama.start()
            self.addCleanup(yama.stop)

    def paket_siniri(self, adet=None, karakter=None):
        """GEMINI_BATCH_MAX / GEMINI_BATCH_CHARS'i test suresince degistirir (adet=1: kayit basina istek)."""
        for hedef, deger in (('GEMINI_BATCH_MAX', adet), ('GEMINI_BATCH_CHARS', karakter)):
            if deger is not None:
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
            published_date=date(2026, 9, 12), severity='Yuksek', cvss_score=8.1, needs_translation=True)

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

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertFalse(kayit.needs_translation)
        self.assertEqual(kayit.translation_provider, 'libretranslate')

    def test_bir_bolumdeki_durma_sonraki_bolumleri_kilitlemez(self):
        """Haberdeki zehirli kayit LibreTranslate'i kapatsa da Gemini hazirken ai bolumu ayni turda islenir."""
        def cevap(protected):
            if 'Z' * 50 in protected:
                self.libre.hazir = False  # 102k haber: LibreTranslate ReadTimeout -> devre kesici
                return None
            return 'LIBRE ' + protected

        self.libre._cevap = cevap
        self.gemini_ayarla(_gemini_cevirisi)
        NewsArticle.objects.create(
            source='SANS ISC', original_title='Patch Tuesday summary',
            turkish_title='Patch Tuesday summary', original_description='Z' * 13000,
            turkish_description='Z' * 13000, link='https://ornek.test/haber/zehir',
            date=date(2026, 10, 13), original_date='2026-10-13', needs_translation=True)
        ai = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'sonraki-bolum')

        sonuc = self._calistir()

        ai.refresh_from_db()
        self.assertTrue(sonuc['stopped'])
        self.assertIn('ai', sonuc['sections'], 'Haberdeki durma ai bolumunu atlatmamali')
        self.assertFalse(ai.needs_translation)
        self.assertEqual(ai.translation_provider, 'gemini')

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

    def test_transport_hatasinda_yukseltme_deneme_saymaz(self):
        durum = {'hazir': True}

        def paket(kayitlar):
            durum['hazir'] = False  # 429/ag hatasi: devre kesici acildi
            return gemini.PaketSonucu(istek_hatasi=True)

        self.gemini_ayarla(hazir=lambda: durum['hazir'], paket=paket)
        self.paket_siniri(adet=1)  # iki ayri paket: ilkinin hatasi ikincisini durdurmali
        kayit1 = _libre_kaydi('t1')
        kayit2 = _libre_kaydi('t2')

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(len(self.paket_cagrilar), 1, 'Ilk istek hatasinda asama durmaliydi')
        for kayit in (kayit1, kayit2):
            kayit.refresh_from_db()
            self.assertEqual(kayit.translation_provider, 'libretranslate')
            self.assertEqual(kayit.translation_attempts, 0, 'Istek hatasi deneme sayilmaz')
        self.assertEqual(list(self.redis.scan_iter(f'{self.prefix}:upgrade-cursor:*')), [])

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
        self.assertEqual(kayit.translation_attempts, 1, 'Gemini hazirken reddetti: icerik hatasi')

    def test_yukseltme_icerik_hatasi_tur_sonucunda_failed_sayilir(self):
        def cevap(alanlar):
            return None if 'Story number 1' in alanlar.get('title', '') else _gemini_cevirisi(alanlar)

        self.gemini_ayarla(cevap)
        _libre_kaydi('f1', baslik='Story number 1 published')
        _libre_kaydi('f2', baslik='Story number 2 published')

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 1)
        self.assertEqual(sonuc['sections']['ai'], {'translated': 0, 'failed': 1, 'upgraded': 1})
        self.assertEqual(sonuc['failed'], 1)

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

    def test_butce_bitince_kalanlar_sonraki_tura_kalir(self):
        durum = {'kalan': 1}

        def cevap(alanlar):
            durum['kalan'] -= 1
            return _gemini_cevirisi(alanlar)

        self.gemini_ayarla(cevap)
        self.paket_siniri(adet=1)  # kayit basina bir paket: butce paketler arasinda biter
        # hazir() ikinci kayittan once False'a dusmeli
        yama = mock.patch.object(gemini, 'hazir', lambda: durum['kalan'] > 0)
        yama.start()
        self.addCleanup(yama.stop)
        for i in range(3):
            _libre_kaydi(f'y5-{i}', baslik=f'Story number {i + 1} published')

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 1)
        kalanlar = AINewsEntry.objects.filter(translation_provider='libretranslate')
        self.assertEqual(kalanlar.count(), 2)
        self.assertEqual([k.translation_attempts for k in kalanlar], [0, 0], 'Butce bitisi deneme sayilmaz')
        self.assertEqual(list(self.redis.scan_iter(f'{self.prefix}:upgrade-cursor:*')), [])

        durum['kalan'] = 5  # ertesi gun: butce yenilendi
        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 2)
        self.assertFalse(AINewsEntry.objects.filter(translation_provider='libretranslate').exists())

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
        self.assertEqual(kayit.translation_attempts, 1, 'Isaret kaybi icerik hatasidir, deneme sayilir')

    def test_google_kayitlari_yukseltilmez(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _libre_kaydi('y7')
        kayit.translation_provider = 'google'
        kayit.save(update_fields=['translation_provider'])

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(self.gemini_cagrilar, [])


def _cve_kaydi(no, cvss=None, kev=None, needs_translation=False):
    govde = 'A remote attacker can read arbitrary files from the server.'
    return CVEEntry.objects.create(
        cve_id=f'CVE-2026-{no}', source='NVD', original_title=f'CVE-2026-{no} - Guvenlik Acigi',
        turkish_title=f'CVE-2026-{no} - Guvenlik Acigi', original_description=govde,
        turkish_description=govde if needs_translation else 'LIBRE ' + govde,
        link=f'https://ornek.test/cve/{no}', published_date=date(2026, 9, 12),
        cvss_score=cvss, kev_added_date=kev, needs_translation=needs_translation,
        translation_provider='' if needs_translation else 'libretranslate')


class OnemSinifiTests(GeminiSahteMixin, SaglayiciZinciriMixin, RetranslateTestBase):
    """Spec 2026-11-02 G1/G2: yalniz CVSS >= 7 ya da KEV CVE Gemini alir; yukseltme en yeniden baslar."""

    def setUp(self):
        super().setUp()
        self.libre = self.saglayicilari_ayarla(SahteSaglayici('libretranslate', _libre))[0]

    def _saglayici(self, kayit):
        kayit.refresh_from_db()
        return kayit.translation_provider

    def test_orta_cve_yukseltilmez(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _cve_kaydi('7001', cvss=6.5)

        self._calistir()

        self.assertEqual(self._saglayici(kayit), 'libretranslate')
        self.assertEqual(self.gemini_cagrilar, [])

    def test_yuksek_cve_yukseltilir(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _cve_kaydi('7002', cvss=7.0)

        self._calistir()

        self.assertEqual(self._saglayici(kayit), 'gemini')

    def test_kev_orta_cve_yukseltilir(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _cve_kaydi('7003', cvss=5.0, kev=date(2026, 9, 10))

        self._calistir()

        self.assertEqual(self._saglayici(kayit), 'gemini')

    def test_skorsuz_cve_yukseltilmez(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _cve_kaydi('7004')

        self._calistir()

        self.assertEqual(self._saglayici(kayit), 'libretranslate')
        self.assertEqual(self.gemini_cagrilar, [])

    def test_orta_cve_bekleyende_gemini_almaz(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _cve_kaydi('7005', cvss=4.0, needs_translation=True)

        self._calistir()

        kayit.refresh_from_db()
        self.assertFalse(kayit.needs_translation)
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertTrue(kayit.turkish_description.startswith('LIBRE'))
        self.assertEqual(self.gemini_cagrilar, [])

    def test_orta_cve_zincir_kapaliyken_icerik_hatasi_sayilmaz(self):
        """Aday olmayan CVE'yi Gemini reddetmis sayilmaz: zincir yoksa bolum durur, sayac artmaz."""
        self.libre.hazir = False
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _cve_kaydi('7006', cvss=4.0, needs_translation=True)

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertTrue(kayit.needs_translation)
        self.assertEqual(kayit.translation_attempts, 0)
        self.assertEqual(sonuc['failed'], 0)
        self.assertEqual(self.gemini_cagrilar, [])

    def test_yukseltme_en_yeniden_baslar(self):
        from django.utils import timezone
        self.gemini_ayarla(_gemini_cevirisi)
        kayitlar = [_libre_kaydi(f'yeni-{i}', baslik=f'Story number {i + 1} published') for i in range(3)]
        simdi = timezone.now()
        # En yeni olan ortadaki kayit: ne id ne updated_at sirasi onu one alir
        for kayit, saat_once in zip(kayitlar, (5, 1, 3)):
            AINewsEntry.objects.filter(pk=kayit.pk).update(created_at=simdi - timedelta(hours=saat_once))

        sonuc = self._calistir(upgrade_batch=1)

        self.assertEqual(sonuc['upgraded'], 1)
        self.assertEqual([self._saglayici(k) for k in kayitlar], ['libretranslate', 'gemini', 'libretranslate'])

    def test_reddedilen_yukseltme_deneme_sayar(self):
        from news.retranslate import RETRANSLATE_MAX_ATTEMPTS
        self.gemini_ayarla(None)  # Gemini hazir ama her seferinde reddediyor
        kayit = _libre_kaydi('red1')

        self._calistir()
        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_attempts, 1)

        for _ in range(RETRANSLATE_MAX_ATTEMPTS - 1):
            self._calistir()
        self.assertEqual(len(self.gemini_cagrilar), RETRANSLATE_MAX_ATTEMPTS)

        self._calistir()  # esige ulasti: artik aday degil
        self.assertEqual(len(self.gemini_cagrilar), RETRANSLATE_MAX_ATTEMPTS)
        self.assertEqual(self._saglayici(kayit), 'libretranslate')

    def test_cok_uzun_kayit_yukseltmede_deneme_sayar(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _libre_kaydi('uzun3', govde='C' * (gemini.GEMINI_MAX_CHARS + 1))

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_attempts, 1)
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertEqual(kayit.translation_provider, 'libretranslate')


class KalanTurSayisiTests(SimpleTestCase):
    """Spec 2026-11-02 G4: gunun kalan tur sayisi Beat takviminden (Istanbul) Pasifik gece yarisina kadar sayilir."""

    def _say(self, *args, **kwargs):
        from news import retranslate
        return retranslate.kalan_tur_sayisi(datetime(*args, tzinfo=gemini.PASIFIK, **kwargs))

    def test_kalan_tur_sayisi_gun_basinda_20(self):
        # 2026-11-10 PST (UTC-8): Pasifik 00:10 = Istanbul 11:10; Pasifik gece yarisi = Istanbul 11:00.
        # simdi - 30 dk = 10:40, sonraki ilk an 11:05 (simdiki tur, dahil). Elle sayilan :05 anlari:
        #   11, 13, 14, 15, 16, 17, 19, 20, 21, 22, 23  -> 11
        #   (ertesi gun) 01, 02, 03, 04, 05, 07, 08, 09, 10  -> 9   (11:05 yeni Pasifik gunune duser)
        self.assertEqual(self._say(2026, 11, 10, 0, 10), 20)

    def test_kalan_tur_sayisi_yaz_saatinde_de_20(self):
        # 2026-07-10 PDT (UTC-7): Pasifik 00:10 = Istanbul 10:10; gun sonu Istanbul 10:00 (ertesi gun).
        #   10 (simdiki tur, 09:40 sonrasi), 11, 13-17, 19-23  -> 12
        #   (ertesi gun) 01-05, 07, 08, 09  -> 8
        self.assertEqual(self._say(2026, 7, 10, 0, 10), 20)

    def test_kalan_tur_sayisi_gun_ortasinda(self):
        # 2026-11-10 Pasifik 12:00 = Istanbul 23:00. 22:30 sonrasi: 23 -> 1; ertesi gun 01-05, 07-10 -> 9.
        self.assertEqual(self._say(2026, 11, 10, 12, 0), 10)

    def test_kalan_tur_en_az_bir(self):
        # Pasifik 23:45 = Istanbul 10:45. 10:15 sonrasi ilk an 11:05, o da yeni Pasifik gunu: sayi 0 -> 1.
        self.assertEqual(self._say(2026, 11, 10, 23, 45), 1)

    def test_kalan_tur_sayisi_takvimden_okunur(self):
        """Sayi takvimin hour/minute kumelerinden gelir, sabit kodlanmaz."""
        takvim = dict(settings.CELERY_BEAT_SCHEDULE)
        takvim['retranslate-pending-hourly'] = {
            'task': 'news.tasks.retranslate_pending_task', 'schedule': crontab(minute='5,35', hour='*')}
        with override_settings(CELERY_BEAT_SCHEDULE=takvim):
            # Pasifik 00:10 = Istanbul 11:10; 10:40 sonrasi 11:05'ten ertesi gun 10:35'e: 24 saat x 2
            self.assertEqual(self._say(2026, 11, 10, 0, 10), 48)


class TurPayiHesabiTests(SimpleTestCase):

    def setUp(self):
        super().setUp()
        self.simdi = datetime(2026, 11, 10, 3, 0, tzinfo=gemini.PASIFIK)

    def _pay(self, kullanim, kalan_tur):
        from news import retranslate
        with mock.patch.object(gemini, 'butce_kullanimi', return_value=kullanim), \
                mock.patch.object(retranslate, 'kalan_tur_sayisi', return_value=kalan_tur) as sayac:
            pay = retranslate.tur_payi(self.simdi)
        sayac.assert_called_once_with(self.simdi)
        return pay

    def test_tur_payi_kalan_butceyi_bolustirir(self):
        self.assertEqual(self._pay(250, 10), 20)   # ceil(200 / 10)
        self.assertEqual(self._pay(241, 10), 21)   # ceil(209 / 10): yukari yuvarlanir
        self.assertEqual(self._pay(0, 20), 23)     # ceil(450 / 20)
        self.assertEqual(self._pay(440, 1), 10)    # gunun son turu kalanin tamamini alir

    def test_tur_payi_butce_bittiyse_sifir(self):
        self.assertEqual(self._pay(450, 5), 0)
        self.assertEqual(self._pay(460, 5), 0, 'Pay negatife inmemeli')

    def test_tur_kalan_harcamayi_duser_ve_sifirin_altina_inmez(self):
        from news import retranslate
        tur = retranslate._Tur(pay=5, baslangic=100)
        with mock.patch.object(gemini, 'butce_kullanimi', return_value=103):
            self.assertEqual(tur.kalan(), 2)
        with mock.patch.object(gemini, 'butce_kullanimi', return_value=110):
            self.assertEqual(tur.kalan(), 0)


class TurPayiTests(GeminiSahteMixin, SaglayiciZinciriMixin, RetranslateTestBase):
    """Spec 2026-11-02 G4: tur payi bitince Gemini istegi atilmaz; bekleyen zincirle surer, yukseltme durur."""

    def setUp(self):
        super().setUp()
        self.libre = self.saglayicilari_ayarla(SahteSaglayici('libretranslate', _libre))[0]

    def _tur(self, pay):
        from news import retranslate
        return retranslate._Tur(pay=pay, baslangic=gemini.butce_kullanimi())

    def test_tur_payi_bitince_gemini_cagrilmaz(self):
        """PR-B: pay=1 tek paket demektir; uc aday ayni istekte gider, sonra istek atilmaz."""
        self.gemini_ayarla(_gemini_cevirisi, istek_say=True)
        kayitlar = [_libre_kaydi(f'pay-{i}', baslik=f'Story number {i + 1} published') for i in range(3)]

        sonuc = self._calistir(tur=self._tur(1))

        self.assertEqual(len(self.paket_cagrilar), 1)
        self.assertEqual(self.tekil_cagrilar, [])
        self.assertEqual(sonuc['upgraded'], 3)
        self.assertEqual(sonuc['stopped_reason'], 'gemini_tur_payi')
        self.assertFalse(sonuc['stopped'])
        self.assertEqual(sonuc['gemini_tur_payi'], 1)
        for kayit in kayitlar:
            kayit.refresh_from_db()
            self.assertEqual(kayit.translation_provider, 'gemini')

    def test_tur_payi_bitince_ikinci_paket_gitmez(self):
        self.gemini_ayarla(_gemini_cevirisi, istek_say=True)
        self.paket_siniri(adet=2)
        kayitlar = [_libre_kaydi(f'pay2-{i}', baslik=f'Story number {i + 1} published') for i in range(3)]

        sonuc = self._calistir(tur=self._tur(1))

        self.assertEqual([len(p) for p in self.paket_cagrilar], [2])
        self.assertEqual(sonuc['upgraded'], 2)
        self.assertEqual(sonuc['stopped_reason'], 'gemini_tur_payi')
        saglayicilar = []
        for kayit in kayitlar:
            kayit.refresh_from_db()
            saglayicilar.append(kayit.translation_provider)
            self.assertEqual(kayit.translation_attempts, 0, 'Pay bitmesi icerik hatasi degildir')
        self.assertEqual(sorted(saglayicilar), ['gemini', 'gemini', 'libretranslate'])

    def test_tur_payi_bitince_bekleyen_zincirle_cevrilir(self):
        self.gemini_ayarla(_gemini_cevirisi, istek_say=True)
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'pay0')

        sonuc = self._calistir(tur=self._tur(0))

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertFalse(kayit.needs_translation)
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertTrue(kayit.turkish_title.startswith('LIBRE'))
        self.assertEqual(sonuc['by_provider'], {'gemini': 0, 'libretranslate': 1})
        self.assertEqual(sonuc['stopped_reason'], 'gemini_tur_payi')
        self.assertFalse(sonuc['stopped'])

    def test_tur_payi_bitince_zincir_kapaliysa_icerik_hatasi_sayilmaz(self):
        """Pay bitti, zincir kapali, Gemini hazir: istek atilmadi; kaydin sucu degil, sayac artmaz."""
        self.libre.hazir = False
        self.gemini_ayarla(_gemini_cevirisi, istek_say=True)
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'pay0z')

        sonuc = self._calistir(tur=self._tur(0))

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertTrue(kayit.needs_translation)
        self.assertEqual(kayit.translation_attempts, 0)
        self.assertEqual(sonuc['failed'], 0)

    def test_oncelik_kati_cve_once(self):
        self.gemini_ayarla(_gemini_cevirisi, istek_say=True)
        self.paket_siniri(adet=1)  # kayit basina istek: pay iki CVE'de biter
        cveler = [_cve_kaydi(f'810{i}', cvss=9.8) for i in range(2)]
        ai_kayitlari = [_libre_kaydi(f'onc-{i}', baslik=f'Story number {i + 1} published') for i in range(2)]

        sonuc = self._calistir(tur=self._tur(2))

        for kayit in cveler:
            kayit.refresh_from_db()
            self.assertEqual(kayit.translation_provider, 'gemini')
        for kayit in ai_kayitlari:
            kayit.refresh_from_db()
            self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(len(self.gemini_cagrilar), 2)
        self.assertEqual(sonuc['sections']['cve']['upgraded'], 2)
        self.assertEqual(sonuc['sections']['ai']['upgraded'], 0)
        self.assertEqual(sonuc['stopped_reason'], 'gemini_tur_payi')

    def test_gunluk_butce_tur_payina_baskin(self):
        """Ikisi birden gecerliyse sebep 'gemini_budget'."""
        self.gemini_ayarla(_gemini_cevirisi, butce=False, istek_say=True)
        _libre_kaydi('baskin')

        sonuc = self._calistir(tur=self._tur(0))

        self.assertEqual(self.gemini_cagrilar, [])
        self.assertEqual(sonuc['stopped_reason'], 'gemini_budget')

    def test_pay_turun_kendi_harcamasini_sayar(self):
        """Kalan = pay - (simdiki kullanim - baslangic): turdan once harcanmis istekler payi yemez."""
        self.gemini_ayarla(_gemini_cevirisi, istek_say=True)
        self.paket_siniri(adet=1)
        for _ in range(7):
            gemini._get_butce().artir(gemini.butce_anahtari())
        for i in range(3):
            _libre_kaydi(f'oncesi-{i}', baslik=f'Story number {i + 1} published')

        sonuc = self._calistir(tur=self._tur(2))

        self.assertEqual(len(self.gemini_cagrilar), 2)
        self.assertEqual(sonuc['upgraded'], 2)

    def test_tur_verilmezse_tur_payindan_kurulur(self):
        from news import retranslate
        self.gemini_ayarla(_gemini_cevirisi, istek_say=True)
        self.paket_siniri(adet=1)
        for i in range(3):
            _libre_kaydi(f'vars-{i}', baslik=f'Story number {i + 1} published')

        with mock.patch.object(retranslate, 'tur_payi', return_value=2) as tur_payi:
            sonuc = self._calistir()

        tur_payi.assert_called_once()
        simdi = tur_payi.call_args.args[0]
        self.assertIsNotNone(simdi.tzinfo, 'tur_payi zaman dilimli bir an almali (timezone.now())')
        self.assertEqual(sonuc['gemini_tur_payi'], 2)
        self.assertEqual(len(self.gemini_cagrilar), 2)


def _ceviri_paketi(kayitlar, reddet=()):
    """Senaryo yardimcisi: reddet'teki kimlikler reddedilen, digerleri 'GEMINI ' onekiyle cevrilir."""
    sonuc = gemini.PaketSonucu()
    for kimlik, alanlar in kayitlar.items():
        if kimlik in reddet:
            sonuc.reddedilen.add(kimlik)
        else:
            sonuc.ceviriler[kimlik] = _gemini_cevirisi(alanlar)
    return sonuc


class PaketliYukseltmeTests(GeminiSahteMixin, SaglayiciZinciriMixin, RetranslateTestBase):
    """Spec 2026-11-02 G5: yukseltme asamasi bir istekte birden cok kayit gonderir."""

    def setUp(self):
        super().setUp()
        self.libre = self.saglayicilari_ayarla(SahteSaglayici('libretranslate', _libre))[0]

    def _ai_adaylari(self, adet, onek='pk'):
        return [_libre_kaydi(f'{onek}-{i}', baslik=f'Story number {i + 1} published') for i in range(adet)]

    def _kayit(self, kayit):
        kayit.refresh_from_db()
        return kayit

    def test_paketle_karakter_ve_adet_siniri(self):
        from news.retranslate import _paketle

        def boylari(adaylar):
            return [len(paket) for paket in _paketle(adaylar, 10000, 15)]

        orta = [(i, {'title': 'a' * 400, 'description': 'b' * 500}) for i in range(20)]
        self.assertEqual(boylari(orta), [11, 9])          # 11 x 900 = 9900; 12. kayit 10800 olurdu
        kisa = [(i, {'title': 'c' * 100}) for i in range(20)]
        self.assertEqual(boylari(kisa), [15, 5])          # adet siniri
        paketler = _paketle(orta, 10000, 15)
        self.assertEqual([k for paket in paketler for k, _ in paket], list(range(20)), 'Sira korunmali')
        # Tek basina sinirdan buyuk kayit kendi paketinde gider; oncesi ve sonrasi ayri paketlerdir
        buyuk = [(0, {'title': 'x' * 100}), (1, {'title': 'y' * 11000}), (2, {'title': 'z' * 100})]
        self.assertEqual([[k for k, _ in paket] for paket in _paketle(buyuk, 10000, 15)], [[0], [1], [2]])
        self.assertEqual(_paketle([], 10000, 15), [])

    def test_yukseltme_tek_istekte_bes_kayit(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayitlar = self._ai_adaylari(5)

        sonuc = self._calistir(upgrade_batch=5)

        self.assertEqual(len(self.paket_cagrilar), 1)
        self.assertEqual(sorted(self.paket_cagrilar[0]), ['k0', 'k1', 'k2', 'k3', 'k4'])
        self.assertEqual(self.paket_bolumleri, ['ai'], 'Bolum adi log icin paket_cevir\'e gecmeli')
        self.assertEqual(self.tekil_cagrilar, [])
        self.assertEqual(sonuc['upgraded'], 5)
        for kayit in kayitlar:
            kayit = self._kayit(kayit)
            self.assertEqual(kayit.translation_provider, 'gemini')
            self.assertEqual(kayit.turkish_title, 'GEMINI ' + kayit.original_title)

    def test_paketteki_reddedilen_deneme_sayar_digerleri_yazilir(self):
        def cevap(alanlar):
            return None if alanlar['title'] == 'Story number 2 published' else _gemini_cevirisi(alanlar)

        self.gemini_ayarla(cevap)
        kayitlar = self._ai_adaylari(3)

        sonuc = self._calistir()

        self.assertEqual(len(self.paket_cagrilar), 1)
        self.assertEqual((sonuc['upgraded'], sonuc['failed']), (2, 1))
        for kayit in map(self._kayit, kayitlar):
            reddedildi = kayit.original_title == 'Story number 2 published'
            self.assertEqual(kayit.translation_provider, 'libretranslate' if reddedildi else 'gemini')
            self.assertEqual(kayit.translation_attempts, 1 if reddedildi else 0)

    def test_eksik_kimlik_yalniz_o_kaydi_reddeder(self):
        """Yanitta k1 hic yok (ne cevrilen ne reddedilen): yalniz o kayit sayilir; ceviriler kimlikle eslenir."""
        def paket(kayitlar):
            sonuc = _ceviri_paketi(kayitlar)
            del sonuc.ceviriler['k1']
            return sonuc

        self.gemini_ayarla(paket=paket)
        self._ai_adaylari(3)

        sonuc = self._calistir()

        self.assertEqual((sonuc['upgraded'], sonuc['failed']), (2, 1))
        gonderilen = self.paket_cagrilar[0]
        for kimlik, alanlar in gonderilen.items():
            kayit = AINewsEntry.objects.get(original_title=alanlar['title'])
            if kimlik == 'k1':
                self.assertEqual((kayit.translation_provider, kayit.translation_attempts), ('libretranslate', 1))
            else:
                self.assertEqual(kayit.turkish_title, 'GEMINI ' + alanlar['title'], 'Ceviri kendi kaydina yazilmali')
                self.assertEqual(kayit.translation_attempts, 0)

    def test_istek_hatasinda_hicbir_kayit_deneme_saymaz(self):
        durum = {'hazir': True}

        def paket(kayitlar):
            durum['hazir'] = False  # 429/5xx/ag: devre kesici acildi
            return gemini.PaketSonucu(istek_hatasi=True)

        self.gemini_ayarla(hazir=lambda: durum['hazir'], paket=paket)
        self.paket_siniri(adet=2)
        kayitlar = self._ai_adaylari(4)

        sonuc = self._calistir()

        self.assertEqual(len(self.paket_cagrilar), 1, 'Istek hatasinda asama durmali, ikinci paket gitmemeli')
        self.assertEqual((sonuc['upgraded'], sonuc['failed']), (0, 0))
        for kayit in map(self._kayit, kayitlar):
            self.assertEqual(kayit.translation_attempts, 0)
            self.assertEqual(kayit.translation_provider, 'libretranslate')

    def test_kayda_ozgu_istek_hatasi_paketi_boler(self):
        """Gemini hazirken istek hatasi (kayda ozgu 4xx, devre kesici yok): kesilme gibi ikiye bolunur."""
        senaryo = iter([gemini.PaketSonucu(istek_hatasi=True)])
        self.gemini_ayarla(paket=lambda kayitlar: next(senaryo, None) or _ceviri_paketi(kayitlar))
        kayitlar = self._ai_adaylari(4)

        sonuc = self._calistir()

        self.assertEqual([len(p) for p in self.paket_cagrilar], [4, 2, 2])
        self.assertEqual(sonuc['upgraded'], 4)
        for kayit in map(self._kayit, kayitlar):
            self.assertEqual((kayit.translation_provider, kayit.translation_attempts), ('gemini', 0))

    def test_tek_kayit_kayda_ozgu_istek_hatasi_icerik_hatasi(self):
        self.gemini_ayarla(paket=lambda kayitlar: gemini.PaketSonucu(istek_hatasi=True))
        kayit = _libre_kaydi('ozgu-1')

        sonuc = self._calistir()

        self.assertEqual(len(self.paket_cagrilar), 1)
        self.assertEqual(sonuc['failed'], 1)
        self.assertEqual(self._kayit(kayit).translation_attempts, 1)

    def test_kesilen_paket_ikiye_bolunup_ayni_turda_denenir(self):
        senaryo = iter([gemini.PaketSonucu(kesildi=True)])
        self.gemini_ayarla(paket=lambda kayitlar: next(senaryo, None) or _ceviri_paketi(kayitlar))
        kayitlar = self._ai_adaylari(4)

        sonuc = self._calistir()

        self.assertEqual([len(p) for p in self.paket_cagrilar], [4, 2, 2])
        self.assertEqual(sonuc['upgraded'], 4)
        # Bolunen yarilar sirayi korur: ilk yari ilk paketin ilk iki kaydidir
        ilk = [a['title'] for a in self.paket_cagrilar[0].values()]
        self.assertEqual([a['title'] for a in self.paket_cagrilar[1].values()], ilk[:2])
        self.assertEqual([a['title'] for a in self.paket_cagrilar[2].values()], ilk[2:])
        for kayit in map(self._kayit, kayitlar):
            self.assertEqual((kayit.translation_provider, kayit.translation_attempts), ('gemini', 0))

    def test_tek_kayit_kesilirse_icerik_hatasi(self):
        self.gemini_ayarla(paket=lambda kayitlar: gemini.PaketSonucu(kesildi=True))
        kayitlar = self._ai_adaylari(2)

        sonuc = self._calistir()

        self.assertEqual([len(p) for p in self.paket_cagrilar], [2, 1, 1])
        self.assertEqual((sonuc['upgraded'], sonuc['failed']), (0, 2))
        for kayit in map(self._kayit, kayitlar):
            self.assertEqual((kayit.translation_provider, kayit.translation_attempts), ('libretranslate', 1))

    def test_yanit_bozuk_paket_bolunur_yalniz_suclu_sayilir(self):
        """Bir kayit tum yaniti bozuyor (SAFETY): paket bolunur, yalniz suclu deneme sayar (B2 fix 1)."""
        suclu = 'Story number 2 published'  # en yeni once sirada k2

        def paket(kayitlar):
            if any(alanlar['title'] == suclu for alanlar in kayitlar.values()):
                return gemini.PaketSonucu(yanit_bozuk=True)
            return _ceviri_paketi(kayitlar)

        self.gemini_ayarla(paket=paket)
        kayitlar = self._ai_adaylari(4)

        sonuc = self._calistir()

        self.assertEqual(self.paket_cagrilar[0]['k2']['title'], suclu)
        self.assertEqual([len(p) for p in self.paket_cagrilar], [4, 2, 2, 1, 1])
        self.assertEqual((sonuc['upgraded'], sonuc['failed']), (3, 1))
        for kayit in map(self._kayit, kayitlar):
            if kayit.original_title == suclu:
                self.assertEqual((kayit.translation_provider, kayit.translation_attempts), ('libretranslate', 1))
            else:
                self.assertEqual((kayit.translation_provider, kayit.translation_attempts), ('gemini', 0))

    def test_hep_bozuk_yanitta_seri_bolumu_durdurur(self):
        self.gemini_ayarla(paket=lambda kayitlar: gemini.PaketSonucu(yanit_bozuk=True))
        self._ai_adaylari(7)

        sonuc = self._calistir(upgrade_batch=7)

        # 7 -> 4+3 -> 2+2 -> 1+1 ...: 5. tek kayit reddinde durur (11 istek); 2 kayit sayilmaz
        self.assertEqual(len(self.paket_cagrilar), 11)
        self.assertEqual((sonuc['upgraded'], sonuc['failed']), (0, 5))
        self.assertEqual(sonuc['sections']['ai']['stopped_reason'], 'ardisik_icerik_hatasi')
        denemeler = sorted(AINewsEntry.objects.values_list('translation_attempts', flat=True))
        self.assertEqual(denemeler, [0, 0, 1, 1, 1, 1, 1])

    def test_paketli_k8s_isaret_kaybi_icerik_hatasi(self):
        """GitHub Releases disi K8s kaydi paketlenir ama isaret denetiminden yine gecer (B2 fix 2)."""
        govde = 'Release notes:\n---ITEM---\nAdds a flag.'

        def cevap(alanlar):
            ceviri = _gemini_cevirisi(alanlar)
            if 'description' in ceviri:
                ceviri['description'] = ceviri['description'].replace('---ITEM---', '')
            return ceviri

        self.gemini_ayarla(cevap)
        kayit = KubernetesEntry.objects.create(
            source='Kubernetes Blog', category='release', version='', original_title='Kubernetes notes',
            turkish_title='LIBRE Kubernetes notes', original_description=govde,
            turkish_description='LIBRE ' + govde, link='https://ornek.test/k8s/paket-isaret',
            published_date=date(2026, 9, 12), needs_translation=False, translation_provider='libretranslate')
        eski = kayit.turkish_description

        sonuc = self._calistir()

        self.assertEqual(self.tekil_cagrilar, [])
        self.assertEqual(len(self.paket_cagrilar), 1)
        kayit = self._kayit(kayit)
        self.assertEqual(sonuc['sections']['kubernetes']['upgraded'], 0)
        self.assertEqual((kayit.translation_provider, kayit.translation_attempts), ('libretranslate', 1))
        self.assertEqual(kayit.turkish_description, eski)

    def test_k8s_yapisal_changelog_paketlenmez(self):
        self.gemini_ayarla(_gemini_cevirisi)
        yapisal_govde = '===SECTION: Features===\n---ITEM---\nAdds a flag.\n<<<PR#123|@kisi|sig>>>'
        ortak = dict(category='release', published_date=date(2026, 9, 12), needs_translation=False,
                     translation_provider='libretranslate')
        yapisal = KubernetesEntry.objects.create(
            source='GitHub Releases', version='v1.35.0', original_title='Kubernetes v1.35.0 released',
            turkish_title='LIBRE Kubernetes v1.35.0 released', original_description=yapisal_govde,
            turkish_description='LIBRE ' + yapisal_govde, link='https://ornek.test/k8s/paket1', **ortak)
        blog = KubernetesEntry.objects.create(
            source='Kubernetes Blog', version='', original_title='Farmers adopt new sensors',
            turkish_title='LIBRE Farmers adopt new sensors',
            original_description='Sensors measure soil moisture every hour.',
            turkish_description='LIBRE Sensors measure soil moisture every hour.',
            link='https://ornek.test/k8s/paket2', **ortak)

        sonuc = self._calistir()

        self.assertEqual(self.tekil_cagrilar, [{'title': 'Kubernetes v1.35.0 released', 'description': yapisal_govde}])
        self.assertEqual(self.paket_cagrilar, [{'k0': {'title': 'Farmers adopt new sensors',
                                                       'description': 'Sensors measure soil moisture every hour.'}}])
        self.assertEqual(sonuc['sections']['kubernetes']['upgraded'], 2)
        for kayit in (yapisal, blog):
            self.assertEqual(self._kayit(kayit).translation_provider, 'gemini')

    def test_tur_payi_paket_basina_sayilir(self):
        self.gemini_ayarla(_gemini_cevirisi, istek_say=True)
        kayitlar = self._ai_adaylari(5)
        from news import retranslate
        tur = retranslate._Tur(pay=1, baslangic=gemini.butce_kullanimi())

        sonuc = self._calistir(upgrade_batch=5, tur=tur)

        self.assertEqual(len(self.paket_cagrilar), 1)
        self.assertEqual(gemini.butce_kullanimi() - tur.baslangic, 1, 'Paket tek istek sayilir')
        self.assertEqual(sonuc['upgraded'], 5)
        for kayit in map(self._kayit, kayitlar):
            self.assertEqual(kayit.translation_provider, 'gemini')

    def test_ardisik_red_paket_sirasinda_sayilir(self):
        """Seri paket sirasiyla sayilir; paketin kabul edilen kaydi sifirlar; 5'te bolum durur."""
        self.paket_siniri(adet=3)
        senaryo = [
            lambda k: _ceviri_paketi(k, reddet={'k0', 'k1', 'k2'}),   # seri 3
            lambda k: _ceviri_paketi(k, reddet={'k1', 'k2'}),         # k0 sifirlar, seri 2
            lambda k: _ceviri_paketi(k, reddet={'k0', 'k1', 'k2'}),   # seri 5 -> dur
        ]
        sira = iter(senaryo)
        self.gemini_ayarla(paket=lambda kayitlar: next(sira)(kayitlar))
        self._ai_adaylari(12)

        sonuc = self._calistir(upgrade_batch=12)

        self.assertEqual(len(self.paket_cagrilar), 3, 'Dorduncu paket gonderilmemeli')
        self.assertEqual((sonuc['upgraded'], sonuc['failed']), (1, 8))
        self.assertEqual(sonuc['sections']['ai']['stopped_reason'], 'ardisik_icerik_hatasi')
        denemeler = sorted(AINewsEntry.objects.values_list('translation_attempts', flat=True))
        self.assertEqual(denemeler, [0] * 4 + [1] * 8)

    def test_tamami_reddedilen_paket_yalniz_siniri_kadar_sayilir(self):
        """15 kayitlik paket tamamen reddedilirse 5'te sayim durur; kalan 10 deneme almaz (kalan adaylar sayilmaz)."""
        self.gemini_ayarla(paket=lambda k: _ceviri_paketi(k, reddet=set(k)))
        self._ai_adaylari(15)

        sonuc = self._calistir(upgrade_batch=15)

        self.assertEqual(len(self.paket_cagrilar), 1)
        self.assertEqual((sonuc['upgraded'], sonuc['failed']), (0, 5))
        self.assertEqual(sonuc['sections']['ai']['stopped_reason'], 'ardisik_icerik_hatasi')
        denemeler = sorted(AINewsEntry.objects.values_list('translation_attempts', flat=True))
        self.assertEqual(denemeler, [0] * 10 + [1] * 5)

    def test_karisik_paketta_kabul_seriyi_sifirlar_sinir_sonrasi_sayilmaz(self):
        """3 red, 1 kabul, 6 red: 3 sayilir, kabul yazilir ve seriyi sifirlar, sonraki 5 sayilir, sonuncusu sayilmaz."""
        self.paket_siniri(adet=10)
        reddedilen = {'k0', 'k1', 'k2'} | {f'k{i}' for i in range(4, 10)}
        self.gemini_ayarla(paket=lambda k: _ceviri_paketi(k, reddet=reddedilen))
        kayitlar = self._ai_adaylari(10)

        sonuc = self._calistir(upgrade_batch=10)

        self.assertEqual(len(self.paket_cagrilar), 1)
        self.assertEqual((sonuc['upgraded'], sonuc['failed']), (1, 8))
        self.assertEqual(sonuc['sections']['ai']['stopped_reason'], 'ardisik_icerik_hatasi')
        # Aday sirasi bilinmediginden kimlikle degil dagilimla dogrulanir
        kabul = [k for k in map(self._kayit, kayitlar) if k.translation_provider == 'gemini']
        self.assertEqual(len(kabul), 1)
        self.assertEqual(kabul[0].translation_attempts, 0)
        denemeler = sorted(k.translation_attempts for k in map(self._kayit, kayitlar))
        self.assertEqual(denemeler, [0, 0] + [1] * 8)


class GeminiAdayiTests(SimpleTestCase):
    """_gemini_adayi_mi: CVE icin CVSS >= 7.0 ya da KEV; diger bolumlerde her kayit."""

    def test_esik_ve_kev(self):
        from news.retranslate import CVE_GEMINI_ESIGI, _gemini_adayi_mi
        self.assertEqual(CVE_GEMINI_ESIGI, 7.0)
        durumlar = [
            (None, None, False), (6.9, None, False), (7.0, None, True), (9.8, None, True),
            (0.0, date(2026, 9, 1), True), (None, date(2026, 9, 1), True),
        ]
        for cvss, kev, beklenen in durumlar:
            with self.subTest(cvss=cvss, kev=kev):
                kayit = CVEEntry(cvss_score=cvss, kev_added_date=kev)
                self.assertIs(_gemini_adayi_mi('cve', kayit), beklenen)

    def test_diger_bolumler_hep_aday(self):
        from news.retranslate import _gemini_adayi_mi
        for ad in ('news', 'ai', 'sre', 'devtools', 'kubernetes'):
            with self.subTest(ad=ad):
                self.assertTrue(_gemini_adayi_mi(ad, AINewsEntry()))

    def test_aday_olmayan_cve_icin_istek_atilmaz(self):
        from news import retranslate
        kayit = CVEEntry(cvss_score=5.0, original_description='A remote attacker can read arbitrary files.')
        with mock.patch.object(gemini, 'hazir', lambda: True), \
             mock.patch.object(gemini, 'kaydi_cevir') as cevir:
            self.assertIsNone(retranslate._gemini_ile_cevir('cve', kayit))
        cevir.assert_not_called()


class BolumOncelikTests(SimpleTestCase):
    """Spec 2026-11-02 G3: once CVE, sonra haber, AI, SRE, DevTools, Kubernetes."""

    def test_cve_ilk_bolumdur(self):
        from news.retranslate import BOLUMLER
        self.assertEqual(BOLUMLER[0][0], 'cve')

    def test_bolum_sirasi_beklendigi_gibi(self):
        from news.retranslate import BOLUMLER
        self.assertEqual([ad for ad, *_ in BOLUMLER],
                         ['cve', 'news', 'ai', 'sre', 'devtools', 'kubernetes'])


class GeminiBolumAdiTests(TestCase):
    """Bolum adi kaydi_cevir'e log icin gecer; hazir() bolumden bagimsizdir."""

    def test_kaydi_cevir_bolum_adini_alir(self):
        from news import retranslate

        cve = CVEEntry.objects.create(
            cve_id='CVE-2026-9500', source='NVD',
            original_title='CVE-2026-9500 - Guvenlik Acigi',
            original_description='A remote attacker can read arbitrary files from the server.',
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/9500',
            turkish_title='CVE-2026-9500 - Guvenlik Acigi',
            turkish_description='Eski LibreTranslate cevirisi.', cvss_score=9.8,
            needs_translation=False, translation_provider='libretranslate')

        with mock.patch.object(gemini, 'hazir', return_value=True) as hazir, \
             mock.patch.object(gemini, 'kaydi_cevir',
                               return_value={'description': 'Yeni Gemini cevirisi.'}) as cevir:
            retranslate._gemini_ile_cevir('cve', cve)

        self.assertTrue(hazir.called, 'gemini.hazir cagrilmaliydi')
        self.assertTrue(all(c.args == () and c.kwargs == {} for c in hazir.call_args_list),
                        'gemini.hazir parametresiz cagrilmali')
        self.assertEqual(cevir.call_args.args[1], 'cve',
                         'gemini.kaydi_cevir bolum adiyla cagrilmaliydi (log)')


class YukseltmeHttpHatasiTests(TestCase):
    """Gercek gemini.kaydi_cevir, sahte HTTP: sistemik 4xx kayitlari kuyruktan dusurmemeli."""

    def setUp(self):
        super().setUp()
        ayar = override_settings(GEMINI_API_KEY='test-anahtar')
        ayar.enable()
        self.addCleanup(ayar.disable)
        for hedef, deger in (('_gate', tu._LocalGate()), ('_butce', gemini._LocalButce()),
                             ('GEMINI_MIN_INTERVAL', 0.0)):
            yama = mock.patch.object(gemini, hedef, deger)
            yama.start()
            self.addCleanup(yama.stop)
        self.kayitlar = [_libre_kaydi(f'http-{i}', baslik=f'Story number {i + 1} published') for i in range(2)]

    def _yukselt(self, durum, metin='{"error": {}}', sonuc=None):
        from news import retranslate
        yanit = mock.Mock(status_code=durum, text=metin)
        sonuc = {'stopped_reason': None, 'sections': {}} if sonuc is None else sonuc
        with mock.patch('news.gemini.requests.post', return_value=yanit) as post:
            yukseltilen, basarisiz = retranslate._yukselt('ai', AINewsEntry, 10, sonuc)
        return yukseltilen, basarisiz, post

    def test_400_gecersiz_anahtar_yukseltmede_deneme_saymaz_ve_asama_durur(self):
        """Google gecersiz anahtari 401 degil 400 + API_KEY_INVALID ile doner (bulgu 1)."""
        from news.tests.test_gemini import GECERSIZ_ANAHTAR_400
        yukseltilen, basarisiz, post = self._yukselt(400, metin=GECERSIZ_ANAHTAR_400)

        self.assertEqual((yukseltilen, basarisiz), (0, 0))
        self.assertEqual(post.call_count, 1, 'Devre kesici acildi; ikinci kayit denenmemeli')
        for kayit in self.kayitlar:
            kayit.refresh_from_db()
            self.assertEqual(kayit.translation_attempts, 0)
            self.assertEqual(kayit.translation_provider, 'libretranslate')

    def test_ardisik_icerik_hatasi_sinirinda_bolum_asamasi_durur(self):
        """Ayni turda bir bolumde 5 ardisik icerik hatasi: kalan adaylar denenmez, sayilmaz
        (taninmayan sistemik bir hata butun birikimi deneme tavanina itmesin)."""
        from news import retranslate
        self.kayitlar += [_libre_kaydi(f'http-ek-{i}', baslik=f'Story number {i} published')
                          for i in range(3, 8)]
        self.assertEqual(len(self.kayitlar), 7)
        sonuc = {'stopped_reason': None, 'sections': {}}
        yukseltilen, basarisiz, post = self._yukselt(400, sonuc=sonuc)

        self.assertEqual(retranslate.ARDISIK_HATA_SINIRI, 5)
        self.assertEqual((yukseltilen, basarisiz), (0, 5))
        # Kayda ozgu 400 (devre kesici yok) paketi ikiye boler: 7 -> 4+3 -> 2+2 -> 1+1 ...; tek kayitta
        # icerik hatasi. 5. tek kayit reddine kadar 11 istek (4xx butceyi geri alir).
        self.assertEqual(post.call_count, 11)
        denemeler = sorted(AINewsEntry.objects.values_list('translation_attempts', flat=True))
        self.assertEqual(denemeler, [0, 0, 1, 1, 1, 1, 1])
        self.assertEqual(sonuc['sections']['ai']['stopped_reason'], 'ardisik_icerik_hatasi')
        self.assertIsNone(sonuc['stopped_reason'], 'tur duzeyi sebep ezilmemeli')

    def test_basari_ardisik_hata_serisini_sifirlar(self):
        from news import retranslate
        self.kayitlar += [_libre_kaydi(f'seri-{i}', baslik=f'Story number {i} published') for i in range(3, 8)]
        ret, ok = gemini.PaketSonucu(reddedilen={'k0'}), gemini.PaketSonucu(ceviriler={'k0': {'title': 'Başarılı'}})
        sira = iter([ret, ret, ret, ret, ok, ret, ret])
        sonuc = {'stopped_reason': None, 'sections': {}}
        with mock.patch.object(gemini, 'hazir', return_value=True), \
                mock.patch.object(gemini, 'GEMINI_BATCH_MAX', 1), \
                mock.patch.object(gemini, 'paket_cevir', side_effect=lambda *a, **k: next(sira)):
            yukseltilen, basarisiz = retranslate._yukselt('ai', AINewsEntry, 10, sonuc)

        self.assertEqual((yukseltilen, basarisiz), (1, 6))
        self.assertNotIn('ai', sonuc['sections'])

    def test_ardisik_hata_sebebi_tur_sonucunda_bolum_satirinda_kalir(self):
        from news import retranslate
        self.kayitlar += [_libre_kaydi(f'tur-{i}', baslik=f'Story number {i} published') for i in range(3, 8)]
        redis_client = test_redis_client()
        prefix = f'test-retranslate-{uuid.uuid4().hex}'
        yanit = mock.Mock(status_code=400, text='{"error": {"status": "INVALID_ARGUMENT"}}')
        with mock.patch.object(tu, 'herhangi_saglayici_hazir', return_value=False), \
                mock.patch('news.gemini.requests.post', return_value=yanit) as post:
            sonuc = retranslate.retranslate_pending(redis_client=redis_client, prefix=prefix, upgrade_batch=10,
                                                    tur=retranslate._Tur(pay=100, baslangic=0))

        self.assertEqual(post.call_count, 11)  # paket bolunmesi: bkz. ardisik_icerik_hatasi_sinirinda
        self.assertEqual(sonuc['sections']['ai'], {'translated': 0, 'failed': 5, 'upgraded': 0,
                                                   'stopped_reason': 'ardisik_icerik_hatasi'})
        self.assertNotIn('stopped_reason', sonuc['sections']['news'])
        self.assertIsNone(sonuc['stopped_reason'])

    def test_401_yukseltmede_deneme_saymaz_ve_asama_durur(self):
        yukseltilen, basarisiz, post = self._yukselt(401)

        self.assertEqual((yukseltilen, basarisiz), (0, 0))
        self.assertEqual(post.call_count, 1, 'Devre kesici acildi; ikinci kayit denenmemeli')
        for kayit in self.kayitlar:
            kayit.refresh_from_db()
            self.assertEqual(kayit.translation_attempts, 0)
            self.assertEqual(kayit.translation_provider, 'libretranslate')

    def test_400_yukseltmede_kayit_basina_deneme_sayar(self):
        yukseltilen, basarisiz, post = self._yukselt(400)

        self.assertEqual((yukseltilen, basarisiz), (0, 2))
        self.assertEqual(post.call_count, 3, 'Iki kayitlik paket reddedilir, sonra tek tek denenir')
        for kayit in self.kayitlar:
            kayit.refresh_from_db()
            self.assertEqual(kayit.translation_attempts, 1)


class SilinenKayitTests(TransactionTestCase):
    """Tur ortasinda silinen kayit tum turu dusurmemeli (2026-09-18 vakasi).

    Eszamanli bir temizleme (views.clear_cve_cache) retranslate'in elindeki
    kaydi silince kayit.save(update_fields=...) 0 satir gunceller ve Django
    DatabaseError atar; bu istisna tum retranslate turunu comertti ve o turda
    diger bolumler hic yukseltme almadi.

    TransactionTestCase ZORUNLU, TestCase ile calismaz: Model.save() kendi icinde
    atomic(savepoint=False) kullanir ve iceride istisna olusunca KUSATAN transaction
    'rollback gerekiyor' diye isaretlenir. TestCase her testi bir atomic bloga
    sardigi icin, istisnadan sonraki ilk sorgu TransactionManagementError atar ve
    dongu devam edemez. Uretimde retranslate hicbir atomic blok icinde degildir
    (dogrulandi: retranslate.py, tasks.py ve settings.py'de atomic/ATOMIC_REQUESTS
    yok), yani save()'in kendi atomic'i en distaki blok olur ve dongu devam eder.
    TransactionTestCase bu autocommit kosulunu birebir yansitir.
    """

    def _cve(self, no, saglayici='libretranslate'):
        return CVEEntry.objects.create(
            cve_id=f'CVE-2026-{no}', source='NVD',
            original_title=f'CVE-2026-{no}',
            original_description='A remote attacker can read arbitrary files from the server.',
            turkish_description='Eski LibreTranslate cevirisi.', cvss_score=9.8,
            published_date=date(2026, 9, 12), link=f'https://ornek.test/cve/{no}',
            needs_translation=False, translation_provider=saglayici)

    def test_yaz_silinmis_kayitta_istisna_atmaz_false_doner(self):
        from news import retranslate
        kayit = self._cve('9701')
        CVEEntry.objects.filter(pk=kayit.pk).delete()  # tur ortasinda silindi

        sonuc = retranslate._yaz(kayit, {'turkish_description': 'Yeni ceviri.'}, 'gemini')

        self.assertFalse(sonuc, 'Silinmis kayitta _yaz False donmeli')

    def test_yaz_basarili_yazimda_true_doner(self):
        from news import retranslate
        kayit = self._cve('9702')

        sonuc = retranslate._yaz(kayit, {'turkish_description': 'Yeni ceviri.'}, 'gemini')

        self.assertTrue(sonuc)
        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'gemini')
        self.assertEqual(kayit.turkish_description, 'Yeni ceviri.')

    def test_yaz_gecici_veritabani_hatasini_yutmaz(self):
        """database is locked gibi OperationalError altyapi hatasidir; yukari cikmali."""
        from django.db import OperationalError
        from news import retranslate
        kayit = self._cve('9703')

        with mock.patch.object(CVEEntry, 'save', side_effect=OperationalError('database is locked')):
            with self.assertRaises(OperationalError):
                retranslate._yaz(kayit, {'turkish_description': 'Yeni ceviri.'}, 'gemini')

    def test_yukselt_silinen_kaydi_atlayip_turu_surdurur(self):
        """Asil vaka: tur ortasinda silinen kayit turu dusurmemeli, sonraki kayit yukselmeli."""
        from news import retranslate
        # Yukseltme en yeniden baslar: once silinecek kayit (daha yeni) islenir
        ikinci = self._cve('9705')
        birinci = self._cve('9704')

        def sahte_paket(kayitlar, bolum=None):
            CVEEntry.objects.filter(pk=birinci.pk).delete()  # istek surerken eszamanli temizleme
            return gemini.PaketSonucu(ceviriler={k: {'description': 'Gemini çevirisi.'} for k in kayitlar})

        sonuc = {'stopped_reason': None}
        with mock.patch.object(gemini, 'hazir', lambda: True), \
             mock.patch.object(gemini, 'paket_cevir', sahte_paket):
            yukseltilen, basarisiz = retranslate._yukselt('cve', CVEEntry, 10, sonuc)

        self.assertEqual(yukseltilen, 1, 'Silinen kayit sayilmamali, ikinci kayit yukselmeli')
        self.assertEqual(basarisiz, 0, 'Silinen kayit icerik hatasi degildir')
        ikinci.refresh_from_db()
        self.assertEqual(ikinci.translation_provider, 'gemini')


class SahteCevirmen:
    """kayit_cevirmenleri arayuzunu (name, onek, hazir, kaydi_cevir, paket_cevir) ag olmadan uygular.

    hazir: sabit bool ya da parametresiz fonksiyon. cevap: alanlari alan fonksiyon ya da None (reddeder).
    paket: PaketSonucu listesi (sirayla) ya da kayitlari alan fonksiyon; verilmezse her kayda cevap
    uygulanir. Kayitlar: paket_cagrilar (kimlik -> alanlar), tekil_cagrilar."""

    def __init__(self, name, onek=None, hazir=True, cevap=None, paket=None):
        self.name = name
        self.onek = onek or name
        self.log_adi = name
        self._hazir = hazir
        self.cevap = cevap if cevap is not None else (
            lambda alanlar: {ad: f'{name.upper()} {metin}' for ad, metin in alanlar.items()})
        self._senaryo = iter(paket) if isinstance(paket, (list, tuple)) else None
        self._paket = paket
        self.paket_cagrilar, self.tekil_cagrilar = [], []

    def hazir(self):
        return self._hazir() if callable(self._hazir) else self._hazir

    def kaydi_cevir(self, alanlar, bolum=None):
        self.tekil_cagrilar.append(dict(alanlar))
        return self.cevap(alanlar)

    def paket_cevir(self, kayitlar, bolum=None):
        if not self.hazir():
            return gemini.PaketSonucu(istek_hatasi=True)
        self.paket_cagrilar.append({kimlik: dict(alanlar) for kimlik, alanlar in kayitlar.items()})
        if self._senaryo is not None:
            return next(self._senaryo)
        if callable(self._paket):
            return self._paket(kayitlar)
        sonuc = gemini.PaketSonucu()
        for kimlik, alanlar in kayitlar.items():
            ceviri = self.cevap(alanlar)
            if ceviri is None:
                sonuc.reddedilen.add(kimlik)
            else:
                sonuc.ceviriler[kimlik] = ceviri
        return sonuc

    @property
    def cagrildi(self):
        return bool(self.paket_cagrilar or self.tekil_cagrilar)


def _reddet(alanlar):
    return None


class YedekZincirTests(GeminiSahteMixin, SaglayiciZinciriMixin, RetranslateTestBase):
    """Spec 2026-11-02 G6 (PR-C): retranslate kayit duzeyi yedek zinciri kullanir. Yedekler yalniz birincil
    Gemini gercekten kullanilamazken (gunluk butce / devre kesici) devreye girer; tur payi bitmesi degil."""

    def setUp(self):
        super().setUp()
        self.libre = self.saglayicilari_ayarla(SahteSaglayici('libretranslate', _libre))[0]

    def yedekleri_ayarla(self, *cevirmenler):
        from news import kayit_cevirmenleri
        yama = mock.patch.object(kayit_cevirmenleri, 'YEDEKLER', tuple(cevirmenler))
        yama.start()
        self.addCleanup(yama.stop)
        return cevirmenler

    def _tur(self, pay):
        from news import retranslate
        return retranslate._Tur(pay=pay, baslangic=gemini.butce_kullanimi())

    def _kayit(self, kayit):
        kayit.refresh_from_db()
        return kayit

    def _bekleyen(self, slug='yb'):
        return self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', slug)

    def _adaylar(self, adet, onek='yz'):
        return [_libre_kaydi(f'{onek}-{i}', baslik=f'Story number {i + 1} published') for i in range(adet)]

    # --- _cevirmen_sec ---

    def test_cevirmen_sec_kurallari(self):
        from news import retranslate
        openrouter, deepl = self.yedekleri_ayarla(SahteCevirmen('openrouter'), SahteCevirmen('deepl'))
        for asama in ('bekleyen', 'yukseltme'):
            with self.subTest(asama=asama):
                self.gemini_ayarla(_gemini_cevirisi)
                self.assertIs(retranslate._cevirmen_sec(self._tur(3), asama), gemini.BIRINCIL)
                self.assertIsNone(retranslate._cevirmen_sec(self._tur(0), asama),
                                  'Pay bitti, birincil hazir: tur bekler, yedege gidilmez')
                self.gemini_ayarla(_gemini_cevirisi, butce=False)
                self.assertIs(retranslate._cevirmen_sec(self._tur(0), asama), openrouter)
                self.gemini_ayarla(_gemini_cevirisi, hazir=False)
                openrouter._hazir = False
                self.assertIs(retranslate._cevirmen_sec(self._tur(3), asama), deepl)
                deepl._hazir = False
                self.assertIsNone(retranslate._cevirmen_sec(self._tur(3), asama))
                openrouter._hazir = deepl._hazir = True

    # --- Brief testleri ---

    def test_birincil_hazirsa_yedek_cagrilmaz(self):
        openrouter, deepl = self.yedekleri_ayarla(SahteCevirmen('openrouter'), SahteCevirmen('deepl'))
        self.gemini_ayarla(_gemini_cevirisi)
        bekleyen = self._bekleyen()
        aday = self._adaylar(1)[0]

        self._calistir()

        self.assertFalse(openrouter.cagrildi or deepl.cagrildi)
        self.assertEqual(self._kayit(bekleyen).translation_provider, 'gemini')
        self.assertEqual(self._kayit(aday).translation_provider, 'gemini')

    def test_birincil_butcesi_bitince_openrouter_kullanilir(self):
        openrouter, deepl = self.yedekleri_ayarla(SahteCevirmen('openrouter'), SahteCevirmen('deepl'))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        bekleyen = self._bekleyen()
        adaylar = self._adaylar(2)

        sonuc = self._calistir()

        self.assertEqual(self.gemini_cagrilar, [])
        self.assertFalse(deepl.cagrildi)
        self.assertEqual(len(openrouter.tekil_cagrilar), 1, 'Bekleyen kayit duzeyinde gider')
        self.assertEqual(len(openrouter.paket_cagrilar), 1, 'Yukseltme paketli gider')
        bekleyen = self._kayit(bekleyen)
        self.assertEqual(bekleyen.translation_provider, 'openrouter')
        self.assertFalse(bekleyen.needs_translation)
        self.assertEqual(bekleyen.turkish_title, 'OPENROUTER Farmers adopt new sensors')
        for kayit in map(self._kayit, adaylar):
            self.assertEqual(kayit.translation_provider, 'openrouter')
            self.assertEqual(kayit.turkish_title, 'OPENROUTER ' + kayit.original_title)
        self.assertEqual(sonuc['by_provider'].get('openrouter'), 1)
        self.assertEqual(sonuc['upgraded'], 2)
        self.assertEqual(self.libre.cagrilar, [])

    def test_birincil_devre_kesicisi_acikken_yedek_kullanilir(self):
        openrouter, = self.yedekleri_ayarla(SahteCevirmen('openrouter'))
        self.gemini_ayarla(_gemini_cevirisi, hazir=False)
        aday = self._adaylar(1)[0]

        self._calistir()

        self.assertEqual(self._kayit(aday).translation_provider, 'openrouter')

    def test_openrouter_da_yoksa_deepl(self):
        openrouter, deepl = self.yedekleri_ayarla(SahteCevirmen('openrouter', hazir=False), SahteCevirmen('deepl'))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        bekleyen = self._bekleyen()
        aday = self._adaylar(1)[0]

        sonuc = self._calistir()

        self.assertFalse(openrouter.cagrildi)
        self.assertEqual(self._kayit(bekleyen).translation_provider, 'deepl')
        self.assertEqual(self._kayit(aday).translation_provider, 'deepl')
        self.assertEqual(sonuc['by_provider'].get('deepl'), 1)

    def test_tur_payi_bitince_yedek_cagrilmaz(self):
        openrouter, deepl = self.yedekleri_ayarla(SahteCevirmen('openrouter'), SahteCevirmen('deepl'))
        self.gemini_ayarla(_gemini_cevirisi, istek_say=True)
        bekleyen = self._bekleyen()
        aday = self._adaylar(1)[0]

        sonuc = self._calistir(tur=self._tur(0))

        self.assertEqual(self.gemini_cagrilar, [])
        self.assertFalse(openrouter.cagrildi or deepl.cagrildi, 'Pay bitmesi yedekleri tetiklemez (G6)')
        self.assertEqual(self._kayit(bekleyen).translation_provider, 'libretranslate')
        aday = self._kayit(aday)
        self.assertEqual(aday.translation_provider, 'libretranslate')
        self.assertEqual(aday.translation_attempts, 0)
        self.assertEqual(sonuc['stopped_reason'], 'gemini_tur_payi')

    def test_orta_cve_yedege_gitmez(self):
        openrouter, deepl = self.yedekleri_ayarla(SahteCevirmen('openrouter'), SahteCevirmen('deepl'))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        bekleyen = _cve_kaydi('7101', cvss=5.0, needs_translation=True)
        skorsuz = _cve_kaydi('7102', needs_translation=True)
        orta_aday = _cve_kaydi('7103', cvss=6.9)

        self._calistir()

        self.assertFalse(openrouter.cagrildi or deepl.cagrildi, 'G1 disi CVE hicbir ucretsiz saglayiciya gitmez')
        self.assertEqual(self._kayit(bekleyen).translation_provider, 'libretranslate')
        self.assertEqual(self._kayit(skorsuz).translation_provider, 'libretranslate')
        orta_aday = self._kayit(orta_aday)
        self.assertEqual(orta_aday.translation_provider, 'libretranslate')
        self.assertEqual(orta_aday.translation_attempts, 0)

    def test_yuksek_cve_yedege_gider(self):
        openrouter, = self.yedekleri_ayarla(SahteCevirmen('openrouter'))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        kayit = _cve_kaydi('7104', cvss=9.8)

        self._calistir()

        self.assertEqual(self._kayit(kayit).translation_provider, 'openrouter')

    def test_yedek_cevirisi_sonradan_yukseltilmez(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayitlar = self._adaylar(2)
        for kayit, saglayici in zip(kayitlar, ('openrouter', 'deepl')):
            type(kayit).objects.filter(pk=kayit.pk).update(translation_provider=saglayici)

        sonuc = self._calistir()

        self.assertEqual(self.gemini_cagrilar, [])
        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual([self._kayit(k).translation_provider for k in kayitlar], ['openrouter', 'deepl'])

    def test_yedegin_reddettigi_kayit_ayni_turda_baska_yedege_gitmez(self):
        """Yonetici karari: bir turda reddedilen kayit o tur baska cevirmene gitmez; red bir kez sayilir."""
        def cevap(alanlar):
            if alanlar.get('title') == 'Story number 1 published':
                return None
            return {ad: 'OPENROUTER ' + metin for ad, metin in alanlar.items()}

        openrouter, deepl = self.yedekleri_ayarla(SahteCevirmen('openrouter', cevap=cevap), SahteCevirmen('deepl'))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        adaylar = self._adaylar(2)

        sonuc = self._calistir()

        self.assertFalse(deepl.cagrildi)
        self.assertEqual(len(openrouter.paket_cagrilar), 1)
        reddedilen, yazilan = map(self._kayit, adaylar)
        self.assertEqual(reddedilen.translation_provider, 'libretranslate')
        self.assertEqual(reddedilen.translation_attempts, 1)
        self.assertEqual(yazilan.translation_provider, 'openrouter')
        self.assertEqual((sonuc['upgraded'], sonuc['failed']), (1, 1))

    def test_yedegin_reddettigi_bekleyen_libre_ile_cevrilir(self):
        openrouter, deepl = self.yedekleri_ayarla(SahteCevirmen('openrouter', cevap=_reddet), SahteCevirmen('deepl'))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        bekleyen = self._bekleyen()

        self._calistir()

        self.assertEqual(len(openrouter.tekil_cagrilar), 1)
        self.assertFalse(deepl.cagrildi)
        self.assertEqual(self._kayit(bekleyen).translation_provider, 'libretranslate')

    def test_yedegin_reddettigi_bekleyen_zincir_kapaliyken_icerik_hatasi(self):
        self.libre.hazir = False
        openrouter, = self.yedekleri_ayarla(SahteCevirmen('openrouter', cevap=_reddet))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        bekleyen = self._bekleyen()

        sonuc = self._calistir()

        bekleyen = self._kayit(bekleyen)
        self.assertTrue(bekleyen.needs_translation)
        self.assertEqual(bekleyen.translation_attempts, 1)
        self.assertFalse(sonuc['stopped'])

    def test_yedek_istek_hatasinda_sonraki_yedek_ayni_paketi_alir(self):
        """Istek duzeyi hata yedegi kapattiysa ayni paket siradakine gider; hicbir kayit sayilmaz."""
        durum = {'hazir': True}

        def kapanir(kayitlar):
            durum['hazir'] = False  # devre kesici acildi
            return gemini.PaketSonucu(istek_hatasi=True)

        openrouter, deepl = self.yedekleri_ayarla(
            SahteCevirmen('openrouter', hazir=lambda: durum['hazir'], paket=kapanir), SahteCevirmen('deepl'))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        adaylar = self._adaylar(3)

        sonuc = self._calistir()

        self.assertEqual(len(openrouter.paket_cagrilar), 1)
        self.assertEqual(len(deepl.paket_cagrilar), 1)
        self.assertEqual(openrouter.paket_cagrilar[0], deepl.paket_cagrilar[0], 'Ayni paket yeniden denenmeli')
        self.assertEqual((sonuc['upgraded'], sonuc['failed']), (3, 0))
        for kayit in map(self._kayit, adaylar):
            self.assertEqual(kayit.translation_provider, 'deepl')
            self.assertEqual(kayit.translation_attempts, 0)

    def test_bekleyende_yedek_istek_hatasinda_sonraki_yedek_dener(self):
        durum = {'hazir': True}

        def kapanir(alanlar):
            durum['hazir'] = False
            return None

        openrouter, deepl = self.yedekleri_ayarla(
            SahteCevirmen('openrouter', hazir=lambda: durum['hazir'], cevap=kapanir), SahteCevirmen('deepl'))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        bekleyen = self._bekleyen()

        self._calistir()

        self.assertEqual(len(openrouter.tekil_cagrilar), 1)
        self.assertEqual(len(deepl.tekil_cagrilar), 1)
        bekleyen = self._kayit(bekleyen)
        self.assertEqual((bekleyen.translation_provider, bekleyen.translation_attempts), ('deepl', 0))

    def test_yedek_hazirken_istek_hatasi_paketi_boler(self):
        """Kayda ozgu 4xx (yedek hazir kaldi): bugunku gibi paket ikiye bolunur, yeniden secilmez."""
        senaryo = iter([gemini.PaketSonucu(istek_hatasi=True)])
        openrouter, deepl = self.yedekleri_ayarla(
            SahteCevirmen('openrouter', paket=lambda kayitlar: next(senaryo, None) or _ceviri_paketi(kayitlar)),
            SahteCevirmen('deepl'))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        adaylar = self._adaylar(2)

        self._calistir()

        self.assertEqual([len(p) for p in openrouter.paket_cagrilar], [2, 1, 1])
        self.assertFalse(deepl.cagrildi)
        # _ceviri_paketi 'GEMINI ' onekli metin verir; yazilan saglayici adi yine secilen cevirmenindir
        self.assertEqual([self._kayit(k).translation_provider for k in adaylar], ['openrouter', 'openrouter'])

    def test_son_yedek_de_kapaninca_asama_durur_kayit_sayilmaz(self):
        openrouter, = self.yedekleri_ayarla(
            SahteCevirmen('openrouter', paket=[gemini.PaketSonucu(istek_hatasi=True)]))
        openrouter._hazir = lambda: not openrouter.paket_cagrilar  # ilk istekten sonra kapanir
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        aday = self._adaylar(1)[0]

        sonuc = self._calistir()

        self.assertEqual(len(openrouter.paket_cagrilar), 1)
        self.assertEqual(sonuc['stopped_reason'], 'gemini_budget')
        aday = self._kayit(aday)
        self.assertEqual((aday.translation_provider, aday.translation_attempts), ('libretranslate', 0))

    def test_yedek_tur_payini_harcamaz(self):
        """Tur payi yalniz birincil icindir: yedek kendi sayaciyla sinirlidir (pay 1, uc paket)."""
        openrouter, = self.yedekleri_ayarla(SahteCevirmen('openrouter'))
        self.gemini_ayarla(_gemini_cevirisi, hazir=False)
        self.paket_siniri(adet=1)
        adaylar = self._adaylar(3)

        sonuc = self._calistir(tur=self._tur(1))

        self.assertEqual(len(openrouter.paket_cagrilar), 3)
        self.assertEqual(sonuc['upgraded'], 3)
        self.assertEqual({self._kayit(k).translation_provider for k in adaylar}, {'openrouter'})

    def test_yapisal_k8s_yedekte_tekil_yoldan_isaret_denetimli(self):
        govde = ('===SECTION: Features===\n---ITEM---\nAdds a flag.\n<<<PR#123|@kisi|sig>>>\n'
                 '---ITEM---\nFix x.\n<<<PR#124|@kisi2|sig2>>>')

        def cevap(alanlar):
            sonuc = {ad: 'OPENROUTER ' + metin for ad, metin in alanlar.items()}
            if 'v1.34.0' in alanlar.get('title', ''):
                sonuc['description'] = sonuc['description'].replace('<<<PR#124|@kisi2|sig2>>>', '', 1)
            return sonuc

        openrouter, = self.yedekleri_ayarla(SahteCevirmen('openrouter', cevap=cevap))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        kayitlar = []
        for surum in ('v1.33.0', 'v1.34.0'):
            kayitlar.append(KubernetesEntry.objects.create(
                source='GitHub Releases', category='release', version=surum,
                original_title=f'Kubernetes {surum} released', turkish_title=f'LIBRE Kubernetes {surum} released',
                original_description=govde, turkish_description='LIBRE ' + govde,
                link=f'https://ornek.test/k8s/yedek-{surum}', published_date=date(2026, 9, 12),
                needs_translation=False, translation_provider='libretranslate'))

        self._calistir()

        self.assertEqual(openrouter.paket_cagrilar, [], 'Yapisal K8s paketlenmez')
        self.assertEqual(len(openrouter.tekil_cagrilar), 2)
        saglam, bozuk = map(self._kayit, kayitlar)
        self.assertEqual(saglam.translation_provider, 'openrouter')
        self.assertEqual((bozuk.translation_provider, bozuk.translation_attempts), ('libretranslate', 1),
                         'Isaret kaybi her cevirmende icerik hatasidir')

    def test_anahtarsiz_kurulum_bugunku_gibi_calisir(self):
        """YEDEKLER gercek (anahtarlar bos): hicbiri hazir degil, HTTP yok; sonuc bugunku zincirle ayni."""
        from news import kayit_cevirmenleri, retranslate
        self.assertTrue(all(not c.hazir() for c in kayit_cevirmenleri.YEDEKLER))
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        bekleyen = self._bekleyen()
        aday = self._adaylar(1)[0]

        with mock.patch('news.gemini.requests.post') as post:
            self.assertIsNone(retranslate._cevirmen_sec(self._tur(5), 'yukseltme'))
            sonuc = self._calistir()

        post.assert_not_called()
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertEqual(self._kayit(bekleyen).translation_provider, 'libretranslate')
        aday = self._kayit(aday)
        self.assertEqual((aday.translation_provider, aday.translation_attempts), ('libretranslate', 0))
        self.assertEqual(sonuc['by_provider'], {'gemini': 0, 'libretranslate': 1})
        self.assertEqual(sonuc['stopped_reason'], 'gemini_budget')
        self.assertFalse(sonuc['stopped'])
