"""FetchRun modeli ve sinyal iskeleti (spec 2026-09-20-a4, bolum 3.1-3.3)."""
from django.test import TestCase
from django.utils import timezone

from news.models import FetchRun


class FetchRunModelTests(TestCase):

    def test_varsayilanlar(self):
        kayit = FetchRun.objects.create(section='cve', trigger='beat', status='running')

        self.assertEqual(kayit.fetched_count, 0)
        self.assertEqual(kayit.saved_count, 0)
        self.assertEqual(kayit.translation_failures, 0)
        self.assertEqual(kayit.total_after, 0)
        self.assertEqual(kayit.by_provider, {})
        self.assertEqual(kayit.stopped_reason, '')
        self.assertEqual(kayit.error, '')
        self.assertIsNone(kayit.finished_at)
        self.assertIsNotNone(kayit.started_at)

    def test_by_provider_sozluk_saklar(self):
        kayit = FetchRun.objects.create(section='retranslate', trigger='beat', status='success',
                                        by_provider={'gemini': 12, 'libretranslate': 3})
        kayit.refresh_from_db()

        self.assertEqual(kayit.by_provider['gemini'], 12)

    def test_siralama_en_yeni_once(self):
        eski = FetchRun.objects.create(section='cve', trigger='beat', status='success')
        FetchRun.objects.filter(pk=eski.pk).update(
            started_at=timezone.now() - timezone.timedelta(days=1))
        yeni = FetchRun.objects.create(section='cve', trigger='beat', status='success')

        self.assertEqual(list(FetchRun.objects.all())[0].pk, yeni.pk)

    def test_updated_at_alani_yok(self):
        """FetchRun v1 delta akisina girmez; updated_at tasimaz (spec 3.1)."""
        alanlar = {f.name for f in FetchRun._meta.get_fields()}

        self.assertNotIn('updated_at', alanlar)


