"""CVE baslik ozeti (uctan uca test bulgusu 7, 2026-10-16).

Kayitlarin %92'si (10-22: 8076/8812) "CVE-x - Güvenlik Açığı" sablon basligi tasiyor; CWE kayitlarin
%9'unda var, etkilenen urun hicbirinde yok. Baslik aciklamanin ilk cumlesinden turetilir (API katmaninda;
saklanan veri degismez, ceviri iyilestikce baslik da iyilesir).
"""
from datetime import date

from django.test import SimpleTestCase, TestCase

from news.api_v1.serializers import CVEEntryV1Serializer
from news.cve_basligi import BASLIK_MAX_KARAKTER, cve_basligi
from news.models import CVEEntry
from news.serializers import CVEEntrySerializer


class CveBasligiTests(SimpleTestCase):

    def test_sablon_olmayan_baslik_aynen_kalir(self):
        self.assertEqual(cve_basligi('CVE-2026-1', 'CVE-2026-1 - Fortinet FortiOS RCE', 'Bir aciklama.', ''),
                         'CVE-2026-1 - Fortinet FortiOS RCE')

    def test_sablon_baslik_ilk_cumleden_turetilir(self):
        self.assertEqual(
            cve_basligi('CVE-2026-2', 'CVE-2026-2 - Güvenlik Açığı',
                        "Tenda AC19 16.03.10.07'de bir güvenlik açığı tespit edilmiştir. Etkilenen bileşen httpd.",
                        'A vulnerability was identified in Tenda AC19 16.03.10.07. The affected component is httpd.'),
            "CVE-2026-2 - Tenda AC19 16.03.10.07'de bir güvenlik açığı tespit edilmiştir")

    def test_aktif_somurulen_sablonu_da_turetilir(self):
        self.assertEqual(
            cve_basligi('CVE-2026-3', 'CVE-2026-3 - Aktif Sömürülen Zafiyet', 'Ivanti EPMM kimlik doğrulamasız RCE.', ''),
            'CVE-2026-3 - Ivanti EPMM kimlik doğrulamasız RCE')

    def test_linux_cekirdek_kalibi_atilir(self):
        for giris in ('Linux çekirdeğinde, aşağıdaki kırılganlık çözülmüştür: bpf: Infer zext_dst statik kayıt analizi',
                      'Linux cekirdeginde su zaafiyet giderildi: bpf: Infer zext_dst statik kayıt analizi',
                      'Linux cekirdeginde asagidaki zaafiyet giderildi:\n\nbpf: Infer zext_dst statik kayıt analizi'):
            with self.subTest(giris=giris[:40]):
                self.assertEqual(cve_basligi('CVE-2026-4', 'CVE-2026-4 - Güvenlik Açığı', giris,
                                             'In the Linux kernel, the following vulnerability has been resolved: bpf: x'),
                                 'CVE-2026-4 - Linux çekirdeği: bpf: Infer zext_dst statik kayıt analizi')

    def test_tanim_cumlesi_atlanir_urun_adi_onek_olur(self):
        self.assertEqual(
            cve_basligi('CVE-2026-5', 'CVE-2026-5 - Güvenlik Açığı',
                        'Elektron JavaScript, HTML ve CSS kullanarak masaüstü uygulamaları yazmak için bir çerçevedir. '
                        '42.11.3 öncesi sürümlerde dış protokol URL\'leri doğrulanmıyor.',
                        'Electron is a framework for writing cross-platform desktop applications using JavaScript, '
                        'HTML and CSS. Prior to 42.11.3, external protocol URLs are not validated.'),
            "CVE-2026-5 - Electron: 42.11.3 öncesi sürümlerde dış protokol URL'leri doğrulanmıyor")

    def test_uzun_cumle_kelime_sinirinda_kesilir(self):
        cumle = 'Vyper ' + 'derleyicisindeki ' * 20 + 'hata.'
        sonuc = cve_basligi('CVE-2026-6', 'CVE-2026-6 - Güvenlik Açığı', cumle, '')
        ozet = sonuc.removeprefix('CVE-2026-6 - ')
        self.assertLessEqual(len(ozet), BASLIK_MAX_KARAKTER)
        self.assertTrue(ozet.endswith('…'))
        self.assertNotIn('derleyicisinde…', ozet.replace('derleyicisindeki', ''))

    def test_surum_noktasi_cumle_sonu_sayilmaz(self):
        sonuc = cve_basligi('CVE-2026-7', 'CVE-2026-7 - Güvenlik Açığı',
                            'Astral uv 0.11.6 öncesi sürümler yol geçişine açık. İkinci cümle.', '')
        self.assertEqual(sonuc, 'CVE-2026-7 - Astral uv 0.11.6 öncesi sürümler yol geçişine açık')

    def test_tek_satir_sonu_cumleyi_bolmez(self):
        # Canli: "Patreon WordPress eklentisinin 1.10.0 öncesi sürümleri, bazı" (satir ici kirilma)
        self.assertEqual(
            cve_basligi('CVE-2026-11', 'CVE-2026-11 - Güvenlik Açığı',
                        'Patreon WordPress eklentisinin 1.10.0 öncesi sürümleri, bazı\nparametreleri temizlemiyor. Devamı.', ''),
            'CVE-2026-11 - Patreon WordPress eklentisinin 1.10.0 öncesi sürümleri, bazı parametreleri temizlemiyor')

    def test_aciklama_yoksa_sablon_kalir(self):
        self.assertEqual(cve_basligi('CVE-2026-8', 'CVE-2026-8 - Güvenlik Açığı', '', ''),
                         'CVE-2026-8 - Güvenlik Açığı')

    def test_turkce_yoksa_orijinal_aciklama_kullanilir(self):
        self.assertEqual(cve_basligi('CVE-2026-9', 'CVE-2026-9 - Güvenlik Açığı', '',
                                     'Missing authorization in hMailServer REST API. More text.'),
                         'CVE-2026-9 - Missing authorization in hMailServer REST API')


class CveSerializerBaslikTests(TestCase):

    def setUp(self):
        self.cve = CVEEntry.objects.create(
            cve_id='CVE-2026-10', source='Tenable', original_title='CVE-2026-10 - Güvenlik Açığı',
            turkish_title='CVE-2026-10 - Güvenlik Açığı',
            original_description='Missing authorization in hMailServer. Details.',
            turkish_description='hMailServer yönetim API\'sinde eksik yetkilendirme. Ayrıntılar.',
            published_date=date(2026, 10, 21), link='https://ornek.test/cve/10')

    def test_eski_api_turkce_basligi_turetir(self):
        veri = CVEEntrySerializer(self.cve).data
        self.assertEqual(veri['turkish_title'], "CVE-2026-10 - hMailServer yönetim API'sinde eksik yetkilendirme")
        self.assertEqual(veri['original_title'], 'CVE-2026-10 - Güvenlik Açığı')

    def test_v1_baslik_tr_turetilir_original_degismez(self):
        baslik = CVEEntryV1Serializer(self.cve).data['title']
        self.assertEqual(baslik['tr'], "CVE-2026-10 - hMailServer yönetim API'sinde eksik yetkilendirme")
        self.assertEqual(baslik['original'], 'CVE-2026-10 - Güvenlik Açığı')

    def test_saklanan_veri_degismez(self):
        CVEEntrySerializer(self.cve).data
        self.cve.refresh_from_db()
        self.assertEqual(self.cve.turkish_title, 'CVE-2026-10 - Güvenlik Açığı')
