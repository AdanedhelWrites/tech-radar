"""Turkce metninde yer tutucu kalintisi olan ama 'cevrildi' gorunen kayitlari bulur.

2026-09-12'de iki hata (ic ice yer tutucunun geri konmamasi ve bozuk yer
tutucunun geri koymadan sonra onarilmasi) 19 CVE kaydinda ham XTRM kodu birakti.
Hatalar A3 Task 1'de duzeltildi; bu komut mevcut bozuk kayitlari
needs_translation=True yapar ki retranslate_pending_task onlari yeniden cevirsin.

Isaretleme sirasinda updated_at de simdiki zamana cekilir (QuerySet.update
auto_now'i atlar): aksi halde saklama suzgeci (updated_at'e gore 90 gunluk
pencere) yeniden cevrilmeyi bekleyen bu kaydi silebilirdi.
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


class Command(BaseCommand):
    help = ("Turkce metninde XTRM yer tutucu kalintisi olan, cevrildi gorunen kayitlari "
            "bulur. Varsayilan olarak yalnizca raporlar; isaretlemek icin --uygula.")

    def add_arguments(self, parser):
        parser.add_argument('--uygula', action='store_true',
                            help='Bulunan kayitlari needs_translation=True yap.')

    def handle(self, *args, **options):
        toplam = 0
        for model in MODELLER:
            model_alanlari = {alan.name for alan in model._meta.get_fields()}
            alanlar = [alan for alan in TURKCE_ALANLAR if alan in model_alanlari]
            kimlikler = [
                kayit.pk
                for kayit in model.objects.filter(needs_translation=False).only('id', *alanlar).iterator()
                if any(KALINTI.search(getattr(kayit, alan) or '') for alan in alanlar)
            ]
            if options['uygula'] and kimlikler:
                model.objects.filter(pk__in=kimlikler).update(
                    needs_translation=True, updated_at=timezone.now(),
                )
            toplam += len(kimlikler)
            self.stdout.write(f'{model.__name__}: {len(kimlikler)}')

        if not options['uygula']:
            self.stdout.write('(yalnizca rapor; isaretlemek icin --uygula)')
        self.stdout.write(f'TOPLAM: {toplam}')
