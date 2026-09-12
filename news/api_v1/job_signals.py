"""Celery sinyalleri: manuel tetiklenen is bitince bolum kilidini birakir.

Worker surecinde news uygulamasi yuklenirken (NewsConfig.ready) import edilir.
Kilit birakilamazsa is basarisiz sayilmaz; REFRESH_LOCK_TTL emniyet agidir.
"""
from celery.signals import task_postrun


@task_postrun.connect
def refresh_kilidini_birak(sender=None, task_id=None, **kwargs):
    # get_gate burada, cagri aninda import edilir; testler onu patch'leyebilsin
    from .refresh import get_gate
    try:
        get_gate().release_job(task_id)
    except Exception as hata:
        print(f'  [Refresh] Kilit birakilamadi ({task_id}): {hata}')
