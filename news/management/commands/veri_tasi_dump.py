"""Tam hassasiyetli veri dump'i (Faz B1, spec 5.3).

Cikti standart `manage.py loaddata <dosya>` ile yuklenir. Dosya HASSASTIR: parola
hash'leri ve API token'lari icerir; commit edilmez, is bitince silinir.
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from news.veri_tasima import yaz


class Command(BaseCommand):
    help = ("Tasinacak tum modelleri mikrosaniyeyi koruyan JSON olarak yazar "
            "(loaddata ile yuklenir). Dosya hassastir: commit etmeyin.")

    def add_arguments(self, parser):
        parser.add_argument('cikti', help='Yazilacak JSON dosyasinin yolu.')

    def handle(self, *args, **options):
        yol = Path(options['cikti'])
        yol.parent.mkdir(parents=True, exist_ok=True)
        with yol.open('w', encoding='utf-8') as akis:
            sayilar = yaz(akis)
        for etiket, sayi in sayilar.items():
            self.stderr.write(f'{etiket} {sayi}')
        self.stderr.write(f'toplam {sum(sayilar.values())} nesne -> {yol}')
