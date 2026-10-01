# Faz B1: PostgreSQL max_length uygular (SQLite uygulamazdi). news, cve ve
# kubernetes bolumlerinin link alani diger uc bolumle ayni 500 karaktere cikar.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0012_alter_newsarticle_link'),
    ]

    operations = [
        migrations.AlterField(
            model_name='newsarticle',
            name='link',
            field=models.URLField(max_length=500, unique=True, verbose_name='Link'),
        ),
        migrations.AlterField(
            model_name='cveentry',
            name='link',
            field=models.URLField(max_length=500, verbose_name='Link'),
        ),
        migrations.AlterField(
            model_name='kubernetesentry',
            name='link',
            field=models.URLField(max_length=500, unique=True, verbose_name='Link'),
        ),
    ]
