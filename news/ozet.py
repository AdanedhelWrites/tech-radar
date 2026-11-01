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

    grafik = list(son_hafta.filter(cvss_score__gte=GRAFIK_ESIK).order_by('-cvss_score', '-created_at', 'cve_id')
                  .values('cve_id', 'cvss_score')[:GRAFIK_LIMITI])
    skorsuz = son_hafta.filter(Q(cvss_score__isnull=True) | Q(cvss_score__lt=GRAFIK_ESIK)).count()

    bolumler = bolum_ozetleri()

    return {
        'generated_at': simdi.isoformat(),
        'critical_count': kritik,
        'high_count': yuksek,
        'kev_count': kev,
        'priority': CVEEntrySerializer(oncelikli, many=True).data,
        'chart': grafik,
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
