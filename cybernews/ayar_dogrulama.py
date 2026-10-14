"""Uretim ayarlarini acilista dogrular (GUVENLIK-PLANI P4).

settings.py bu modulu import eder; Django henuz kurulmamisken calistigi icin
yalniz django.core.exceptions kullanir.
"""
import re
from pathlib import Path
from typing import Mapping, Optional

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


def veritabani_ayari(ortam: Mapping[str, str], debug: bool, base_dir: Path) -> dict:
    """DATABASES sozlugunu dondurur (Faz B1, spec 5.1).

    DB_HOST doluysa PostgreSQL. Bossa yalniz DEBUG=True iken SQLite: env'i eksik
    bir pod veya konteyner sessizce gecici bir SQLite yaratip "calisiyormus" gibi
    gorunmesin, hata acilista gorunsun. DATABASE_URL bilincli olarak okunmaz.
    Hata mesaji parolayi asla icermez.
    """
    host = (ortam.get('DB_HOST') or '').strip()
    if host:
        return {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': ortam.get('DB_NAME') or 'cybernews',
                'USER': ortam.get('DB_USER') or 'cybernews',
                'PASSWORD': ortam.get('DB_PASSWORD', ''),
                'HOST': host,
                'PORT': ortam.get('DB_PORT') or '5432',
                'CONN_MAX_AGE': 600,
                'CONN_HEALTH_CHECKS': True,
                'OPTIONS': {'connect_timeout': 10},
            }
        }
    if not debug:
        raise ImproperlyConfigured(
            "DB_HOST tanimli degil: DEBUG=False iken SQLite'a dusulmez. PostgreSQL "
            "baglantisini DB_HOST, DB_NAME, DB_USER, DB_PASSWORD ile verin "
            "(yerel gelistirmede DEBUG=True ile SQLite kullanilir).")
    return {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': base_dir / 'db.sqlite3',
        }
    }


_ORAN_BICIMI = re.compile(r'\d+/(s|sec|m|min|h|hour|d|day)')


def v1_hiz_sinirlari(env: Mapping[str, str]) -> dict:
    """v1 throttle oranlari (DRF 'sayi/birim'). DAST bunlari ortamdan gevsetir: ZAP API
    taramasi dakikada yuzlerce istek atar, 120/min ile her sey 429 olurdu (P5-c, 2026-10-14).
    Bos deger varsayilana duser. Bicim burada dogrulanir: DRF birimin yalniz ilk harfine
    bakar ('100/dakika' sessizce '100/gun' olurdu), bozuk deger acilista ImproperlyConfigured verir.
    """
    oranlar = {
        'v1_read': ('V1_THROTTLE_READ', '120/min'),
        'v1_refresh': ('V1_THROTTLE_REFRESH', '12/hour'),
    }
    sonuc = {}
    for anahtar, (ad, varsayilan) in oranlar.items():
        deger = env.get(ad, '') or varsayilan
        if not _ORAN_BICIMI.fullmatch(deger):
            raise ImproperlyConfigured(
                f"{ad}={deger!r} gecersiz: 'sayi/birim' bekleniyor (birim: s, m, h, d ya da sec, min, hour, day)."
            )
        sonuc[anahtar] = deger
    return sonuc
