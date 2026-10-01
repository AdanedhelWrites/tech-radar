"""Tasinacak modellerin serilestiriciden bagimsiz ozeti (Faz B1, spec 5.3).

Iki veritabaninda calistirilip ciktilari diff ile karsilastirilir; fark yoksa
tasima kayipsizdir (tum alanlar ve v1 delta sirasi dahil).
"""
from django.core.management.base import BaseCommand

from news.veri_tasima import ozet


class Command(BaseCommand):
    help = ('Model basina satir sayisi, tum alanlarin sha256 ozeti ve (updated_at, id) '
            'delta ozeti. Iki veritabaninin ciktisi diff ile karsilastirilir.')

    def handle(self, *args, **options):
        for etiket, sayi, alan, delta in ozet():
            self.stdout.write(f'{etiket} {sayi} {alan} {delta}')
