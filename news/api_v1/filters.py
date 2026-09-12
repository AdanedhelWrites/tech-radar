"""v1 query parametrelerini ayristirma ve queryset'e uygulama.

Gecersiz parametre sessizce yok sayilmaz; ValueError firlatilir ve view bunu
400 invalid_parameter yanitina cevirir. Sessiz yok sayma, tuketicinin yanlis
veri aldigini fark etmemesine yol acar.
"""
from .serializers import SEVERITY_CODE_TO_TR, SEVERITY_ORDER

DOGRU_DEGERLER = {'true', '1', 'yes'}
YANLIS_DEGERLER = {'false', '0', 'no'}


def parse_bool(ham):
    """'true'/'false' benzeri degerleri bool'a cevirir. Verilmemisse None doner."""
    if ham is None:
        return None
    kucuk = ham.strip().lower()
    if kucuk in DOGRU_DEGERLER:
        return True
    if kucuk in YANLIS_DEGERLER:
        return False
    raise ValueError(f"Beklenen true/false degeri, alinan: '{ham}'")


def parse_csv(ham):
    """Virgulle ayrilmis listeyi ayristirir; bos ogeler atilir."""
    if not ham:
        return []
    return [parca.strip() for parca in ham.split(',') if parca.strip()]


def min_severity_tr_listesi(kod: str):
    """'high' -> ['Yüksek', 'Kritik'] (veritabanindaki Turkce etiketler).

    Bilinmeyen siddet ('Bilinmiyor') siralamada yer almadigi icin sonuca
    dahil edilmez; siddeti belirsiz bir kaydi 'yuksek ve uzeri' saymak yanlis
    olur.
    """
    kucuk = kod.strip().lower()
    if kucuk not in SEVERITY_ORDER:
        gecerli = ', '.join(SEVERITY_ORDER)
        raise ValueError(f"min_severity su degerlerden biri olmali: {gecerli}")
    esik = SEVERITY_ORDER.index(kucuk)
    return [SEVERITY_CODE_TO_TR[k] for k in SEVERITY_ORDER[esik:]]


def severity_tr_listesi(ham: str):
    """'critical,low' -> ['Kritik', 'Düşük']."""
    kodlar = parse_csv(ham)
    bilinmeyen = [k for k in kodlar if k.lower() not in SEVERITY_ORDER]
    if bilinmeyen:
        gecerli = ', '.join(SEVERITY_ORDER)
        raise ValueError(f"Bilinmeyen severity degeri: {', '.join(bilinmeyen)}. "
                         f"Gecerli degerler: {gecerli}")
    return [SEVERITY_CODE_TO_TR[k.lower()] for k in kodlar]


def ortak_filtreler(queryset, params):
    """Alti bolumde de gecerli olan filtreler."""
    kaynaklar = parse_csv(params.get('source'))
    if kaynaklar:
        queryset = queryset.filter(source__in=kaynaklar)

    bekleyen = parse_bool(params.get('needs_translation'))
    if bekleyen is not None:
        queryset = queryset.filter(needs_translation=bekleyen)

    return queryset
