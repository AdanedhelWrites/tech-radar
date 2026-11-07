"""2026-11-07 tam inceleme 2. dalga: ceviri dogrulugu. Ag erisimi yok."""
import re
from datetime import date
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

import scraper_multi
from news import ai_scraper, cve_scraper, devtools_scraper, gemini, k8s_scraper, retranslate, sre_scraper
from news import translation_utils as tu
from news.cve_basligi import baslik_ozeti, onekli_baslik, turkce_baslik
from news.management.commands.bozuk_cevirileri_isaretle import ingilizce_kalmis
from news.metin_temizle import temizle
from news.models import AINewsEntry, CVEEntry, KubernetesEntry
from news.tests.test_gemini import GeminiTestMixin, _yanit
from news.tests.test_translation import TranslationGateMixin
from news.tests.saglayici_yardimcilari import SahteSaglayici, SaglayiciZinciriMixin

_KOD = re.compile(r'XTRM\d{4}X')


def _sablonla(sablon):
    """Korunmus metindeki yer tutuculari sirayla sablona yerlestiren sahte saglayici cevabi."""
    return lambda korunmus: sablon.format(*_KOD.findall(korunmus))


class KodKorumaTests(TranslationGateMixin, SaglayiciZinciriMixin, TestCase):
    """Son islem geri konmus kodu bozuyordu: "os.environ.get" -> "Os. Environ.get", "blazer_usb.c" ->
    "blazer_usb. C" (LibreTranslate CVE'lerinde canli)."""

    def test_noktali_tanimlayici_ve_dosya_adi_bozulmaz(self):
        self.saglayicilari_ayarla(SahteSaglayici(
            'libretranslate', _sablonla('{} çağrısı {} dosyasında bellek sızdırır.')))
        sonuc = tu.translate_text('The os.environ.get call in blazer_usb.c leaks memory.')
        self.assertEqual(sonuc, 'os.environ.get çağrısı blazer_usb.c dosyasında bellek sızdırır.')

    def test_kod_parcasi_icindeki_noktalama_bozulmaz(self):
        self.saglayicilari_ayarla(SahteSaglayici('libretranslate', _sablonla('{} komutu çalışmaz. sonra dene')))
        sonuc = tu.translate_text('The `kubectl get pods. -A` command fails. try later')
        self.assertEqual(sonuc, '`kubectl get pods. -A` komutu çalışmaz. Sonra dene')

    def test_son_islem_geri_konmus_metinde_de_kodu_korur(self):
        # translate_long_text ve changelog cevirisi son islemi geri konmus metne de uygular
        metin = 'os.environ.get kullanılır. blazer_usb.c ve tribe_events.php dosyası `a. b` ile, e.g. burada.'
        self.assertEqual(tu.turkish_post_process(metin), metin)

    def test_cumle_sonu_duzeltmesi_suruyor(self):
        self.assertEqual(tu.turkish_post_process('İlk cümle bitti.İkinci cümle'), 'İlk cümle bitti. İkinci cümle')

    def test_noktali_tanimlayici_yer_tutucuyla_korunur(self):
        korunmus, sozluk = tu._protect_terms('Use node.js and example.com, not e.g. this.')
        self.assertEqual(sorted(sozluk.values()), ['example.com', 'node.js'])
        self.assertIn('e.g.', korunmus)


def _isle(uretec):
    tu.consume_translation_failures()
    kayitlar = list(uretec)
    return kayitlar, tu.consume_translation_failures()


