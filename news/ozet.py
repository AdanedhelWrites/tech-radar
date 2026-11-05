"""Ana sayfa "Zafiyet Durumu" ozeti (GET /api/ozet/, 2026-10-31 arayuz yenileme).

Pencereler (tasarim ozeti ss.6): kritik = cvss >= 9.0 ve created_at son 24 sa; yuksek =
7.0 <= cvss < 9.0 ve son 7 gun; KEV = kev_added_date son 7 gun (created_at'tan bagimsiz:
CISA'nin ekledigi tarih, kaydin bize geldigi tarih degil).
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Case, IntegerField, Q, When
from django.db.models import F
from django.utils import timezone

from .models import CVEEntry
from .serializers import CVEEntrySerializer

KRITIK_ESIK = 9.0
YUKSEK_ESIK = 7.0
GRAFIK_ESIK = 4.0
PENCERE = timedelta(days=7)
KRITIK_PENCERE = timedelta(hours=24)
ONCELIK_LIMITI = 5
GRAFIK_LIMITI = 40


GRAFIK_BANTLARI = (('kritik', KRITIK_ESIK, None), ('yuksek', YUKSEK_ESIK, KRITIK_ESIK),
                   ('orta', GRAFIK_ESIK, YUKSEK_ESIK))


def _bant_paylari(sayilar: dict, limit: int) -> dict:
    """GRAFIK_LIMITI noktayi bantlara gercek sayilariyla orantili dagitir (en buyuk kalan yontemi).

    2026-11-04: grafik en yuksek 40 skoru aliyordu; haftada 200+ kritik oldugu icin hep "40 kritik, 0 yuksek"
    gorunuyordu. Bos olmayan bant en az bir nokta alir ki dagilim gorunsun.
    """
    toplam = sum(sayilar.values())
    if toplam <= limit:
        return dict(sayilar)
    paylar = {ad: (sayilar[ad] * limit // toplam) for ad in sayilar}
    for ad, sayi in sayilar.items():
        if sayi and not paylar[ad]:
            paylar[ad] = 1
    kalanlar = sorted(sayilar, key=lambda ad: (sayilar[ad] * limit / toplam) - paylar[ad], reverse=True)
    for ad in kalanlar:
        if sum(paylar.values()) >= limit:
            break
        if paylar[ad] < sayilar[ad]:
            paylar[ad] += 1
    while sum(paylar.values()) > limit:  # en az-bir kurali limiti astiysa en buyuk banttan dus
        en_buyuk = max(paylar, key=paylar.get)
        paylar[en_buyuk] -= 1
    return paylar


def _grafik(son_hafta):
    """Bant basina orantili orneklenmis grafik noktalari ve bantlarin gercek sayilari."""
    sayilar, sorgular = {}, {}
    for ad, alt, ust in GRAFIK_BANTLARI:
        sorgu = son_hafta.filter(cvss_score__gte=alt)
        if ust is not None:
            sorgu = sorgu.filter(cvss_score__lt=ust)
        sorgular[ad] = sorgu
        sayilar[ad] = sorgu.count()
    noktalar = []
    for ad, pay in _bant_paylari(sayilar, GRAFIK_LIMITI).items():
        if pay:
            noktalar += list(sorgular[ad].order_by('-cvss_score', '-created_at', 'cve_id')
                             .values('cve_id', 'cvss_score')[:pay])
    return noktalar, sayilar


def yeni_kayit_sayisi(since) -> int:
    """created_at'i `since`'ten sonra olan CVE sayisi."""
    return CVEEntry.objects.filter(created_at__gt=since).count()


def _sonraki_cekim(simdi):
    """CVE cekiminin Beat takvimine gore `simdi`'den sonraki ilk zamani.

    Beat takvimi yerel saatle (schedule.tz) calisir: */6 saat Istanbul saatine gore. remaining_estimate
    celery'nin kendi saatine gore sayar (verilen `simdi`ye degil), bu yuzden remaining_delta ile
    `simdi` yerel saate cevrilip dogrudan toplanir.
    """
    takvim = settings.CELERY_BEAT_SCHEDULE['fetch-cve-every-6h']['schedule']
    yerel = simdi.astimezone(takvim.tz)
    son, kalan, _ = takvim.remaining_delta(yerel)
    return son + kalan


def ozet_hesapla(simdi=None) -> dict:
    from .fetch_runs import bolum_ozetleri
    from .kaynaklar import BOLUMLER, bolum_kaynaklari

    simdi = simdi or timezone.now()
    hafta_basi = simdi - PENCERE
    kev_esigi = simdi.date() - PENCERE

    kayitlar = CVEEntry.objects.all()
    son_hafta = kayitlar.filter(created_at__gte=hafta_basi)
    kev_yeni = Q(kev_added_date__gte=kev_esigi)

    kritik = kayitlar.filter(cvss_score__gte=KRITIK_ESIK, created_at__gte=simdi - KRITIK_PENCERE).count()
    yuksek = son_hafta.filter(cvss_score__gte=YUKSEK_ESIK, cvss_score__lt=KRITIK_ESIK).count()
    kev = kayitlar.filter(kev_yeni).count()

    oncelikli = (son_hafta.filter(Q(cvss_score__gte=YUKSEK_ESIK) | kev_yeni)
                 .annotate(kev_sirasi=Case(When(kev_yeni, then=0), default=1, output_field=IntegerField()))
                 .order_by(F('cvss_score').desc(nulls_last=True), 'kev_sirasi', '-created_at')[:ONCELIK_LIMITI])

    grafik, bant_sayilari = _grafik(son_hafta)
    skorsuz = son_hafta.filter(Q(cvss_score__isnull=True) | Q(cvss_score__lt=GRAFIK_ESIK)).count()

    bolumler = bolum_ozetleri()

    return {
        'generated_at': simdi.isoformat(),
        'critical_count': kritik,
        'high_count': yuksek,
        'kev_count': kev,
        'priority': CVEEntrySerializer(oncelikli, many=True).data,
        'chart': grafik,
        'chart_counts': bant_sayilari,
        'unscored_count': skorsuz,
        'sources': {
            'total': sum(len(bolum_kaynaklari(b)) for b in BOLUMLER),
            'silent': sum(len(b['silent_sources']) for b in bolumler.values()),
        },
        'fetch': {
            'last_success_at': bolumler['cve']['last_success_at'],
            'next_at': _sonraki_cekim(simdi).isoformat(),
        },
    }
