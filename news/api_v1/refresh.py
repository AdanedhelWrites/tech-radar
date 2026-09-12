"""Manuel tetikleme: bolum kilidi, soguma ve job kaydi (spec bolum 8).

Uc Redis anahtari kullanilir (onek varsayilan 'refresh'):

  refresh:running:{bolum}  Calisan isin job_id'si. Is bitince task_postrun
                           sinyali siler (job_signals.py). Worker olurse
                           REFRESH_LOCK_TTL sonunda kendiliginden duser.
  refresh:cooldown:{bolum} Son manuel tetiklemeden sonra REFRESH_COOLDOWN saniye.
  refresh:job:{job_id}     job_id -> bolum. Celery bilinmeyen bir id icin de
                           PENDING dondurur; jobs uc noktasi bilinmeyen
                           kimligi bu kayitla ayirt eder.

Bilinen sinir: Beat'in baslattigi isler kilit almaz. Manuel tetikleme bir Beat
calismasiyla cakisabilir; task'lar update_or_create ve skip_existing ile
idempotent oldugu icin veri bozulmaz, yalnizca kaynak sitelere cift istek gider.
"""
import os
from typing import Optional

REFRESH_COOLDOWN = int(os.environ.get('REFRESH_COOLDOWN', '900'))
# En uzun gozlenen cekim 751 sn (CVE, 2026-09-12). Kilit bundan belirgin uzun olmali.
REFRESH_LOCK_TTL = int(os.environ.get('REFRESH_LOCK_TTL', '3600'))
# Celery sonuc backend'inin varsayilan saklama suresiyle ayni (1 gun)
JOB_RECORD_TTL = 86400

# Anahtar degeri beklenen job_id ise siler; baska bir isin kilidini silmez.
_COMPARE_AND_DELETE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def _metin(deger) -> Optional[str]:
    return deger.decode('utf-8') if deger is not None else None


class RefreshGate:
    """Bolum basina kilit, soguma ve job kaydi. Tum surecler Redis uzerinden paylasir."""

    def __init__(self, client, prefix: str = 'refresh'):
        self.client = client
        self.prefix = prefix

    def _anahtar(self, tur: str, ad: str) -> str:
        return f'{self.prefix}:{tur}:{ad}'

    def running_job(self, section: str) -> Optional[str]:
        return _metin(self.client.get(self._anahtar('running', section)))

    def cooldown_remaining(self, section: str) -> int:
        kalan_ms = self.client.pttl(self._anahtar('cooldown', section))
        if kalan_ms is None or kalan_ms <= 0:  # -2: anahtar yok, -1: suresiz
            return 0
        return -(-kalan_ms // 1000)  # yukari yuvarla: 0.4 sn kaldiysa 1 de

    def acquire(self, section: str, job_id: str, lock_ttl: int) -> bool:
        return bool(self.client.set(self._anahtar('running', section), job_id,
                                    nx=True, ex=lock_ttl))

    def start_cooldown(self, section: str, seconds: int) -> None:
        if seconds > 0:
            self.client.set(self._anahtar('cooldown', section), 1, ex=seconds)

    def record_job(self, job_id: str, section: str, ttl: int = JOB_RECORD_TTL) -> None:
        self.client.set(self._anahtar('job', job_id), section, ex=ttl)

    def job_section(self, job_id: str) -> Optional[str]:
        return _metin(self.client.get(self._anahtar('job', job_id)))

    def release(self, section: str, job_id: str) -> bool:
        return bool(self.client.eval(_COMPARE_AND_DELETE, 1,
                                     self._anahtar('running', section), job_id))

    def release_job(self, job_id: str) -> bool:
        section = self.job_section(job_id)
        return self.release(section, job_id) if section else False

    def rollback(self, section: str, job_id: str) -> None:
        """Kuyruga atma basarisiz olursa tetiklemenin tum izlerini siler."""
        self.release(section, job_id)
        self.client.delete(self._anahtar('cooldown', section), self._anahtar('job', job_id))