class ScraperIstisnaDaliTests(SimpleTestCase):
    """Scraper'in ceviri istisnasi dali Ingilizceyi 'cevrildi' yaziyordu (K8s 428, AI 613): sayac artmali."""

    def _patlat(self, modul, adlar=('translate_text', 'translate_long_text')):
        for ad in adlar:
            yama = mock.patch.object(modul, ad, side_effect=RuntimeError('patladi'))
            yama.start()
            self.addCleanup(yama.stop)

    def test_ai(self):
        self._patlat(ai_scraper)
        kayitlar, hata = _isle(ai_scraper.MultiAINewsScraper().process_entries([
            {'title': 'T', 'description': 'D', 'link': 'https://ornek.test/a', 'date': '2026-11-07', 'source': 'S'}]))
        self.assertEqual((len(kayitlar), kayitlar[0]['turkish_description']), (1, 'D'))
        self.assertGreater(hata, 0)

    def test_kubernetes(self):
        self._patlat(k8s_scraper)
        kayitlar, hata = _isle(k8s_scraper.MultiK8sScraper().process_entries([
            {'original_title': 'T', 'original_description': 'D', 'source': 'CNCF Blog'}]))
        self.assertEqual(len(kayitlar), 1)
        self.assertGreater(hata, 0)

    def test_sre_ve_devtools(self):
        for modul, sinif in ((sre_scraper, sre_scraper.MultiSREScraper),
                             (devtools_scraper, devtools_scraper.MultiDevToolsScraper)):
            with self.subTest(modul.__name__), \
                    mock.patch.object(modul, 'translate_text', side_effect=RuntimeError('patladi')), \
                    mock.patch.object(modul, 'translate_long_text', side_effect=RuntimeError('patladi')):
                kayitlar, hata = _isle(sinif().process_entries([
                    {'title': 'T', 'description': 'D', 'link': 'https://ornek.test/s', 'date': '2026-11-07',
                     'source': 'S'}]))
                self.assertEqual(len(kayitlar), 1)
                self.assertGreater(hata, 0)

    def test_haber(self):
        self._patlat(scraper_multi)
        kayitlar, hata = _isle(scraper_multi.MultiSourceScraper().process_news([
            {'title': 'T', 'description': 'D', 'link': 'https://ornek.test/h', 'date': '2026-11-07',
             'original_date': '2026-11-07', 'source': 'S'}]))
        self.assertEqual(len(kayitlar), 1)
        self.assertGreater(hata, 0)

    def test_cve(self):
        self._patlat(cve_scraper, ('translate_text',))
        kayitlar, hata = _isle(cve_scraper.MultiCVEScraper().process_cves([
            {'cve_id': 'CVE-2026-1', 'original_title': 'CVE-2026-1 - Güvenlik Açığı',
             'original_description': 'A remote attacker can read arbitrary files from the server.'}]))
        self.assertEqual(len(kayitlar), 1)
        self.assertGreater(hata, 0)


ORIJINAL = 'A flaw in libfoo 2.4.1 (CVE-2026-1234) lets attackers call `parse_hdr()`; see https://ornek.test/a.'


class GeminiCapaTests(GeminiTestMixin, SimpleTestCase):
    """Tek kayit yolunda capa denetimi yoktu; model surumu ya da CVE numarasini degistirse ceviri yaziliyordu."""

    def test_capalari_tasiyan_ceviri_gecer(self):
        ceviri = ('libfoo 2.4.1 sürümündeki bir açık (CVE-2026-1234), saldırganların parse_hdr() çağırmasına '
                  'izin verir; bkz. https://ornek.test/a.')
        self._post(_yanit(govde={'description': ceviri}))
        self.assertEqual(gemini.kaydi_cevir({'description': ORIJINAL}), {'description': ceviri})

    def test_surumu_degisen_ceviri_reddedilir(self):
        ceviri = ('libfoo 2.4.2 sürümündeki bir açık (CVE-2026-1234), saldırganların `parse_hdr()` çağırmasına '
                  'izin verir; bkz. https://ornek.test/a.')
        self._post(_yanit(govde={'description': ceviri}))
        self.assertIsNone(gemini.kaydi_cevir({'description': ORIJINAL}))

    def test_cve_numarasi_kaybolan_ceviri_reddedilir(self):
        ceviri = ('libfoo 2.4.1 sürümündeki bir açık, saldırganların `parse_hdr()` çağırmasına izin verir; '
                  'bkz. https://ornek.test/a. Ayrıntı yok.')
        self._post(_yanit(govde={'description': ceviri}))
        self.assertIsNone(gemini.kaydi_cevir({'description': ORIJINAL}))

    def test_paket_icinde_tek_capasini_kaybeden_kayit_reddedilir(self):
        kaynak = {'k0': {'description': 'Upgrade to version 3.1.4 to fix the denial of service bug quickly.'},
                  'k1': {'description': 'Attackers can read arbitrary files from the server remotely.'}}
        self._post(_yanit(govde={
            'k0': {'description': 'Hizmet reddi hatasını hızla düzeltmek için yeni sürüme yükseltin lütfen.'},
            'k1': {'description': 'Saldırganlar sunucudaki keyfi dosyaları uzaktan okuyabilir.'}}))
        sonuc = gemini.paket_cevir(kaynak)
        self.assertEqual((set(sonuc.ceviriler), sonuc.reddedilen), ({'k1'}, {'k0'}))

    def test_talimat_terim_sozlugunu_tasir(self):
        for talimat in (gemini.SISTEM_TALIMATI, gemini.PAKET_TALIMATI):
            self.assertIn('vulnerability -> güvenlik açığı', talimat)
            self.assertIn('İngilizce bırak: commit', talimat)