class SinyalTests(TestCase):
    """Sinyal iskeleti (spec 3.3). Gercek Celery isi kuyruga atilmaz;
    sinyal islevleri dogrudan cagrilir."""

    def _sender(self, ad):
        """Celery sender nesnesinin sinyal icin gereken yuzu."""
        class SahteSender:
            name = ad
            request = {}
        return SahteSender()

    def test_prerun_running_satiri_acar(self):
        from news import fetch_runs
        fetch_runs.tur_basladi(sender=self._sender('news.tasks.fetch_cve_task'), task_id='t1')

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.section, 'cve')
        self.assertEqual(kayit.status, 'running')
        self.assertEqual(kayit.trigger, 'beat')
        self.assertIsNone(kayit.finished_at)

    def test_haritada_olmayan_task_satir_acmaz(self):
        from news import fetch_runs
        fetch_runs.tur_basladi(sender=self._sender('celery.backend_cleanup'), task_id='t2')

        self.assertEqual(FetchRun.objects.count(), 0)

    def test_postrun_sayaclari_yazar_ve_kapatir(self):
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t3')

        fetch_runs.tur_bitti(sender=sender, task_id='t3',
                             retval={'success': True, 'count': 7, 'fetched_count': 42,
                                     'translation_failures': 2})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'success')
        self.assertEqual(kayit.saved_count, 7)
        self.assertEqual(kayit.fetched_count, 42)
        self.assertEqual(kayit.translation_failures, 2)
        self.assertIsNotNone(kayit.finished_at)

    def test_yeni_kayit_yoksa_yine_basarili(self):
        """SPEC 1.3 REGRESYONU: fetched>0, saved=0 saglikli bir durumdur."""
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_sre_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t4')

        fetch_runs.tur_bitti(sender=sender, task_id='t4',
                             retval={'success': False, 'count': 0, 'fetched_count': 14,
                                     'translation_failures': 0})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'success',
                         'success=False ama hata yok: yeni kayit yok demektir, basarisizlik degil')
        self.assertEqual(kayit.fetched_count, 14)
        self.assertEqual(kayit.saved_count, 0)

    def test_donuste_error_anahtari_varsa_basarisiz(self):
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t5')

        fetch_runs.tur_bitti(sender=sender, task_id='t5',
                             retval={'success': False, 'error': 'disk I/O error'})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'failure')
        self.assertIn('disk I/O error', kayit.error)

    def test_task_failure_satiri_basarisiz_kapatir(self):
        from news import fetch_runs
        sender = self._sender('news.tasks.retranslate_pending_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t6')

        fetch_runs.tur_coktu(sender=sender, task_id='t6',
                             exception=ValueError('beklenmedik'))

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'failure')
        self.assertIn('beklenmedik', kayit.error)
        self.assertIsNotNone(kayit.finished_at)

    def test_bozuk_retval_sinyali_dusurmez(self):
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t7')

        fetch_runs.tur_bitti(sender=sender, task_id='t7', retval='sozluk degil')

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'success')
        self.assertEqual(kayit.saved_count, 0)

    def test_total_after_bolum_modelinden_sayilir(self):
        from datetime import date
        from news.models import CVEEntry
        from news import fetch_runs
        CVEEntry.objects.create(cve_id='CVE-2026-1', source='NVD', original_title='T',
                                original_description='D', published_date=date(2026, 9, 12),
                                link='https://ornek.test/1')
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t8')

        fetch_runs.tur_bitti(sender=sender, task_id='t8',
                             retval={'success': True, 'count': 1, 'fetched_count': 1})

        self.assertEqual(FetchRun.objects.get().total_after, 1)

    def test_retranslate_alan_eslemesi(self):
        """retranslate donusu farkli anahtarlar tasir (spec 3.4)."""
        from news import fetch_runs
        sender = self._sender('news.tasks.retranslate_pending_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t9')

        fetch_runs.tur_bitti(sender=sender, task_id='t9',
                             retval={'translated': 12, 'upgraded': 40, 'failed': 3,
                                     'stopped_reason': 'gemini_budget',
                                     'by_provider': {'gemini': 52, 'libretranslate': 0}})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.saved_count, 52, 'translated + upgraded')
        self.assertEqual(kayit.translation_failures, 3)
        self.assertEqual(kayit.fetched_count, 0, 'retranslate hicbir kaynaga gitmez')
        self.assertEqual(kayit.total_after, 0, 'retranslate tek bir bolume ait degil')
        self.assertEqual(kayit.stopped_reason, 'gemini_budget')
        self.assertEqual(kayit.by_provider['gemini'], 52)

    def test_trigger_header_dan_okunur(self):
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_cve_task')
        sender.request = {'fetchrun_trigger': 'admin'}

        fetch_runs.tur_basladi(sender=sender, task_id='t10')

        self.assertEqual(FetchRun.objects.get().trigger, 'admin')

    def test_uzun_hata_kisaltilir(self):
        """spec bolum 5: error metni ilk 2000 karaktere kisaltilir."""
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t11')

        fetch_runs.tur_bitti(sender=sender, task_id='t11',
                             retval={'success': False, 'error': 'x' * 5000})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'failure')
        self.assertEqual(len(kayit.error), 2000)

    def test_sinyaller_gercekten_bagli(self):
        """Sinyal fonksiyonlari sadece dogrudan cagrilabilir olmakla kalmaz,
        Celery'nin sinyal alicilari listesine de kayitli olmalidir. apps.py'daki
        'from . import fetch_runs' satiri veya @connect dekoratoru silinirse
        bu test kirilir; diger tum testler dogrudan cagri yaptigi icin
        boyle bir silmeyi yakalayamaz."""
        from celery.signals import task_failure, task_postrun, task_prerun
        from news import fetch_runs

        prerun_alicilar = [alici() for _, alici in task_prerun.receivers]
        self.assertIn(fetch_runs.tur_basladi, prerun_alicilar)

        postrun_alicilar = [alici() for _, alici in task_postrun.receivers]
        self.assertIn(fetch_runs.tur_bitti, postrun_alicilar)

        failure_alicilar = [alici() for _, alici in task_failure.receivers]
        self.assertIn(fetch_runs.tur_coktu, failure_alicilar)

    def test_coktu_sonrasi_bitti_satiri_yeniden_acmaz(self):
        """Celery gercek bir hatada once task_failure sonra task_postrun gonderir.
        _kapat icindeki _acik_turlar.pop(...) None donmesi, postrun'un satiri
        'success' olarak yeniden acmasini engelleyen tek mekanizmadir (spec 3.3)."""
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t-siralama')

        fetch_runs.tur_coktu(sender=sender, task_id='t-siralama',
                             exception=ValueError('beklenmedik cokme'))
        fetch_runs.tur_bitti(sender=sender, task_id='t-siralama',
                             retval={'success': True, 'count': 5})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'failure')
        self.assertEqual(kayit.saved_count, 0)

    def test_basarisiz_durumlu_postrun_basarili_yazmaz(self):
        """2026-10-21: FetchRun 1086 sert sure sinirinda olduruldu ama 'success' kaydedildi. Postrun
        state=FAILURE ve sozluk olmayan retval (istisna) ile geldiginde basarisizlik yazilmali."""
        from news import fetch_runs
        sender = self._sender('news.tasks.retranslate_pending_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t-durum')

        fetch_runs.tur_bitti(sender=sender, task_id='t-durum',
                             retval=RuntimeError('alt surec kesildi'), state='FAILURE')

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'failure')
        self.assertIn('alt surec kesildi', kayit.error)

    def _eski_running(self, bolum, saniye_once):
        kayit = FetchRun.objects.create(section=bolum, trigger='beat', status='running')
        FetchRun.objects.filter(pk=kayit.pk).update(
            started_at=timezone.now() - timezone.timedelta(seconds=saniye_once))
        return kayit

    def test_sert_sure_siniri_ana_surecte_satiri_kapatir(self):
        """Sert sinirda task_failure ana surecte gelir; task_id -> satir haritasi alt surecteydi.
        Sure sinirini asmis en eski running satiri kapatilir; ayni bolumde yeni baslamis tur dokunulmaz."""
        from billiard.exceptions import TimeLimitExceeded
        from news import fetch_runs
        oldurulen = self._eski_running('retranslate', 1800)
        paralel = self._eski_running('retranslate', 60)

        fetch_runs.tur_coktu(sender=self._sender('news.tasks.retranslate_pending_task'),
                             task_id='ana-surecte-bilinmeyen', exception=TimeLimitExceeded(1800))

        oldurulen.refresh_from_db()
        paralel.refresh_from_db()
        self.assertEqual(oldurulen.status, 'failure')
        self.assertEqual(oldurulen.stopped_reason, 'time_limit')
        self.assertIn('TimeLimitExceeded', oldurulen.error)
        self.assertIsNotNone(oldurulen.finished_at)
        self.assertEqual(paralel.status, 'running')

    def test_bilinmeyen_task_baska_hatada_satira_dokunmaz(self):
        from news import fetch_runs
        kayit = self._eski_running('cve', 1800)

        fetch_runs.tur_coktu(sender=self._sender('news.tasks.fetch_cve_task'),
                             task_id='bilinmeyen', exception=ValueError('baska'))

        kayit.refresh_from_db()
        self.assertEqual(kayit.status, 'running')

    def test_eski_kayitlar_temizlenir(self):
        from news import fetch_runs
        eski = FetchRun.objects.create(section='cve', trigger='beat', status='success')
        FetchRun.objects.filter(pk=eski.pk).update(
            started_at=timezone.now() - timezone.timedelta(days=31))
        yeni = FetchRun.objects.create(section='cve', trigger='beat', status='success')

        silinen = fetch_runs.eski_kayitlari_temizle(gun=30)

        self.assertEqual(silinen, 1)
        self.assertTrue(FetchRun.objects.filter(pk=yeni.pk).exists())
        self.assertFalse(FetchRun.objects.filter(pk=eski.pk).exists())


