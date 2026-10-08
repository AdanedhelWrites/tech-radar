# FetchRun.by_source: kaynak basina gelen/yazilan sayaclari (kaynak sagligi, 2026-10-08).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0013_link_max_length_500'),
    ]

    operations = [
        migrations.AddField(
            model_name='fetchrun',
            name='by_source',
            field=models.JSONField(blank=True, default=dict, verbose_name='Kaynak Dagilimi'),
        ),
    ]
