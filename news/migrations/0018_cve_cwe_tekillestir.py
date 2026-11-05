"""Yinelenen CWE kimliklerini temizler.

NVD ayni CWE'yi Primary (NVD) ve Secondary (CNA) olarak iki kez verebiliyordu;
ayristirici ikisini de kaydettigi icin ~190 kayitta liste yineleniyordu (arayuzde
cift rozet ve React anahtar uyarisi). Ayristirici artik tekillestiriyor; bu goc
mevcut kayitlari sirayi koruyarak duzeltir. updated_at'e dokunmamak icin
queryset.update kullanilir.
"""
from django.db import migrations


def cwe_tekillestir(apps, schema_editor):
    CVEEntry = apps.get_model('news', 'CVEEntry')
    for kayit in CVEEntry.objects.only('id', 'cwe_ids').iterator():
        liste = kayit.cwe_ids
        if not isinstance(liste, list):
            continue
        tekil = list(dict.fromkeys(c for c in liste if c))
        if tekil != liste:
            CVEEntry.objects.filter(pk=kayit.pk).update(cwe_ids=tekil)


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0017_translation_provider_yedekler'),
    ]

    operations = [
        migrations.RunPython(cwe_tekillestir, migrations.RunPython.noop),
    ]