class CveBaslikYardimcilariTests(SimpleTestCase):

    def test_baslik_ozeti(self):
        self.assertEqual(baslik_ozeti('CVE-2026-1', 'CVE-2026-1 - Güvenlik Açığı'), '')
        self.assertEqual(baslik_ozeti('CVE-2026-1', 'CVE-2026-1 - Aktif Sömürülen Zafiyet'), '')
        self.assertEqual(baslik_ozeti('CVE-2026-1', 'CVE-2026-1 - listmonk: SQL Injection'), 'listmonk: SQL Injection')
        self.assertEqual(baslik_ozeti('CVE-2026-1', 'Baska bicim'), '')

    def test_onekli_baslik_ayiraci_tek_bicime_getirir(self):
        for ceviri in ('SQL enjeksiyonu', 'CVE-2026-1 - SQL enjeksiyonu', 'CVE-2026-1 – SQL enjeksiyonu',
                       'cve-2026-1: SQL enjeksiyonu'):
            with self.subTest(ceviri):
                self.assertEqual(onekli_baslik('CVE-2026-1', ceviri), 'CVE-2026-1 - SQL enjeksiyonu')
        self.assertEqual(onekli_baslik('CVE-2026-1', '  '), '')

    def test_turkce_baslik(self):
        cevir = mock.Mock(return_value='SQL enjeksiyonu')
        self.assertEqual(turkce_baslik('CVE-2026-1', 'CVE-2026-1 - Güvenlik Açığı', cevir),
                         'CVE-2026-1 - Güvenlik Açığı')
        cevir.assert_not_called()
        self.assertEqual(turkce_baslik('CVE-2026-1', 'CVE-2026-1 - SQL Injection', cevir),
                         'CVE-2026-1 - SQL enjeksiyonu')
        cevir.assert_called_once_with('SQL Injection')

    def test_process_cves_ozet_basligi_cevirir(self):
        with mock.patch.object(cve_scraper, 'translate_text', side_effect=lambda m: f'TR {m}'):
            kayit = next(cve_scraper.MultiCVEScraper().process_cves([
                {'cve_id': 'CVE-2026-1', 'original_title': 'CVE-2026-1 - Stored XSS in Foo',
                 'original_description': 'Short.'}]))
        self.assertEqual(kayit['turkish_title'], 'CVE-2026-1 - TR Stored XSS in Foo')


def _cve(no, baslik=None, cvss=9.8, provider='libretranslate', tr_aciklama=None, **ek):
    govde = 'A remote attacker can read arbitrary files from the server.'
    baslik = baslik or f'CVE-2026-{no} - Güvenlik Açığı'
    return CVEEntry.objects.create(
        cve_id=f'CVE-2026-{no}', source='GitHub Advisory', original_title=baslik, turkish_title=baslik,
        original_description=govde, turkish_description=tr_aciklama or 'Uzaktaki saldırgan dosya okuyabilir.',
        link=f'https://ornek.test/cve/{no}', published_date=date(2026, 9, 12), cvss_score=cvss,
        translation_provider=provider, **ek)


