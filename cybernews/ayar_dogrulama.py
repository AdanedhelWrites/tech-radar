"""Uretim ayarlarini acilista dogrular (GUVENLIK-PLANI P4).

settings.py bu modulu import eder; Django henuz kurulmamisken calistigi icin
yalniz django.core.exceptions kullanir.
"""
from typing import Optional

from django.core.exceptions import ImproperlyConfigured

# Yalniz DEBUG=True iken ve SECRET_KEY verilmemisse kullanilir
GELISTIRME_ANAHTARI = 'django-insecure-yalniz-yerel-gelistirme-icin'

# Django check --deploy 50 karakter ister; openssl rand -hex 32 (64 karakter)
# rahatca gecer. Alt sinir, "test", "changeme" gibi elle yazilmis degerleri eler.
MIN_UZUNLUK = 32

# Depoda ya da belgelerde ornek olarak gecmis degerler (gitleaks baseline'daki
# bes bulgu + docker-compose.yml + settings.py'nin eski varsayilani). Bunlarla
# uretimde acilmak anahtari herkese acar: session/CSRF imzasi taklit edilebilir.
BILINEN_ORNEKLER = frozenset({
    'your-secret-key-here-change-in-production',
    'buraya-guclu-rastgele-secret-key-yazin-min-50-karakter',
    'min-50-karakter-rastgele-guclu-bir-key',
    'django-insecure-change-in-production',
})

_URETIM_IPUCU = '`openssl rand -hex 32` ile uretip SECRET_KEY ortam degiskenine verin.'


def dogrulanmis_secret_key(anahtar: Optional[str], debug: bool) -> str:
    """Kullanilacak SECRET_KEY'i dondurur; uretimde zayif anahtarla acilmayi reddeder.

    Hata mesaji anahtarin kendisini asla icermez (loglara sizmasin).
    """
    if debug:
        return anahtar or GELISTIRME_ANAHTARI
    if not anahtar:
        raise ImproperlyConfigured(f'DEBUG=False iken SECRET_KEY tanimli olmali. {_URETIM_IPUCU}')
    if anahtar in BILINEN_ORNEKLER or anahtar.startswith('django-insecure'):
        raise ImproperlyConfigured(f'SECRET_KEY depodaki bir ornek deger. {_URETIM_IPUCU}')
    if len(anahtar) < MIN_UZUNLUK:
        raise ImproperlyConfigured(
            f'SECRET_KEY en az {MIN_UZUNLUK} karakter olmali. {_URETIM_IPUCU}')
    return anahtar