class DonusSozlesmesiTests(TestCase):
    """Alti fetch task'i sinyalin ihtiyac duydugu sayaclari dondurmeli."""

    def test_cve_task_fetched_count_dondurur(self):
        from unittest import mock
        from news import tasks
        yama = mock.patch('news.tasks.MultiCVEScraper')
        scraper = yama.start()
        self.addCleanup(yama.stop)
        scraper.return_value.fetch_all_cves.return_value = []

        sonuc = tasks.fetch_cve_task(days=7)

        self.assertIn('fetched_count', sonuc)
        self.assertIn('translation_failures', sonuc)
        self.assertEqual(sonuc['fetched_count'], 0)
        self.assertIn('success', sonuc, 'mevcut alan korunmali')
        self.assertIn('count', sonuc, 'mevcut alan korunmali')

    def test_retranslate_task_eski_kayitlari_temizler(self):
        from unittest import mock
        from news import tasks
        eski = FetchRun.objects.create(section='cve', trigger='beat', status='success')
        FetchRun.objects.filter(pk=eski.pk).update(
            started_at=timezone.now() - timezone.timedelta(days=31))
        with mock.patch('news.retranslate.retranslate_pending', return_value={'translated': 0}):
            tasks.retranslate_pending_task()

        self.assertFalse(FetchRun.objects.filter(pk=eski.pk).exists())

    def test_fetched_count_drop_existing_oncesinde_sayilir(self):
        """SPEC 1.3'un ta kendisi: sre/devtools gunlerdir bu durumda -- kaynak
        calisiyor ama donen kayitlarin hepsi zaten DB'de (needs_translation=False),
        _drop_existing hepsini eliyor. fetched_count dedup'tan ONCE sayilmali,
        yoksa 'kaynak bozuk' (fetched=0) ile 'yeni kayit yok' (fetched>0, saved=0)
        ayirt edilemez. kaynaktan_gelen dedup'tan SONRA sayilsaydi bu test
        fetched_count icin 1 bekler, fakat gercek deger 0 olurdu (yalnizca 'yeni'
        hayatta kalirdi) -- ilk assertion o zaman patlardi."""
        from unittest import mock
        from datetime import date
        from news import tasks
        from news.models import CVEEntry

        CVEEntry.objects.create(
            cve_id='CVE-2026-5000', source='NVD', original_title='Var olan CVE',
            original_description='Aciklama', published_date=date(2026, 9, 1),
            link='https://ornek.test/mevcut', needs_translation=False,
        )

        var_olan = {'cve_id': 'CVE-2026-5000', 'source': 'NVD',
                    'original_title': 'Var olan CVE', 'original_description': 'Aciklama',
                    'published_date': date(2026, 9, 1), 'link': 'https://ornek.test/mevcut'}
        yeni = {'cve_id': 'CVE-2026-5001', 'source': 'NVD',
                'original_title': 'Yeni CVE', 'original_description': 'Aciklama',
                'published_date': date(2026, 9, 2), 'link': 'https://ornek.test/yeni'}

        yama = mock.patch('news.tasks.MultiCVEScraper')
        scraper_sinifi = yama.start()
        self.addCleanup(yama.stop)
        scraper = scraper_sinifi.return_value
        scraper.fetch_all_cves.return_value = [var_olan, yeni]
        # dedup sonrasi sadece 'yeni' kalir; process_cves onu oldugu gibi isler
        scraper.process_cves.side_effect = lambda cves: cves

        sonuc = tasks.fetch_cve_task(days=7)

        self.assertEqual(sonuc['fetched_count'], 2,
                         'kaynaktan 2 kayit geldi -- dedup ONCESI sayi')
        self.assertEqual(sonuc['count'], 1, 'sadece yeni olan kaydedildi')
        self.assertTrue(CVEEntry.objects.filter(cve_id='CVE-2026-5001').exists())