class RetranslateCveBaslikTests(TestCase):

    def test_gemini_alanlari_ozeti_tasir(self):
        kayit = _cve(1, 'CVE-2026-1 - Stored XSS in Foo')
        self.assertEqual(retranslate._gemini_alanlari('cve', kayit),
                         {'title': 'Stored XSS in Foo', 'description': kayit.original_description})
        self.assertNotIn('title', retranslate._gemini_alanlari('cve', _cve(2)))

    def test_yaz_onek_geri_koyar(self):
        kayit = _cve(3, 'CVE-2026-3 - Stored XSS in Foo')
        retranslate._yaz(kayit, {'turkish_title': "Foo'da kalıcı XSS"}, 'gemini')
        kayit.refresh_from_db()
        self.assertEqual(kayit.turkish_title, "CVE-2026-3 - Foo'da kalıcı XSS")

    def test_ascii_gemini_cevirisi_yukseltme_adayidir(self):
        ascii_ = _cve(4, provider='gemini', tr_aciklama='Uzaktaki saldirgan sunucudan istedigi dosyalari '
                                                         'okuyabilir ve hassas verileri ele gecirebilir.')
        _cve(5, provider='gemini', tr_aciklama='Uzaktaki saldırgan sunucudan istediği dosyaları okuyabilir ve '
                                               'hassas verileri ele geçirebilir.')
        _cve(6, provider='gemini', tr_aciklama='Kisa ascii metin.')
        libre = _cve(7)
        dusuk = _cve(8, cvss=4.0, provider='gemini', tr_aciklama=ascii_.turkish_description)
        adaylar = retranslate._yukseltme_adaylari('cve', CVEEntry, 50)
        self.assertEqual({k.pk for k in adaylar}, {ascii_.pk, libre.pk})
        self.assertNotIn(dusuk.pk, {k.pk for k in adaylar}, 'Onem sinifi (G1) ASCII adaylara da uygulanir')


class CveBaslikCevirKomutuTests(SaglayiciZinciriMixin, TranslationGateMixin, TestCase):

    def setUp(self):
        super().setUp()
        self.saglayicilari_ayarla(SahteSaglayici('libretranslate', lambda m: f'LT {m}'))
        self.onemli = _cve(11, 'CVE-2026-11 - Stored XSS in Foo', provider='gemini')
        self.dusuk = _cve(12, 'CVE-2026-12 - Open redirect in Bar', cvss=4.3, provider='gemini')
        self.sablon = _cve(13)
        self.cevrilmis = _cve(14, 'CVE-2026-14 - Old', provider='gemini')
        CVEEntry.objects.filter(pk=self.cevrilmis.pk).update(turkish_title='CVE-2026-14 - Eski')

    def _komut(self, *args):
        cikti = StringIO()
        call_command('cve_baslik_cevir', *args, stdout=cikti)
        return cikti.getvalue()

    def test_rapor_yazmaz(self):
        self.assertIn('Basligi cevrilmemis CVE: 2 (Gemini: 1, LibreTranslate: 1)', self._komut())
        self.onemli.refresh_from_db()
        self.assertEqual(self.onemli.turkish_title, self.onemli.original_title)

    def test_onemli_gemini_digeri_libretranslate(self):
        def paket(kayitlar, bolum=None):
            return gemini.PaketSonucu(ceviriler={k: {'title': f'GM {v["title"]}'} for k, v in kayitlar.items()})
        with mock.patch.object(gemini, 'hazir', return_value=True), \
                mock.patch.object(gemini, 'paket_cevir', side_effect=paket) as paket_cevir:
            cikti = self._komut('--uygula')
        self.assertIn('Gemini: 1; LibreTranslate: 1', cikti)
        self.assertEqual(paket_cevir.call_args[0][0], {'k0': {'title': 'Stored XSS in Foo'}})
        for kayit in (self.onemli, self.dusuk, self.sablon, self.cevrilmis):
            kayit.refresh_from_db()
        self.assertEqual(self.onemli.turkish_title, 'CVE-2026-11 - GM Stored XSS in Foo')
        self.assertEqual(self.dusuk.turkish_title, 'CVE-2026-12 - LT Open redirect in Bar')
        self.assertEqual(self.sablon.turkish_title, 'CVE-2026-13 - Güvenlik Açığı')
        self.assertEqual(self.cevrilmis.turkish_title, 'CVE-2026-14 - Eski')
        self.assertEqual(self.onemli.translation_provider, 'gemini', 'Saglayici (aciklamanin) degismez')

    def test_gemini_hazir_degilse_onemli_baslik_kalir(self):
        with mock.patch.object(gemini, 'hazir', return_value=False):
            cikti = self._komut('--uygula')
        self.assertIn('sonraki calistirmaya kalan: 1', cikti)
        self.onemli.refresh_from_db()
        self.assertEqual(self.onemli.turkish_title, self.onemli.original_title)

    def test_gemini_reddi_libretranslatee_duser(self):
        with mock.patch.object(gemini, 'hazir', return_value=True), \
                mock.patch.object(gemini, 'paket_cevir', return_value=gemini.PaketSonucu(reddedilen={'k0'})):
            self._komut('--uygula')
        self.onemli.refresh_from_db()
        self.assertEqual(self.onemli.turkish_title, 'CVE-2026-11 - LT Stored XSS in Foo')


