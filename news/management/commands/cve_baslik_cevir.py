"""Basligi Ingilizce kalmis CVE'lerin basligini bir kez cevirir (2026-11-07).

GitHub Advisory ozeti ve CISA KEV zafiyet adi "CVE-x - <ozet>" olarak saklanir. 11-07'ye kadar CVE basligi hic
cevrilmiyordu (sablon basligi varsayimi); 1039 GHSA ve 16 KEV kaydinin basligi Ingilizce kaldi. Yeni kayitlar
artik cevriliyor (cve_basligi.turkce_baslik); bu komut eskileri tamamlar. Yalniz turkish_title yazilir:
aciklama ve translation_provider degismez.

Onem sinifi kurali (retranslate G1) aynen gecerlidir: CVSS >= 7 ya da KEV kaydinin basligi Gemini'ye paketli
gider (40 baslik tek istek), digerleri LibreTranslate ile cevrilir. Gemini'nin reddettigi baslik LibreTranslate'e
duser; Gemini hazir degilse (butce / devre kesici) kalan onemli basliklar sonraki calistirmaya kalir.
"""
from django.core.management.base import BaseCommand
from django.db.models import F

from news import gemini
from news import translation_utils as tu
from news.cve_basligi import baslik_ozeti, onekli_baslik
from news.models import CVEEntry
from news.retranslate import _gemini_adayi_mi, _paketle

PAKET_ADEDI = 40


def adaylar():
    """Basligi ozet tasiyan ve Turkce basligi orijinaliyle ayni (hic cevrilmemis) CVE'ler, en onemli once."""
    sorgu = (CVEEntry.objects.filter(needs_translation=False, turkish_title=F('original_title'))
             .order_by(F('cvss_score').desc(nulls_last=True), 'cve_id')
             .only('id', 'cve_id', 'original_title', 'turkish_title', 'cvss_score', 'kev_added_date'))
    return [(kayit, ozet) for kayit in sorgu.iterator()
            if (ozet := baslik_ozeti(kayit.cve_id, kayit.original_title))]


def _yaz(kayit, ceviri: str) -> bool:
    baslik = onekli_baslik(kayit.cve_id, ceviri)
    if not baslik or baslik == kayit.original_title:
        return False
    kayit.turkish_title = baslik
    kayit.save(update_fields=['turkish_title', 'updated_at'])
    return True


class Command(BaseCommand):
    help = ("Basligi Ingilizce kalmis GHSA/KEV CVE basliklarini cevirir. Varsayilan yalniz raporlar; "
            "yazmak icin --uygula.")

    def add_arguments(self, parser):
        parser.add_argument('--uygula', action='store_true', help='Basliklari cevir ve yaz (yoksa yalniz rapor)')

    def handle(self, *args, **opts):
        tum = adaylar()
        onemli = [(k, o) for k, o in tum if _gemini_adayi_mi('cve', k)]
        diger = [(k, o) for k, o in tum if not _gemini_adayi_mi('cve', k)]
        self.stdout.write(f"Basligi cevrilmemis CVE: {len(tum)} (Gemini: {len(onemli)}, LibreTranslate: {len(diger)})")
        if not opts['uygula']:
            for kayit, _ in tum[:10]:
                self.stdout.write(f"  {kayit.original_title[:120]}")
            self.stdout.write("Rapor modu; yazmak icin --uygula.")
            return

        gemini_yazilan, kalan = 0, 0
        paketler = _paketle([(k, {'title': o}) for k, o in onemli], gemini.GEMINI_BATCH_CHARS, PAKET_ADEDI)
        for sira, paket in enumerate(paketler):
            if not gemini.hazir():
                kalan = sum(len(p) for p in paketler[sira:])
                self.stdout.write(f"  Gemini hazir degil; {kalan} onemli baslik sonraki calistirmaya kaldi")
                break
            sonuc = gemini.paket_cevir({f'k{i}': alanlar for i, (_, alanlar) in enumerate(paket)}, 'cve')
            if sonuc.istek_hatasi or sonuc.kesildi or sonuc.yanit_bozuk:
                # Istek duzeyi hata: kayitlarin sucu degil, LibreTranslate'e dusurulmez
                kalan += len(paket)
                self.stdout.write(f"  paket {sira + 1}: istek basarisiz, {len(paket)} baslik kaldi")
                continue
            for i, (kayit, alanlar) in enumerate(paket):
                ceviri = sonuc.ceviriler.get(f'k{i}')
                if ceviri and _yaz(kayit, ceviri['title']):
                    gemini_yazilan += 1
                else:
                    diger.append((kayit, alanlar['title']))  # icerik reddi: LibreTranslate denensin

        libre_yazilan, basarisiz = 0, 0
        for kayit, ozet in diger:
            tu.consume_translation_failures()
            ceviri = tu.translate_text(ozet)
            if tu.consume_translation_failures() == 0 and _yaz(kayit, ceviri):
                libre_yazilan += 1
            else:
                basarisiz += 1
        tu.consume_translation_providers()
        self.stdout.write(f"Gemini: {gemini_yazilan}; LibreTranslate: {libre_yazilan}; "
                          f"cevrilemeyen: {basarisiz}; sonraki calistirmaya kalan: {kalan}")
