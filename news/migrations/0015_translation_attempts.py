# Ceviri deneme sayaci (2026-10-08): retranslate zehirli kayit dongusu.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0014_fetchrun_by_source'),
    ]

    operations = [
        migrations.AddField(
            model_name=model,
            name='translation_attempts',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='Ceviri Deneme Sayisi'),
        )
        for model in ('newsarticle', 'cveentry', 'kubernetesentry', 'sreentry', 'devtoolsentry', 'ainewsentry')
    ]
