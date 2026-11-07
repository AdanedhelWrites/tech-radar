"""Aciklamasi yer tutucu ("No description provided") olan CVE'leri NVD'den tamamlar (2026-11-07).

10-23'te Tenable 57 CVE'yi aciklamasiz yazdi (18'i Kritik). O zamanki kod var olan kaydi hic
guncellemedigi icin bu kayitlar aciklamasiz kaldi. Yeni kod (news/cve_guncelleme.py) gercek aciklama
geldiginde kaydi gunceller; ama bu CVE'lerin yayin tarihi NVD cekim penceresinin disinda kaldigi icin
yalniz NVD'de degistirildiklerinde gelirler. Bu komut onlari CVE kimligiyle NVD'den bir kez ister.

Guncellenen kayit ceviri kuyruguna doner (needs_translation); saatlik retranslate onu cevirir.
NVD anahtarsiz 5 istek / 30 sn: istekler NVD_ISTEK_ARALIGI ile aralanir (57 kayit ~6 dk).
"""
from django.core.management.base import BaseCommand

from news import cve_guncelleme
from news.cve_scraper import NVDScraper, aciklama_yer_tutucu_mu
from news.models import CVEEntry


class Command(BaseCommand):
    help = ("Aciklamasi yer tutucu olan CVE'leri NVD'den tamamlar. Varsayilan yalniz raporlar; "
            "yazmak icin --uygula.")

    def add_arguments(self, parser):
        parser.add_argument('--uygula', action='store_true', help='Kayitlari guncelle (yoksa yalniz rapor)')

    def handle(self, *args, **opts):
        adaylar = [k for k in CVEEntry.objects.order_by('-cvss_score', 'cve_id')
                   .only('id', 'cve_id', 'original_description')
                   if aciklama_yer_tutucu_mu(k.original_description)]
        self.stdout.write(f"Yer tutucu aciklamali CVE: {len(adaylar)}")
        if not opts['uygula']:
            for kayit in adaylar:
                self.stdout.write(f"  {kayit.cve_id}")
            self.stdout.write("Rapor modu; yazmak icin --uygula.")
            return

        scraper = NVDScraper()
        guncellenen, bulunamayan = 0, []
        for kayit in adaylar:
            try:
                yanit = scraper._nvd_get(scraper.BASE_URL, params={'cveId': kayit.cve_id}, timeout=30)
                yanit.raise_for_status()
                ogeler = (yanit.json() or {}).get('vulnerabilities', [])
            except Exception as hata:
                self.stderr.write(f"  {kayit.cve_id}: NVD hatasi ({type(hata).__name__}: {hata})")
                bulunamayan.append(kayit.cve_id)
                continue
            cve = scraper._nvd_kaydi(ogeler[0].get('cve', {}), 'NVD') if ogeler else None
            if cve and cve_guncelleme.guncelle(CVEEntry.objects.get(pk=kayit.pk), cve):
                guncellenen += 1
                self.stdout.write(f"  {kayit.cve_id}: guncellendi, ceviri kuyrugunda")
            else:
                bulunamayan.append(kayit.cve_id)
                self.stdout.write(f"  {kayit.cve_id}: NVD'de kullanilabilir aciklama/CVSS yok")
        self.stdout.write(f"Guncellenen: {guncellenen}; tamamlanamayan: {len(bulunamayan)}")