class ReklamSuzgeciTests(SimpleTestCase):

    def test_etkinlik_reklami_atilir(self):
        metin = ('OpenAI released a new model today.\n\n'
                 'Disrupt 2026: OpenAI, Anthropic, Replit, and more take over 3 industry stages. 50% off tickets now\n\n'
                 'Founder Summit begins Nov. 4, 9:00 a.m. ET. Get your pass savings & deals before it starts. '
                 'REGISTER HERE.\n\n'
                 'Don’t forget to register for KubeCon + CloudNativeCon North America 2026.\n\n'
                 'The model is available via the API.')
        self.assertEqual(temizle(metin), 'OpenAI released a new model today.\n\nThe model is available via the API.')

    def test_uzun_paragraf_ve_sponsor_bildirimi_kalir(self):
        uzun = 'TechCrunch says REGISTER HERE appears in promos. ' + 'Analysis of the market continues. ' * 20
        metin = f'{uzun.strip()}\n\nSponsored and written by Cape.'
        self.assertEqual(temizle(metin), metin)


class BozukCeviriIsaretlemeTests(TestCase):

    def test_ingilizce_kalmis(self):
        orijinal = ('In January 1917, Germany sent a secret telegram. It went to Mexico and offered Texas, '
                    'Arizona and New Mexico back.')
        self.assertTrue(ingilizce_kalmis(orijinal.replace('January', 'Ocak'), orijinal))
        self.assertFalse(ingilizce_kalmis('Ocak 1917de Almanya gizli bir telgraf gonderdi ve Meksika Teksas '
                                          'Arizona ile New Mexico geri teklif edildi.', orijinal),
                         'ASCII Turkce ceviri Ingilizce sayilmaz (yukseltme asamasi duzeltir)')
        self.assertFalse(ingilizce_kalmis('Kısa metin', 'Short text'))

    def test_komut_ingilizce_kaydi_kuyruga_koyar(self):
        orijinal = ('In January 1917, Germany sent a secret telegram. It went to Mexico and offered Texas, '
                    'Arizona and New Mexico back.')
        kayit = KubernetesEntry.objects.create(
            source='CNCF Blog', original_title='T', turkish_title='T', original_description=orijinal,
            turkish_description=orijinal.replace('January', 'Ocak'), link='https://ornek.test/k8s/428',
            published_date=date(2026, 9, 12), translation_provider='google', translation_attempts=3)
        temiz = AINewsEntry.objects.create(
            source='S', original_title='T', turkish_title='T', original_description=orijinal,
            turkish_description='Ocak 1917’de Almanya gizli bir telgraf gönderdi.', link='https://ornek.test/ai/1',
            published_date=date(2026, 9, 12))
        cikti = StringIO()
        call_command('bozuk_cevirileri_isaretle', '--uygula', stdout=cikti)
        self.assertIn('KubernetesEntry: 1 (kalinti 0, ingilizce 1)', cikti.getvalue())
        kayit.refresh_from_db()
        temiz.refresh_from_db()
        self.assertEqual((kayit.needs_translation, kayit.translation_attempts), (True, 0))
        self.assertFalse(temiz.needs_translation)