class TetikleyiciTests(TestCase):
    """Manuel tetiklenen isler FetchRun'da beat'ten ayirt edilebilmeli."""

    def test_v1_refresh_api_header_i_gecer(self):
        """news/api_v1/refresh.py::trigger(section, gate=None, ...) -> TriggerResult

        RefreshGate'in gercek imzasi (client, prefix='refresh') -- 'redis_client'
        diye bir parametresi yok. Gercek Redis'e bagimli olmamak icin gate'in
        kendisi tamamen sahte (Mock) kurulur: trigger() kilit/soguma/kayit
        adimlarinin hepsini bu sahte gate uzerinden gecer, boylece hicbir gercek
        Redis baglantisi kurulmaz ve hicbir gercek Celery isi kuyruga atilmaz.
        """
        from unittest import mock
        from news.api_v1 import refresh
        sahte_gorev = mock.Mock()
        sahte_kapi = mock.Mock()
        sahte_kapi.running_job.return_value = None
        sahte_kapi.cooldown_remaining.return_value = 0
        sahte_kapi.acquire.return_value = True

        with mock.patch.object(refresh, 'section_tasks', return_value={'cve': sahte_gorev}):
            sonuc = refresh.trigger('cve', gate=sahte_kapi)

        self.assertEqual(sonuc.status, 'started')
        self.assertTrue(sahte_gorev.apply_async.called)
        self.assertEqual(sahte_gorev.apply_async.call_args.kwargs.get('headers'),
                         {'fetchrun_trigger': 'api'})


