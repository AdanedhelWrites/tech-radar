"""Celery sinyalleriyle FetchRun satiri acma/kapatma (spec 2026-09-20-a4, bolum 3.3).

Task govdeleri degismez; zengin sayaclar donus sozlesmesinden okunur.
Sinyal hicbir kosulda task'i dusurmez: her govde try/except icindedir ve
hata yalnizca loglanir (news/api_v1/job_signals.py ile ayni kalip).
"""
from datetime import timedelta

from celery.signals import task_failure, task_postrun, task_prerun
from django.utils import timezone

from .models import (
    AINewsEntry, CVEEntry, DevToolsEntry, FetchRun, KubernetesEntry, NewsArticle, SREEntry,
)

TASK_BOLUMLERI = {
    'news.tasks.fetch_news_task': 'news',
    'news.tasks.fetch_cve_task': 'cve',
    'news.tasks.fetch_k8s_task': 'kubernetes',
    'news.tasks.fetch_sre_task': 'sre',
    'news.tasks.fetch_devtools_task': 'devtools',
    'news.tasks.fetch_ai_news_task': 'ai',
    'news.tasks.retranslate_pending_task': 'retranslate',
}

BOLUM_MODELLERI = {
    'news': NewsArticle, 'cve': CVEEntry, 'kubernetes': KubernetesEntry,
    'sre': SREEntry, 'devtools': DevToolsEntry, 'ai': AINewsEntry,
}

HATA_TAVANI = 2000

# task_id -> FetchRun.id. Surec icidir: prerun ve postrun ayni worker alt
# surecinde calisir. Surec arada olursa satir 'running' kalir; aranan sinyal budur.
_acik_turlar = {}


def _bolum(sender):
    return TASK_BOLUMLERI.get(getattr(sender, 'name', None))


def _tetikleyici(sender):
    istek = getattr(sender, 'request', None) or {}
    try:
        deger = istek.get('fetchrun_trigger')
    except AttributeError:
        deger = getattr(istek, 'fetchrun_trigger', None)
    return deger if deger in ('beat', 'api', 'admin') else 'beat'


def eski_kayitlari_temizle(gun: int = 30) -> int:
    """Saklama penceresi disindaki FetchRun satirlarini siler. Donus: silinen sayisi."""
    sinir = timezone.now() - timedelta(days=gun)
    silinen, _ = FetchRun.objects.filter(started_at__lt=sinir).delete()
    return silinen


@task_prerun.connect
def tur_basladi(sender=None, task_id=None, **kwargs):
    try:
        bolum = _bolum(sender)
        if not bolum:
            return
        kayit = FetchRun.objects.create(section=bolum, trigger=_tetikleyici(sender), status='running')
        _acik_turlar[task_id] = kayit.id
    except Exception as hata:
        print(f'  [FetchRun] Satir acilamadi ({task_id}): {hata}')


def _kapat(task_id, **alanlar):
    kayit_id = _acik_turlar.pop(task_id, None)
    if kayit_id is None:
        return
    alanlar['finished_at'] = timezone.now()
    FetchRun.objects.filter(pk=kayit_id).update(**alanlar)


@task_postrun.connect
def tur_bitti(sender=None, task_id=None, retval=None, **kwargs):
    try:
        if not _bolum(sender):
            return
        if not isinstance(retval, dict):
            _kapat(task_id, status='success')
            return

        hata = str(retval.get('error') or '')[:HATA_TAVANI]
        bolum = _bolum(sender)
        if bolum == 'retranslate':
            sayaclar = {
                'saved_count': retval.get('translated', 0) + retval.get('upgraded', 0),
                'translation_failures': retval.get('failed', 0),
                'fetched_count': 0,
                'total_after': 0,
                'by_provider': retval.get('by_provider') or {},
                'stopped_reason': retval.get('stopped_reason') or '',
            }
        else:
            model = BOLUM_MODELLERI[bolum]
            sayaclar = {
                'saved_count': retval.get('count', 0),
                'fetched_count': retval.get('fetched_count', 0),
                'translation_failures': retval.get('translation_failures', 0),
                'total_after': model.objects.count(),
            }
        _kapat(task_id, status='failure' if hata else 'success', error=hata, **sayaclar)
    except Exception as hata:
        print(f'  [FetchRun] Satir kapatilamadi ({task_id}): {hata}')


@task_failure.connect
def tur_coktu(sender=None, task_id=None, exception=None, **kwargs):
    try:
        if not _bolum(sender):
            return
        _kapat(task_id, status='failure', error=f'{type(exception).__name__}: {exception}'[:HATA_TAVANI])
    except Exception as hata:
        print(f'  [FetchRun] Cokme yazilamadi ({task_id}): {hata}')
