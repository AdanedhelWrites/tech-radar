"""Turkce metni bozuk ama 'cevrildi' gorunen kayitlari bulur ve yeniden ceviri kuyruguna koyar.

Iki sebep aranir:
  - yer tutucu kalintisi: 2026-09-12'de iki hata (ic ice yer tutucunun geri konmamasi ve bozuk yer
    tutucunun geri koymadan sonra onarilmasi) 19 CVE kaydinda ham XTRM kodu birakti (A3 Task 1'de duzeldi).
  - ingilizce kalmis: scraper'in ceviri istisnasi dali 2026-11-07'ye kadar orijinali cevrildi olarak
    yaziyordu (ornek K8s 428: 'In Ocak 1917, Germany sent a secret telegram'). Yalniz ay adi gibi birkac
    kelimesi degismis metin tam esitlikle yakalanmaz; Turkce harf tasimayan ve kelimelerinin cogu
    orijinalde de gecen metin aranir.

Bulunan kayit needs_translation=True ve translation_attempts=0 yapilir ki retranslate_pending_task onu
yeniden cevirsin. ASCII'ye kaymis (diakritiksiz) eski Gemini cevirileri burada degil, retranslate'in
yukseltme asamasinda paketli olarak yeniden cevrilir (retranslate._ascii_gemini_cevirisi).

Isaretleme sirasinda updated_at de simdiki zamana cekilir (QuerySet.update auto_now'i atlar): aksi halde
saklama suzgeci (updated_at'e gore 90 gunluk pencere) yeniden cevrilmeyi bekleyen bu kaydi silebilirdi.
"""
import re

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)

# Bozuk bicimler dahil: 'XTRM0021X', 'xtrm 0003x', 'X TRM0001 X'
KALINTI = re.compile(r'[Xx]\s*[Tt]\s*[Rr]\s*[Mm]\s*\d{4}\s*[Xx]')
MODELLER = (NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry)
TURKCE_ALANLAR = ('turkish_title', 'turkish_description', 'turkish_summary')

_TURKCE_HARF = re.compile('[çğıöşüÇĞİÖŞÜ]')
_KELIME = re.compile(r'[^\W\d_]{3,}')
INGILIZCE_MIN_KELIME = 10
# Turkce cevirinin kelimelerinin bu orani orijinalde de geciyorsa metin cevrilmemistir. 11-07 canli olcumu:
# cevrilmemis 4 kayit 1.0; urun adi agir kisa CVE cevirileri (ASCII Gemini) 0.80-0.82'ye cikiyor.
INGILIZCE_ORTAK_ORAN = 0.9


def ingilizce_kalmis(turkce: str, orijinal: str) -> bool:
    kelimeler = [k.casefold() for k in _KELIME.findall(turkce or '')]
    if len(kelimeler) < INGILIZCE_MIN_KELIME or _TURKCE_HARF.search(turkce):
        return False
    orijinal_kelimeler = {k.casefold() for k in _KELIME.findall(orijinal or '')}
    ortak = sum(1 for k in kelimeler if k in orijinal_kelimeler)
    return ortak / len(kelimeler) >= INGILIZCE_ORTAK_ORAN


def bozuk_sebebi(kayit, alanlar) -> str:
    """'kalinti', 'ingilizce' ya da '' (sorun yok)."""
    if any(KALINTI.search(getattr(kayit, alan) or '') for alan in alanlar):
        return 'kalinti'
    if ingilizce_kalmis(kayit.turkish_description, kayit.original_description):
        return 'ingilizce'
    return ''


class Command(BaseCommand):
    help = ("Turkce metninde XTRM yer tutucu kalintisi olan ya da Ingilizce kalmis, cevrildi gorunen "
            "kayitlari bulur. Varsayilan olarak yalnizca raporlar; isaretlemek icin --uygula.")

    def add_arguments(self, parser):
        parser.add_argument('--uygula', action='store_true',
                            help='Bulunan kayitlari needs_translation=True yap.')

    def handle(self, *args, **options):
        toplam = 0
        for model in MODELLER:
            model_alanlari = {alan.name for alan in model._meta.get_fields()}
            alanlar = [alan for alan in TURKCE_ALANLAR if alan in model_alanlari]
            sebepler = {'kalinti': [], 'ingilizce': []}
            sorgu = model.objects.filter(needs_translation=False).only('id', 'original_description', *alanlar)
            for kayit in sorgu.iterator():
                sebep = bozuk_sebebi(kayit, alanlar)
                if sebep:
                    sebepler[sebep].append(kayit.pk)
            kimlikler = sebepler['kalinti'] + sebepler['ingilizce']
            if options['uygula'] and kimlikler:
                model.objects.filter(pk__in=kimlikler).update(
                    needs_translation=True, translation_attempts=0, updated_at=timezone.now(),
                )
            toplam += len(kimlikler)
            self.stdout.write(f"{model.__name__}: {len(kimlikler)} (kalinti {len(sebepler['kalinti'])}, "
                              f"ingilizce {len(sebepler['ingilizce'])})")

        if not options['uygula']:
            self.stdout.write('(yalnizca rapor; isaretlemek icin --uygula)')
        self.stdout.write(f'TOPLAM: {toplam}')
