"""CISA KEV onegi: CISAKEVScraper aciklamanin basina eklenme/son islem tarihini yazar."""
import re
from datetime import date, datetime

KEV_ONEK = re.compile(
    r'^Added to the CISA KEV catalog on (\d{4}-\d{2}-\d{2})'
    r'(?:; required action due (\d{4}-\d{2}-\d{2}))?\.\s*')


def _tarih(metin):
    try:
        return datetime.strptime(metin, '%Y-%m-%d').date()
    except ValueError:
        return None


def kev_oneki_ayir(metin: str) -> tuple[date | None, date | None, str]:
    """(eklenme tarihi, son islem tarihi, onegi atilmis govde) dondurur.

    Onek yalnizca metnin basindaysa taninir; yoksa ya da tarih gecersizse metin aynen doner.
    """
    eslesme = KEV_ONEK.match(metin or '')
    if not eslesme:
        return None, None, metin
    eklenme = _tarih(eslesme.group(1))
    if eklenme is None:
        return None, None, metin
    son = _tarih(eslesme.group(2)) if eslesme.group(2) else None
    return eklenme, son, metin[eslesme.end():]