class WorkerAcilisTests(TestCase):
    """worker_ready: tek worker iken onceki surecten kalan running satirlarini kapatir
    (2026-10-13). Host uykusundan sonra satir, ayni bolumun sonraki turuna kadar
    running kaliyordu (canlida 748: acilistan sonra 3 sa 43 dk)."""

    def setUp(self):
        from news import fetch_runs
        self.fr = fetch_runs
        self.addCleanup(setattr, fetch_runs, '_acilis_ani', fetch_runs._acilis_ani)

    def _sender(self, yanitlar=None, hata=None):
        """Celery consumer nesnesinin sinyal icin gereken yuzu: hostname + app.control.ping."""
        from types import SimpleNamespace
        from unittest import mock
        ping = mock.Mock(return_value=yanitlar if yanitlar is not None else [], side_effect=hata)
        sender = SimpleNamespace(hostname='celery@bu',
                                 app=SimpleNamespace(control=SimpleNamespace(ping=ping)))
        return sender, ping

    def _satir(self, dakika_once, status='running', section='news'):
        from datetime import timedelta
        kayit = FetchRun.objects.create(section=section, status=status)
        FetchRun.objects.filter(pk=kayit.pk).update(
            started_at=timezone.now() - timedelta(minutes=dakika_once))
        return kayit.pk

    def test_tek_worker_iken_onceki_running_satirlarini_kapatir(self):
        eski = self._satir(60)
        eski_cve = self._satir(30, section='cve')
        basarili = self._satir(60, status='success')
        self.fr.worker_baslatildi()
        yeni = self._satir(0)
        sender, ping = self._sender([{'celery@bu': {'ok': 'pong'}}])

        self.fr.worker_hazir(sender=sender)

        ping.assert_called_once_with(timeout=1.0)
        for pk in (eski, eski_cve):
            kayit = FetchRun.objects.get(pk=pk)
            self.assertEqual(kayit.status, 'failure')
            self.assertEqual(kayit.stopped_reason, 'interrupted')
            self.assertIn('Worker yeniden basladi', kayit.error)
            self.assertIsNotNone(kayit.finished_at)
        self.assertEqual(FetchRun.objects.get(pk=yeni).status, 'running',
                         'acilistan sonra baslayan telafi turu kapatilmamali')
        self.assertEqual(FetchRun.objects.get(pk=basarili).status, 'success')

    def test_baska_worker_yanit_verirse_hicbir_satiri_kapatmaz(self):
        eski = self._satir(60)
        self.fr.worker_baslatildi()
        sender, _ = self._sender([{'celery@bu': {'ok': 'pong'}},
                                  {'celery@diger': {'ok': 'pong'}}])

        self.fr.worker_hazir(sender=sender)

        self.assertEqual(FetchRun.objects.get(pk=eski).status, 'running')

    def test_ping_hata_verirse_sessizce_gecer(self):
        eski = self._satir(60)
        self.fr.worker_baslatildi()
        sender, _ = self._sender(hata=ConnectionError('broker yok'))

        self.fr.worker_hazir(sender=sender)  # istisna yukselmemeli

        self.assertEqual(FetchRun.objects.get(pk=eski).status, 'running')

    def test_acilis_ani_yoksa_hicbir_satiri_kapatmaz(self):
        eski = self._satir(60)
        self.fr._acilis_ani = None
        sender, ping = self._sender([{'celery@bu': {'ok': 'pong'}}])

        self.fr.worker_hazir(sender=sender)

        self.assertEqual(FetchRun.objects.get(pk=eski).status, 'running')
        ping.assert_not_called()
