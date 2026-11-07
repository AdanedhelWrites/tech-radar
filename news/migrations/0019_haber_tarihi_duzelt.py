"""Okunamadigi icin cekim gunu yazilmis haber tarihlerini original_date'ten duzeltir (2026-11-07).

The Hacker News tarih metninin basinda ikon yazi tipi karakteri var ('\\ue802Nov 07, 2026'); tam esleme
bekleyen strptime hep dustu ve 439 kaydin `date` alanina cekim gunu yazildi. Ayristirici artik tarihi metnin
icinden ayikliyor (news.base_scraper.ay_tarihi_coz); bu goc mevcut kayitlari ayni kuralla duzeltir. Desen
burada kopyadir: goc, uygulama kodu sonradan degisse de ayni sonucu vermeli. Yalniz tarihi okunabilen ve
farkli olan kayitlar yazilir; updated_at'e dokunmamak icin queryset.update kullanilir.
"""
import re
from datetime import date

from django.db import migrations

_AY_TARIHI = re.compile(
    r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})(?!\d)', re.I)
_AYLAR = {ad: i for i, ad in enumerate(
    ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'), 1)}


def _coz(metin):
    eslesme = _AY_TARIHI.search(metin or '')
    if not eslesme:
        return None
    try:
        return date(int(eslesme.group(3)), _AYLAR[eslesme.group(1).lower()], int(eslesme.group(2)))
    except ValueError:
        return None


def tarihleri_duzelt(apps, schema_editor):
    NewsArticle = apps.get_model('news', 'NewsArticle')
    for kayit in NewsArticle.objects.exclude(original_date='').only('id', 'date', 'original_date').iterator():
        dogru = _coz(kayit.original_date)
        if dogru is not None and dogru != kayit.date:
            NewsArticle.objects.filter(pk=kayit.pk).update(date=dogru)


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0018_cve_cwe_tekillestir'),
    ]

    operations = [
        migrations.RunPython(tarihleri_duzelt, migrations.RunPython.noop),
    ]
