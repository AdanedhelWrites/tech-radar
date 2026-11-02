# KEV eklenme tarihi alani (2026-10-31): onekten geri doldurulur.
from django.db import migrations, models

from news.kev import kev_oneki_ayir


def geri_doldur(apps, schema_editor):
    """Onekli KEV kayitlarinin eklenme tarihini alana yazar; original_description degismez.

    QuerySet.update updated_at'i ilerletmez; tuketicinin delta akisina kayit dusmez.
    """
    CVEEntry = apps.get_model('news', 'CVEEntry')
    kayitlar = CVEEntry.objects.filter(original_description__startswith='Added to the CISA KEV catalog on ')
    for pk, aciklama in kayitlar.values_list('pk', 'original_description'):
        eklenme, _son, _govde = kev_oneki_ayir(aciklama)
        if eklenme:
            CVEEntry.objects.filter(pk=pk).update(kev_added_date=eklenme)


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0015_translation_attempts'),
    ]

    operations = [
        migrations.AddField(
            model_name='cveentry',
            name='kev_added_date',
            field=models.DateField(blank=True, db_index=True, null=True, verbose_name='KEV Eklenme Tarihi'),
        ),
        migrations.RunPython(geri_doldur, migrations.RunPython.noop),
    ]
