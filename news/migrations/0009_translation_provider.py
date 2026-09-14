from django.db import migrations, models

MODELLER = ('ainewsentry', 'cveentry', 'devtoolsentry', 'kubernetesentry', 'newsarticle', 'sreentry')


def eski_cevirileri_google_isaretle(apps, schema_editor):
    """2026-09-14'e kadar tek saglayici Google'di: cevrilmis kayitlar 'google' olur.

    QuerySet.update updated_at'i ilerletmez; tuketicinin delta akisina kayit dusmez.
    Aciklamasi 30 karakterden kisa oldugu icin hic cevrilmemis CVE'ler de 'google'
    gorunur; cevrilecek metinleri olmadigi icin zararsizdir.
    """
    for ad in MODELLER:
        apps.get_model('news', ad).objects.filter(needs_translation=False).update(translation_provider='google')


def geri_al(apps, schema_editor):
    for ad in MODELLER:
        apps.get_model('news', ad).objects.update(translation_provider='')


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0008_updated_at'),
    ]

    operations = [
        *[
            migrations.AddField(
                model_name=ad,
                name='translation_provider',
                field=models.CharField(
                    blank=True, default='', max_length=20,
                    choices=[('google', 'Google'), ('libretranslate', 'LibreTranslate')],
                    verbose_name='Ceviri Saglayicisi'),
            )
            for ad in MODELLER
        ],
        migrations.RunPython(eski_cevirileri_google_isaretle, geri_al),
    ]
