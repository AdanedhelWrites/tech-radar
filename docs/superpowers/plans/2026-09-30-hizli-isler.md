# Hizli Isler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dependabot PR #44/#45'i almak, uretimde placeholder `SECRET_KEY` ve `ALLOWED_HOSTS='*'` ile acilmayi engellemek ve eski `POST /api/*/fetch/` uclarini v1'in bolum kilidi + soguma kapisindan gecirmek.

**Architecture:** `SECRET_KEY` kontrolu saf bir fonksiyona (`cybernews/ayar_dogrulama.py`) yazilir, `settings.py` onu cagirir. Eski fetch uclari `news/api_v1/refresh.py::trigger()`'i (iki yeni istege bagli parametreyle) kullanan tek bir `_tetikle()` yardimcisina toplanir; kilit ve soguma v1 ile ayni Redis anahtarlarini paylasir. Frontend, sunucunun `message` alanini gosteren ortak bir yardimci kullanir.

**Tech Stack:** Django 5.2.17, DRF 3.18.1, Celery 5.6, Redis, React 18 + Vite 6, docker compose, Helm 3, GitHub Actions, `gh` CLI.

**Spec:** [`docs/superpowers/specs/2026-09-30-hizli-isler-design.md`](../specs/2026-09-30-hizli-isler-design.md) — once onu oku.

## Global Constraints

- Tum komutlar depo kokunden calisir: `C:\Users\Adanedhel\Desktop\OpenCodeProjects\CyberNews\cybersecurity_news` (Bash: `/c/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news`).
- Testler **yalniz** konteynerde: `docker compose exec -T teknoloji-api python manage.py test news` (kod bind mount ile canli; test icin yeniden baslatma gerekmez). Tek modul: `... test news.tests.test_x`.
- Testler hicbir zaman gercek Celery isi kuyruga atmaz ve `FLUSHDB` kullanmaz. Tetikleme testleri `news/tests/base.py::RefreshTestMixin` kullanir (gate'i benzersiz onekle kurar, alti task'in `apply_async`'ini mock'lar).
- Kod stili: Turkce ASCII tanimlayici/yorum (`_tetikle`, `dogrulanmis_secret_key`), kullaniciya giden backend mesajlari ASCII Turkce ("cekimi baslatildi"). Frontend metinleri Turkce karakterli kalir.
- v1 (`/api/v1/`) davranisi **degismez**. `refresh.trigger('cve')` parametresiz cagrildiginda task'a `kwargs={'skip_existing': True}` ve `headers={'fetchrun_trigger': 'api'}` gitmeye devam eder.
- Eski uclarin URL'leri, view fonksiyon adlari ve basari yanit zarfi (`success/message/count/data`) degismez.
- `SECRET_KEY` degeri hicbir komut ciktisina, loga veya commit'e yazilmaz. `.env` gitignore'dadir; asla `git add` edilmez.
- `.gitleaksignore` **degistirilmez**.
- Her is ayri dal; `git merge --no-ff`; kapiyi gecemeyen is geri alinir, push edilmez, rapor edilir.
- Commit mesajlari su satirla biter:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (uygulayan model farkliysa kendi adini yazar).

### Tam kapi (Task 4 ve Task 8'de kullanilir)

```bash
# 1. Yigini yeniden kur (ortam degiskeni degistiyse --force-recreate sart)
docker compose up -d --build --force-recreate teknoloji-api teknoloji-worker teknoloji-scheduler

# 2. Alti servis Up mi
docker compose ps --format "{{.Service}} {{.Status}}"

# 3. Testler
docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^Ran |^OK|^FAILED"

# 4. Sema
docker compose exec -T teknoloji-api python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybernews.settings')
django.setup()
from drf_spectacular.drainage import reset_generator_stats, GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator
reset_generator_stats()
schema = SchemaGenerator().get_schema(request=None, public=True)
print('Yol sayisi:', len(schema.get('paths', {})))
print('warnings:', dict(GENERATOR_STATS._warn_cache))
print('errors:', dict(GENERATOR_STATS._error_cache))
"

# 5. Canli HTTP
curl -s -o /dev/null -w "health:%{http_code}\n" http://localhost:8000/api/v1/health/
curl -s -o /dev/null -w "schema:%{http_code}\n" http://localhost:8000/api/v1/schema/
curl -s -o /dev/null -w "admin:%{http_code}\n" http://localhost:8000/admin/login/
curl -s -o /dev/null -w "frontend:%{http_code}\n" http://localhost:3000/

# 6. Worker ve beat ayakta mi
docker compose logs --since 3m teknoloji-worker teknoloji-scheduler 2>&1 | grep -E "ready|beat: Starting"
```

Beklenen: alti servis `Up` | `Ran N tests ... OK` (N >= 326 + o ana kadar eklenen testler) | `Yol sayisi: 11`, `warnings: {}`, `errors: {}` | `health:200`, `schema:401`, `admin:200`, `frontend:200` | `celery@... ready` ve `beat: Starting...`.

Uctan uca istemci (tam kapinin son parcasi):

```bash
TOKEN=$(docker compose exec -T teknoloji-api python manage.py shell -c "
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
U = get_user_model()
u, _ = U.objects.get_or_create(username='plan_dogrulama', defaults={'is_staff': True})
t, _ = Token.objects.get_or_create(user=u)
print(t.key)
" | tr -d '\r' | tail -1)

CYBERNEWS_TOKEN="$TOKEN" CYBERNEWS_URL=http://localhost:8000 python scripts/ornek_istemci.py

docker compose exec -T teknoloji-api python manage.py shell -c "
from django.contrib.auth import get_user_model
get_user_model().objects.filter(username='plan_dogrulama').delete()
print('silindi')
"
rm -f scripts/ornek_istemci_durum.json
```

Beklenen: alti bolum icin `degisen=` satirlari ve `... kayit upsert edildi`, sonra `silindi`.

### Dal ve merge akisi

```bash
git checkout main && git pull --ff-only origin main
git checkout -b <dal>
# ... gorevler + commit'ler ... tam kapi ...
git checkout main
git merge --no-ff <dal> -m "Merge <dal>: <kisa aciklama>"
git push origin main
git branch -d <dal>
```

---

### Task 1: Dependabot PR #44 (react-hot-toast 2.6.0 -> 2.6.1)

**Files:** yok (GitHub PR'i; `frontend/package.json`, `frontend/package-lock.json` PR icinde)

**Interfaces:**
- Consumes: yok
- Produces: yok

- [ ] **Step 1: PR durumunu ve diff'i oku**

```bash
gh pr view 44 --json title,mergeable,mergeStateStatus,files --jq '{title,mergeable,mergeStateStatus,files:[.files[].path]}'
gh pr checks 44
gh pr diff 44 | head -80
```

Beklenen: `mergeable: MERGEABLE`, dosyalar yalniz `frontend/package.json` ve `frontend/package-lock.json`, diff yalniz `react-hot-toast` (ve varsa onun lockfile girdileri). Check listesinde `Backend (Django testleri)` yoksa `gh pr update-branch 44` calistir ve check'lerin bitmesini bekle (`gh pr checks 44 --watch`).

- [ ] **Step 2: Check'lerin hepsi `pass` (veya `skipping`) ise merge et**

Herhangi biri `fail` ise **merge etme**; hangi check'in kirildigini rapor et ve Task 2'ye gec.

```bash
gh pr merge 44 --merge
git checkout main && git pull --ff-only origin main
```

- [ ] **Step 3: Frontend yeni paketle aciliyor mu**

Dev sunucusu acilista `npm install` calistirir; yeniden baslat:

```bash
docker compose restart teknoloji-frontend
```

Frontend'in hazir olmasini bekle (npm install ~30-60 sn surer), sonra:

```bash
curl -s -o /dev/null -w "frontend:%{http_code}\n" http://localhost:3000/
docker compose logs --since 3m teknoloji-frontend 2>&1 | grep -iE "ready in|error" | tail -5
```

Beklenen: `frontend:200` ve `VITE ... ready in` satiri, `error` yok.

---

### Task 2: Dependabot PR #45 (actions grubu, 3 guncelleme)

**Files:** yok (GitHub PR'i; `.github/workflows/*.yml` ve/veya `.github/actions/*` PR icinde)

**Interfaces:**
- Consumes: yok
- Produces: yok

- [ ] **Step 1: Diff'i satir satir oku**

```bash
gh pr view 45 --json title,mergeable,mergeStateStatus,files --jq '{title,mergeable,mergeStateStatus,files:[.files[].path]}'
gh pr diff 45
```

Kontrol listesi (hepsi saglanmali):
1. Her degisen `uses:` satiri **40 karakterlik SHA + `# vX.Y.Z` yorumu** bicimini korur (ornek: `uses: actions/checkout@3d3c... # v7.0.1`). Etiket (`@v7`) veya dal referansi **olmamali**.
2. `.github/workflows/trivy.yml`'deki `uses: $/.github/actions/setup-trivy` satirlarina **dokunulmamis** olmali (2026-09-22'de `151cdd7` ile geri alinan zizmor regresyonu).
3. Yalniz surum yukseltmesi var; yeni `permissions:`, yeni adim veya `run:` degisikligi yok.

Biri saglanmazsa **merge etme**; bulguyu rapor et ve Task 3'e gec.

- [ ] **Step 2: Check'ler**

```bash
gh pr checks 45
```

Check listesinde `Backend (Django testleri)` yoksa `gh pr update-branch 45` + `gh pr checks 45 --watch`. Hepsi `pass`/`skipping` degilse merge etme, rapor et.

- [ ] **Step 3: Merge**

```bash
gh pr merge 45 --merge
git checkout main && git pull --ff-only origin main
```

- [ ] **Step 4: main uzerindeki koşulari dogrula**

Merge'den ~5 dk sonra:

```bash
gh run list --branch main --limit 10 --json name,conclusion,status --jq '.[] | "\(.name) \(.status) \(.conclusion)"'
```

Beklenen: `CI`, `zizmor`, `trivy`, `gitleaks`, `CodeQL Advanced` `completed success`. Kirmizi varsa rapor et (geri alma karari koordinatorundur).

---

### Task 3: `SECRET_KEY` dogrulama fonksiyonu ve `settings.py` baglantisi

**Files:**
- Create: `cybernews/ayar_dogrulama.py`
- Create: `news/tests/test_ayar_dogrulama.py`
- Modify: `cybernews/settings.py:14-21`
- Modify: `docker-compose.yml` (satir 12, 90, 115)
- Modify: `.env` (yerel, commit'lenmez)

**Interfaces:**
- Consumes: yok
- Produces: `cybernews.ayar_dogrulama.dogrulanmis_secret_key(anahtar: Optional[str], debug: bool) -> str` (hata: `django.core.exceptions.ImproperlyConfigured`); `cybernews.ayar_dogrulama.GELISTIRME_ANAHTARI: str`; `cybernews.ayar_dogrulama.BILINEN_ORNEKLER: frozenset[str]`

- [ ] **Step 1: Dali ac**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b fix/secret-key-korumasi
```

- [ ] **Step 1b: Once calisan yigina gercek anahtari ver (settings'ten ONCE — sira kritik)**

Neden once: gunicorn `--preload` olmadan calisir (`Dockerfile` CMD). Step 6'daki `settings.py` degisikliginden sonra bir gunicorn worker'i yeniden dogarsa (timeout vb.) yeni settings'i compose'un placeholder anahtariyla yukler ve **api coker**. Bu yuzden anahtar ve compose once degisir, yigin yeniden olusturulur; settings sonra degisir.

Yerel `.env`'e anahtar ekle (degeri yazdirmadan):

```bash
[ -n "$(tail -c1 .env)" ] && echo >> .env
grep -q '^SECRET_KEY=' .env || printf 'SECRET_KEY=%s\n' "$(python -c 'import secrets;print(secrets.token_hex(32))')" >> .env
grep -c '^SECRET_KEY=' .env
git check-ignore -q .env && echo ".env ignore'da"
```

Beklenen: `1` ve `.env ignore'da`. **`cat .env` calistirma.**

`docker-compose.yml`'de uc serviste (teknoloji-api satir 12, teknoloji-worker satir 90, teknoloji-scheduler satir 115) su satiri:

```yaml
      - SECRET_KEY=your-secret-key-here-change-in-production
```

su iki satirla degistir:

```yaml
      - SECRET_KEY=${SECRET_KEY:?SECRET_KEY .env icinde tanimli olmali (openssl rand -hex 32)}
      - ALLOWED_HOSTS=localhost,127.0.0.1,teknoloji-api
```

Dogrula ve yigini yeni ortamla olustur:

```bash
grep -c 'your-secret-key-here' docker-compose.yml
grep -c 'ALLOWED_HOSTS=localhost,127.0.0.1,teknoloji-api' docker-compose.yml
docker compose config --quiet && echo "compose config OK"
docker compose up -d --force-recreate teknoloji-api teknoloji-worker teknoloji-scheduler
docker compose exec -T teknoloji-api python -c "import os; print(len(os.environ['SECRET_KEY']), os.environ['ALLOWED_HOSTS'])"
curl -s -o /dev/null -w "health:%{http_code}\n" http://localhost:8000/api/v1/health/
curl -s -o /dev/null -w "frontend-api:%{http_code}\n" http://localhost:3000/api/stats/
```

Beklenen: `0`, `3`, `compose config OK`, `64 localhost,127.0.0.1,teknoloji-api`, `health:200`, `frontend-api:200`. (Admin oturumu bu adimda bir kez duser; beklenen.)

- [ ] **Step 2: Basarisiz testi yaz**

`news/tests/test_ayar_dogrulama.py`:

```python
"""cybernews/ayar_dogrulama.py: uretimde ornek/zayif SECRET_KEY ile acilmayi reddetme.

Test kesfi yalniz `news` altinda calistigi icin (manage.py test news) test burada durur.
"""
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from cybernews.ayar_dogrulama import (
    BILINEN_ORNEKLER, GELISTIRME_ANAHTARI, dogrulanmis_secret_key,
)

GUCLU = 'a3f1' * 16  # 64 karakter, openssl rand -hex 32 ciktisi uzunlugunda


class UretimdeReddetmeTest(SimpleTestCase):

    def test_bos_anahtar_reddedilir(self):
        for deger in (None, ''):
            with self.subTest(deger=deger), self.assertRaises(ImproperlyConfigured):
                dogrulanmis_secret_key(deger, debug=False)

    def test_bilinen_ornekler_reddedilir(self):
        for deger in BILINEN_ORNEKLER:
            with self.subTest(deger=deger), self.assertRaises(ImproperlyConfigured):
                dogrulanmis_secret_key(deger, debug=False)

    def test_depodaki_tum_ornekler_listede(self):
        """compose, helm, k8s, README ve kokteki values.yaml'da gecmis degerler."""
        self.assertLessEqual({
            'your-secret-key-here-change-in-production',
            'buraya-guclu-rastgele-secret-key-yazin-min-50-karakter',
            'min-50-karakter-rastgele-guclu-bir-key',
            'django-insecure-change-in-production',
        }, BILINEN_ORNEKLER)

    def test_django_insecure_onekli_reddedilir(self):
        with self.assertRaises(ImproperlyConfigured):
            dogrulanmis_secret_key('django-insecure-' + 'x' * 60, debug=False)

    def test_kisa_anahtar_reddedilir(self):
        with self.assertRaises(ImproperlyConfigured):
            dogrulanmis_secret_key('k' * 31, debug=False)

    def test_hata_mesaji_anahtari_icermez(self):
        with self.assertRaises(ImproperlyConfigured) as baglam:
            dogrulanmis_secret_key('gizli-ama-kisa', debug=False)
        self.assertNotIn('gizli-ama-kisa', str(baglam.exception))

    def test_guclu_anahtar_aynen_doner(self):
        self.assertEqual(dogrulanmis_secret_key(GUCLU, debug=False), GUCLU)


class GelistirmedeEsneklikTest(SimpleTestCase):

    def test_debug_bos_anahtarda_gelistirme_anahtari_doner(self):
        self.assertEqual(dogrulanmis_secret_key(None, debug=True), GELISTIRME_ANAHTARI)
        self.assertEqual(dogrulanmis_secret_key('', debug=True), GELISTIRME_ANAHTARI)

    def test_debug_verilen_anahtari_dogrulamadan_kullanir(self):
        self.assertEqual(dogrulanmis_secret_key('kisa', debug=True), 'kisa')
```

- [ ] **Step 3: Testin kirildigini gor**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_ayar_dogrulama 2>&1 | tail -5
```

Beklenen: `ModuleNotFoundError: No module named 'cybernews.ayar_dogrulama'` (ImportError ile FAILED/ERROR).

- [ ] **Step 4: Fonksiyonu yaz**

`cybernews/ayar_dogrulama.py`:

```python
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
```

- [ ] **Step 5: Testlerin gectigini gor**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_ayar_dogrulama 2>&1 | grep -E "^Ran |^OK|^FAILED"
```

Beklenen: `Ran 9 tests` ve `OK`.

- [ ] **Step 6: `settings.py`'yi bagla**

`cybernews/settings.py` satir 14-21 su an:

```python
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# ALLOWED_HOSTS — virgülle ayrılmış liste veya '*'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')
```

Su hale getir (DEBUG once okunur, cunku anahtar dogrulamasi ona bagli). Dosyanin basindaki importlara `from cybernews.ayar_dogrulama import dogrulanmis_secret_key` ekle (`from pathlib import Path` satirinin altina):

```python
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# DEBUG=False iken bos, ornek veya zayif anahtarla acilmayi reddeder (GUVENLIK-PLANI P4)
SECRET_KEY = dogrulanmis_secret_key(os.environ.get('SECRET_KEY'), DEBUG)

# ALLOWED_HOSTS — virgülle ayrılmış liste; '*' yalnizca acikca verilirse
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if host.strip()
]
```

- [ ] **Step 7: Tum paket ve reddetme kaniti**

Step 1b sayesinde konteyner gercek anahtarla calisiyor:

```bash
docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^Ran |^OK|^FAILED"
docker compose restart teknoloji-api && sleep 10
curl -s -o /dev/null -w "health:%{http_code}\n" http://localhost:8000/api/v1/health/
```

Beklenen: `OK` (326 + 9 = 335 test) ve yeni settings ile yeniden baslayan api'de `health:200`.

Placeholder ile gercekten reddedildigini kanitla:

```bash
docker compose exec -T -e SECRET_KEY=your-secret-key-here-change-in-production teknoloji-api python manage.py check 2>&1 | tail -1
```

Beklenen: `django.core.exceptions.ImproperlyConfigured: SECRET_KEY depodaki bir ornek deger. ...`

- [ ] **Step 8: Commit**

```bash
git add cybernews/ayar_dogrulama.py cybernews/settings.py news/tests/test_ayar_dogrulama.py docker-compose.yml
git status --short | grep -c "\.env$"
```

Ikinci komut `0` vermeli (`.env` asla eklenmez).

```bash
git commit -m "fix: uretimde ornek/zayif SECRET_KEY ile acilmayi reddet, ALLOWED_HOSTS varsayilanini daralt

Compose uc serviste placeholder yerine \${SECRET_KEY:?} (.env) ve acik ALLOWED_HOSTS.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `.env.example`, CI, Helm, k8s ve belgeler; tam kapi ve merge

**Files:**
- Modify: `.env.example`
- Modify: `.github/workflows/ci.yml` (`manifests` isi, "helm lint + template" ve "docker compose config" adimlari)
- Modify: `.github/workflows/trivy.yml` (satir 50-56, "Tara" adimi)
- Modify: `helm/tech-radar/values.yaml:302`
- Modify: `helm/tech-radar/templates/secret.yaml:10`
- Rename: `k8s/02-secret.yaml` -> `k8s/02-secret.yaml.example`
- Delete: `values.yaml` (kok dizin)
- Modify: `README.md` (satir ~468, ~479-495 agac, ~644-651, ~676, ~876-878)
- Modify: `docs/GUVENLIK-PLANI.md`

**Interfaces:**
- Consumes: Task 3'un `settings.py` davranisi (DEBUG=False + zayif anahtar -> ImproperlyConfigured) ve compose'un `${SECRET_KEY:?...}` satirlari
- Produces: yok (CI/Helm/k8s/belge uyumu)

Ayni dal (`fix/secret-key-korumasi`) uzerinde devam edilir.

- [ ] **Step 2: `.env.example`**

Dosyanin sonuna ekle:

```
# Django imza anahtari. DEBUG=False iken zorunlu; bos, ornek ya da 32 karakterden
# kisa deger uygulamayi acmaz. Uretmek icin: openssl rand -hex 32
SECRET_KEY=
```

- [ ] **Step 3: Compose anahtarsiz calismayi reddediyor mu**

```bash
env -u SECRET_KEY docker compose --env-file /dev/null config --quiet 2>&1 | tail -1
```

Beklenen: `SECRET_KEY .env icinde tanimli olmali` iceren hata satiri.

- [ ] **Step 4: CI `manifests` isi**

`.github/workflows/ci.yml`'de:

```yaml
      - name: helm lint + template
        run: |
          set -euo pipefail
          helm lint helm/tech-radar
          helm template tech-radar helm/tech-radar > rendered.yaml
```

su hale gelir:

```yaml
      - name: helm lint + template
        run: |
          set -euo pipefail
          # secrets.secretKey bilincli olarak bos ve `required`; CI sahte deger verir
          helm lint helm/tech-radar --set secrets.secretKey=ci-dogrulama-icin-sahte-deger
          helm template tech-radar helm/tech-radar --set secrets.secretKey=ci-dogrulama-icin-sahte-deger > rendered.yaml
```

ve

```yaml
      - name: docker compose config
        run: docker compose -f docker-compose.yml config --quiet
```

su hale gelir:

```yaml
      - name: docker compose config
        # SECRET_KEY compose'da `:?` ile zorunlu; CI sahte deger verir
        run: SECRET_KEY=ci-dogrulama-icin-sahte-deger docker compose -f docker-compose.yml config --quiet
```

- [ ] **Step 5: Trivy'nin helm taramasi `required` yuzunden sessizce atlanmasin**

`.github/workflows/trivy.yml` "Tara" adiminda `--skip-dirs _arsiv \` satirinin altina ekle:

```yaml
            --helm-set secrets.secretKey=trivy-tarama-icin-sahte-deger \
```

- [ ] **Step 6: Helm**

`helm/tech-radar/values.yaml` satir 302:

```yaml
  secretKey: "buraya-guclu-rastgele-secret-key-yazin-min-50-karakter"
```

->

```yaml
  # Zorunlu; bos birakilirsa `helm install` hata verir. Uretmek icin: openssl rand -hex 32
  # Ornek: helm install ... --set secrets.secretKey="$(openssl rand -hex 32)"
  secretKey: ""
```

`helm/tech-radar/templates/secret.yaml` satir 10:

```yaml
  SECRET_KEY: {{ .Values.secrets.secretKey | quote }}
```

->

```yaml
  SECRET_KEY: {{ required "secrets.secretKey zorunlu (openssl rand -hex 32)" .Values.secrets.secretKey | quote }}
```

Helm yerelde kuruluysa dogrula (kurulu degilse bu adimi atla, CI dogrular):

```bash
helm template t helm/tech-radar > /dev/null 2>&1 && echo "HATA: bos anahtarla render edildi" || echo "bos anahtar reddedildi"
helm template t helm/tech-radar --set secrets.secretKey=x > /dev/null && echo "anahtarla render OK"
```

- [ ] **Step 7: k8s ve kok `values.yaml`**

```bash
git mv k8s/02-secret.yaml k8s/02-secret.yaml.example
grep -rn "values.yaml" --include=*.yml --include=*.yaml --include=*.py --include=*.sh --include=Dockerfile . | grep -v node_modules | grep -v "helm/tech-radar" | grep -v "^./docs/"
```

Son komut kokteki `values.yaml`'a **hicbir** kod/CI referansi gostermemeli (bos cikti). Bos ise:

```bash
git rm values.yaml
```

Bos degilse durma, ciktiyi rapor et.

`k8s/02-secret.yaml.example`'in basina (ilk satirdan once) ekle:

```yaml
# ORNEK DOSYA — dogrudan uygulanmaz. Uzanti bilincli olarak .yaml ile bitmez:
# `kubectl apply -f k8s/` bu dosyayi atlar ve gercek secret'in ustune placeholder yazmaz.
# Kullanim: cp k8s/02-secret.yaml.example k8s/02-secret.yaml (gitignore'da degil — commit'lemeyin)
# veya README'deki `kubectl create secret generic` komutunu kullanin.
```

Ayni dosyada `SECRET_KEY:` satirinin degerini bos yap:

```yaml
  SECRET_KEY: ""  # openssl rand -hex 32
```

`.gitignore`'a ekle (dosyanin sonuna):

```
# Gercek k8s secret'i (ornegi: k8s/02-secret.yaml.example)
k8s/02-secret.yaml
```

- [ ] **Step 8: README**

Asagidaki degisiklikleri yap (satir numaralari yaklasiktir; metinle bul):

1. Agactaki `│   ├── 02-secret.yaml          # Gizli bilgiler (placeholder)` -> `│   ├── 02-secret.yaml.example  # Secret ornegi (dogrudan uygulanmaz)`
2. Agactaki `├── values.yaml                 # Root-level values referansi (Helm chart'a kopyasi)` satirini sil.
3. "Adim 2 — Secret'lari Olusturun" altindaki paragraf ve YAML blogu:

   ```
   `k8s/02-secret.yaml` dosyasindaki placeholder degerleri gercek degerlerle degistirin:

   ```yaml
   stringData:
     SECRET_KEY: "min-50-karakter-rastgele-guclu-bir-key"
   ```

   yerine:

   ```
   `k8s/02-secret.yaml.example` dosyasini `k8s/02-secret.yaml` olarak kopyalayip degerleri doldurun (`k8s/02-secret.yaml` gitignore'dadir):

   ```yaml
   stringData:
     SECRET_KEY: ""  # openssl rand -hex 32 — bos, ornek veya 32 karakterden kisa deger uygulamayi acmaz
   ```

   (Blogun geri kalan satirlari — `DB_USER`, `DB_PASSWORD`, `POSTGRES_PASSWORD` — aynen kalir.)
4. `kubectl apply -f k8s/02-secret.yaml` satiri aynen kalir (kopyalanan gercek dosyayi uygular).
5. "Ortam Degiskenleri" tablosunda:

   `| `SECRET_KEY` | `django-insecure-...` | Django secret key (production'da mutlaka degistirin) |`
   ->
   `| `SECRET_KEY` | (yok) | Zorunlu (`DEBUG=False` iken). Bos, depodaki ornek degerler, `django-insecure` onekli veya 32 karakterden kisa anahtar uygulamayi acmaz. Compose `.env`'den okur. Uretmek icin `openssl rand -hex 32` |`

   `| `ALLOWED_HOSTS` | `*` | Virgulle ayrilmis izinli host listesi |`
   ->
   `| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Virgulle ayrilmis izinli host listesi. Compose `localhost,127.0.0.1,teknoloji-api` verir. Kubernetes probe'lari pod IP'siyle geldigi icin K8s'te acikca ayarlanmali |`

6. Tablonun hemen altina ekle:

   ```
   > **Hostta `manage.py` calistirmak:** `DEBUG` varsayilani `False` oldugu icin anahtarsiz
   > `python manage.py ...` artik reddedilir. Yerelde `DEBUG=True python manage.py ...`
   > kullanin ya da komutu konteynerde calistirin (`docker compose exec teknoloji-api ...`).
   ```

Dogrula:

```bash
grep -n "min-50-karakter\|buraya-guclu\|your-secret-key-here" README.md docker-compose.yml helm/tech-radar/values.yaml k8s/02-secret.yaml.example
```

Beklenen: cikti yok.

- [ ] **Step 9: `docs/GUVENLIK-PLANI.md`**

1. Ust not satirini `> Son güncelleme: 2026-09-30 (P1, P2, P4 SECRET_KEY tamamlandı).` yap.
2. **P1** basligini `### P1: Django 4.2 → 5.2 yükseltmesi ✅ (2026-09-22)` yap ve altindaki tum `- [ ]` kutularini `- [x]` yap; P1 basliginin hemen altina ekle: `Uygulandı: Django 5.2.16 (2026-09-22), 5.2.17 PR #43 (2026-09-30). Ayrıntı: superpowers/specs/2026-09-22-guvenlik-temizligi-design.md.`
3. **P2**'deki `- [ ]` kutularini `- [x]` yap (vite 6, Node 22, react-router 7 2026-09-22'de uygulandi).
4. **P4**'te `SECRET_KEY` placeholder'ini `.env`'e tasima maddesini ve "Varsayılan SECRET_KEY ile deploy riski" maddesini `- [x]` yap. "Varsayılan SECRET_KEY" maddesinin alt maddelerini su metinle degistir:

   ```
     - helm: `secretKey` boş, template'te `required` ✅
     - k8s: `02-secret.yaml` → `02-secret.yaml.example` ✅ (uzantı `.yaml` ile bitmez: `kubectl apply -f k8s/` onu atlar)
     - `settings.py`: `DEBUG=False` iken boş/örnek/zayıf `SECRET_KEY` ile açılmayı reddeder ✅ (`cybernews/ayar_dogrulama.py`)
     - `.gitleaksignore` **değiştirilmedi**: girdiler geçmiş commit'lere sabitli; silinirse geçmiş taraması yeniden kırmızı olur. (İlk plandaki "baseline'dan da silinmeli" maddesi bu yüzden geçersiz.)
   ```

5. "## 5. Geçmiş" listesinin sonuna ekle:

   ```
   - **2026-09-22:** Güvenlik temizliği: P1 ve P2 uygulandı, Dependabot 14 → 0, code scanning 89 → 11 (ayrıntı: superpowers/specs/2026-09-22-guvenlik-temizligi-design.md).
   - **2026-09-30:** PR #43 (Django 5.2.17) merge. P4 SECRET_KEY/ALLOWED_HOSTS koruması (superpowers/specs/2026-09-30-hizli-isler-design.md).
   ```

- [ ] **Step 10: Commit**

```bash
git add .env.example .gitignore .github/workflows/ci.yml .github/workflows/trivy.yml \
  helm/tech-radar/values.yaml helm/tech-radar/templates/secret.yaml k8s/02-secret.yaml.example \
  README.md docs/GUVENLIK-PLANI.md
git status --short
```

`git status --short` ciktisinda `.env` **olmamali**; `R  k8s/02-secret.yaml -> k8s/02-secret.yaml.example` ve `D  values.yaml` gorunmeli.

```bash
git commit -m "fix: helm'de SECRET_KEY'i zorunlu yap, k8s secret'ini ornege cevir

CI manifests ve trivy helm taramasi sahte anahtar verir. Kokteki bayat
values.yaml silindi. GUVENLIK-PLANI P1/P2/P4 guncellendi.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 11: Tam kapi**

Yukaridaki "Tam kapi" bolumunu eksiksiz calistir (`--force-recreate` sart: ortam degiskeni degisti). Ek kanit:

```bash
docker compose exec -T teknoloji-api python -c "
import os; print('anahtar uzunlugu:', len(os.environ['SECRET_KEY'])); print('ALLOWED_HOSTS:', os.environ['ALLOWED_HOSTS'])"
docker compose exec -T teknoloji-api python manage.py check --deploy 2>&1 | grep -c "security.W009"
curl -s -o /dev/null -w "kotu-host:%{http_code}\n" -H "Host: saldirgan.example" http://localhost:8000/api/v1/health/
curl -s -o /dev/null -w "frontend-api:%{http_code}\n" http://localhost:3000/api/stats/
```

Beklenen: `anahtar uzunlugu: 64`, `ALLOWED_HOSTS: localhost,127.0.0.1,teknoloji-api`, `0` (W009 = zayif SECRET_KEY uyarisi yok), `kotu-host:400`, `frontend-api:200` (Vite proxy `teknoloji-api` host'uyla geciyor).

Kapi gecmezse **merge ve push etme**. Yigini main'deki haline dondur:

```bash
git checkout main
docker compose up -d --force-recreate teknoloji-api teknoloji-worker teknoloji-scheduler
curl -s -o /dev/null -w "health:%{http_code}\n" http://localhost:8000/api/v1/health/
```

Dali silme (`fix/secret-key-korumasi` inceleme icin kalir); neyin kirildigini rapor et ve dur. Task 5-8 bu dala bagli degildir ama saglam bir yigin olmadan tam kapilari anlamsizdir; koordinatorun kararini bekle.

- [ ] **Step 12: Merge ve push**

```bash
git checkout main
git merge --no-ff fix/secret-key-korumasi -m "Merge fix/secret-key-korumasi: uretimde zayif SECRET_KEY reddi, ALLOWED_HOSTS daraltma"
git push origin main
git branch -d fix/secret-key-korumasi
```

~5 dk sonra:

```bash
gh run list --branch main --limit 10 --json name,conclusion,status --jq '.[] | "\(.name) \(.status) \(.conclusion)"'
```

Beklenen: `CI` (ozellikle "Helm / Compose dogrulama"), `trivy`, `gitleaks` `success`. `trivy` koşusunun "Tarama gercekten bir sey gordu mu" adiminda `misconfig hedefi` sayisi onceki koşudan dusmemeli:

```bash
gh run view $(gh run list --workflow trivy.yml --branch main --limit 1 --json databaseId --jq '.[0].databaseId') --log 2>/dev/null | grep "misconfig hedefi" | tail -1
```

---

### Task 5: `refresh.trigger()` icin `task_kwargs` ve `trigger_label`

**Files:**
- Modify: `news/api_v1/refresh.py:120-154` (`trigger` fonksiyonu)
- Test: `news/tests/test_refresh.py` (sonuna yeni sinif)

**Interfaces:**
- Consumes: yok
- Produces: `refresh.trigger(section: str, gate: Optional[RefreshGate] = None, cooldown: Optional[int] = None, lock_ttl: Optional[int] = None, task_kwargs: Optional[dict] = None, trigger_label: str = 'api') -> TriggerResult`. `TriggerResult.status` degerleri: `'started' | 'already_running' | 'cooldown'`; `job_id: Optional[str]`; `retry_after: int` (saniye).

- [ ] **Step 1: Dali ac**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b fix/eski-fetch-kapisi
```

- [ ] **Step 2: Basarisiz testleri yaz**

`news/tests/test_refresh.py` dosyasinin **sonuna** ekle (dosyanin basinda `from news.api_v1 import refresh` ve `from news.tests.base import RefreshTestMixin, V1TestCase, test_redis_client` zaten var):

```python
class TriggerGorevParametreleriTest(RefreshTestMixin, V1TestCase):
    """Eski /api/*/fetch/ uclari trigger()'a gun/kaynak ve etiket gecirir (2026-09-30)."""

    def test_task_kwargs_skip_existing_ile_birlesir(self):
        refresh.trigger('cve', task_kwargs={'days': 3, 'selected_sources': ['NVD Guncel']},
                        trigger_label='admin')

        cagri = self.gorevler['cve'].call_args
        self.assertEqual(cagri.kwargs['kwargs'],
                         {'skip_existing': True, 'days': 3, 'selected_sources': ['NVD Guncel']})
        self.assertEqual(cagri.kwargs['headers'], {'fetchrun_trigger': 'admin'})

    def test_parametresiz_cagri_v1_davranisini_korur(self):
        refresh.trigger('cve')

        cagri = self.gorevler['cve'].call_args
        self.assertEqual(cagri.kwargs['kwargs'], {'skip_existing': True})
        self.assertEqual(cagri.kwargs['headers'], {'fetchrun_trigger': 'api'})

    def test_task_kwargs_soguma_ve_kilidi_atlatmaz(self):
        ilk = refresh.trigger('sre', task_kwargs={'days': 1})
        ikinci = refresh.trigger('sre', task_kwargs={'days': 1})

        self.assertEqual(ilk.status, 'started')
        self.assertEqual(ikinci.status, 'already_running')
        self.assertEqual(ikinci.job_id, ilk.job_id)
        self.assertEqual(self.gorevler['sre'].call_count, 1)
```

- [ ] **Step 3: Kirildigini gor**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh.TriggerGorevParametreleriTest 2>&1 | tail -5
```

Beklenen: `TypeError: trigger() got an unexpected keyword argument 'task_kwargs'` (ilk ve ucuncu test ERROR; ikincisi PASS).

- [ ] **Step 4: `trigger()`'i genislet**

`news/api_v1/refresh.py`'de fonksiyon imzasi ve docstring:

```python
def trigger(section: str, gate: Optional[RefreshGate] = None,
            cooldown: Optional[int] = None, lock_ttl: Optional[int] = None) -> TriggerResult:
    """Bir bolum icin manuel cekimi baslatir.
```

->

```python
def trigger(section: str, gate: Optional[RefreshGate] = None,
            cooldown: Optional[int] = None, lock_ttl: Optional[int] = None,
            task_kwargs: Optional[dict] = None, trigger_label: str = 'api') -> TriggerResult:
    """Bir bolum icin manuel cekimi baslatir.

    task_kwargs task'a `skip_existing=True` ile birlikte gecer (eski /api/*/fetch/
    uclarinin gun ve kaynak secimi). trigger_label FetchRun'daki tetikleyicidir.
    Kilit ve soguma bolum basinadir: parametreler ne olursa olsun paylasilir.
```

(Docstring'in geri kalan "Kontrol sirasi onemlidir..." paragrafi aynen kalir.)

Fonksiyon sonundaki kuyruga atma blogu:

```python
    try:
        # FetchRun'da bu isi 'api' olarak isaretlemek icin header eklenir
        section_tasks()[section].apply_async(kwargs={'skip_existing': True}, task_id=job_id,
                                              headers={'fetchrun_trigger': 'api'})
```

->

```python
    try:
        # FetchRun tetikleyiciyi bu header'dan okur (news/fetch_runs.py)
        section_tasks()[section].apply_async(kwargs={'skip_existing': True, **(task_kwargs or {})},
                                              task_id=job_id,
                                              headers={'fetchrun_trigger': trigger_label})
```

- [ ] **Step 5: Testler gecsin (yenisi + tum refresh/jobs/fetchrun testleri)**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh news.tests.test_jobs news.tests.test_fetchrun 2>&1 | grep -E "^Ran |^OK|^FAILED"
```

Beklenen: `OK`.

- [ ] **Step 6: Commit**

```bash
git add news/api_v1/refresh.py news/tests/test_refresh.py
git commit -m "feat: refresh.trigger gorev parametresi ve tetikleyici etiketi alsin

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Eski fetch uclari `_tetikle()` uzerinden (serializer + gate)

**Files:**
- Modify: `news/serializers.py` (alti `Fetch*RequestSerializer`)
- Modify: `news/views.py` (import blogu satir 1-33; alti `fetch_*` view'i: `fetch_news` ~67-100, `fetch_cves` ~202-232, `fetch_k8s` ~339-373, `fetch_sre` ~475-509, `fetch_devtools` ~604-638, `fetch_ai_news` ~738-771)
- Create: `news/tests/test_eski_fetch_kapisi.py`
- Modify: `news/tests/test_fetchrun.py` (`test_views_admin_header_i_gecer` silinir)

**Interfaces:**
- Consumes: Task 5'in `refresh.trigger(section, task_kwargs=..., trigger_label=...) -> TriggerResult`
- Produces: `news.views._tetikle(request, bolum: str) -> Response`; `news.views._FETCH_BOLUMLERI: dict[str, tuple[type, tuple[str, ...], str]]`. HTTP sozlesmesi spec bolum 2 tablo 4: 200 (`started`/`already_running`, `job_id`), 429 + `Retry-After` (`retry_after`), 400, 500. Task 7 frontend'i `response.data.message`'i gosterir.

- [ ] **Step 1: Basarisiz testleri yaz**

`news/tests/test_eski_fetch_kapisi.py`:

```python
"""Eski POST /api/*/fetch/ uclari: v1 bolum kilidi + soguma kapisi (2026-09-30).

Uclar anonim kullanima acik kalir (kullanici karari) ama kaynak sitelere ve
ceviri kotasina giden yuk v1 ile ayni Redis kapisindan gecer. Gercek task
kuyruga atilmaz: RefreshTestMixin alti task'in apply_async'ini mock'lar.
"""
from django.core.cache import cache

from news.api_v1 import refresh
from news.tests.base import RefreshTestMixin, V1TestCase

# URL -> (refresh bolumu, frontend cache anahtari)
UCLAR = {
    '/api/fetch/': ('news', 'cybersecurity_news'),
    '/api/cve/fetch/': ('cve', 'cve_entries'),
    '/api/k8s/fetch/': ('kubernetes', 'k8s_entries'),
    '/api/sre/fetch/': ('sre', 'sre_entries'),
    '/api/devtools/fetch/': ('devtools', 'devtools_entries'),
    '/api/ai/fetch/': ('ai', 'ai_entries'),
}


class EskiFetchKapisiTest(RefreshTestMixin, V1TestCase):

    def _gonder(self, url='/api/cve/fetch/', govde=None):
        return self.client.post(url, govde if govde is not None else {'days': 7},
                                content_type='application/json')

    def test_baslatir_ve_gun_kaynak_etiketi_gecer(self):
        yanit = self._gonder(govde={'days': 3, 'sources': ['NVD Guncel']})

        self.assertEqual(yanit.status_code, 200)
        self.assertTrue(yanit.json()['success'])
        self.assertTrue(yanit.json()['job_id'])
        cagri = self.gorevler['cve'].call_args
        self.assertEqual(cagri.kwargs['kwargs'],
                         {'skip_existing': True, 'days': 3, 'selected_sources': ['NVD Guncel']})
        self.assertEqual(cagri.kwargs['headers'], {'fetchrun_trigger': 'admin'})

    def test_gun_verilmezse_varsayilan_bugunku_davranis(self):
        """fetch_cves eskiden request.data.get('days', 7) kullaniyordu."""
        self._gonder(govde={})
        self.assertEqual(self.gorevler['cve'].call_args.kwargs['kwargs'],
                         {'skip_existing': True, 'days': 7, 'selected_sources': None})

    def test_calisan_is_varken_ikinci_istek_kuyruga_atmaz(self):
        ilk = self._gonder().json()
        ikinci = self._gonder()

        self.assertEqual(ikinci.status_code, 200)
        self.assertTrue(ikinci.json()['success'])
        self.assertEqual(ikinci.json()['job_id'], ilk['job_id'])
        self.assertIn('zaten', ikinci.json()['message'])
        self.assertEqual(self.gorevler['cve'].call_count, 1)

    def test_sogumada_429_ve_retry_after(self):
        self.gate.start_cooldown('cve', 600)

        yanit = self._gonder()

        self.assertEqual(yanit.status_code, 429)
        self.assertEqual(yanit['Retry-After'], '600')
        self.assertFalse(yanit.json()['success'])
        self.assertEqual(yanit.json()['retry_after'], 600)
        self.assertIn('10 dk', yanit.json()['message'])
        self.assertFalse(self.gorevler['cve'].called)

    def test_soguma_v1_ile_paylasilir(self):
        """v1 tuketicisi tetikleyip is bittiyse arayuz de sogumaya takilir."""
        sonuc = refresh.trigger('cve')
        self.gate.release('cve', sonuc.job_id)  # is bitti: kilit birakildi, soguma suruyor

        yanit = self._gonder()

        self.assertEqual(yanit.status_code, 429)
        self.assertEqual(self.gorevler['cve'].call_count, 1)

    def test_gecersiz_gun_400(self):
        for govde in ({'days': 0}, {'days': 1000}, {'days': 'abc'}):
            with self.subTest(govde=govde):
                yanit = self._gonder(govde=govde)
                self.assertEqual(yanit.status_code, 400)
                self.assertFalse(yanit.json()['success'])
        self.assertFalse(self.gorevler['cve'].called)

    def test_asiri_kaynak_listesi_400(self):
        yanit = self._gonder(govde={'days': 7, 'sources': [f'k{i}' for i in range(21)]})
        self.assertEqual(yanit.status_code, 400)
        self.assertFalse(self.gorevler['cve'].called)

    def test_cache_yalniz_baslatilinca_silinir(self):
        cache.set('cve_entries', ['eski'])
        self.gate.start_cooldown('cve', 600)
        self._gonder()
        self.assertEqual(cache.get('cve_entries'), ['eski'], 'sogumada cache silinmemeli')

        self.redis.delete(f'{self.gate.prefix}:cooldown:cve')  # soguma bitti
        self._gonder()
        self.assertIsNone(cache.get('cve_entries'), 'baslatilinca cache silinmeli')

    def test_alti_uc_dogru_bolume_gider(self):
        for url, (bolum, cache_anahtari) in UCLAR.items():
            with self.subTest(url=url):
                cache.set(cache_anahtari, ['eski'])
                yanit = self._gonder(url=url, govde={'days': 7})
                self.assertEqual(yanit.status_code, 200)
                self.assertEqual(self.gorevler[bolum].call_count, 1)
                self.assertIsNone(cache.get(cache_anahtari))

    def test_anonim_istek_kabul_edilir(self):
        """Kullanici karari: uclar anonim kullanima acik kalir."""
        self.client.logout()
        self.assertEqual(self._gonder().status_code, 200)
```

- [ ] **Step 2: Kirildigini gor**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_eski_fetch_kapisi 2>&1 | grep -E "^Ran |^OK|^FAILED|Error" | head
```

Beklenen: `FAILED` — `job_id` KeyError, 429 yerine 200, 400 yerine 200/500 vb.

- [ ] **Step 3: Serializer'lar**

`news/serializers.py`'de `class FetchNewsRequestSerializer` satirinin **hemen ustune** ekle:

```python
def _kaynak_listesi():
    """Eski fetch uclarinin kaynak secimi. Bilinmeyen adlari scraper'lar zaten eler;
    burada yalnizca boyut sinirlanir (anonim istek, 2026-09-30)."""
    return serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        allow_empty=True,
        max_length=20,
    )
```

Alti `Fetch*RequestSerializer`'in (`FetchNewsRequestSerializer`, `FetchCVERequestSerializer`, `FetchK8sRequestSerializer`, `FetchSRERequestSerializer`, `FetchDevToolsRequestSerializer`, `FetchAINewsRequestSerializer`) her birindeki:

```python
    sources = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
```

blogunu su satirla degistir:

```python
    sources = _kaynak_listesi()
```

`FetchCVERequestSerializer`'da:

```python
    days = serializers.IntegerField(default=30, min_value=1, max_value=90)
```

->

```python
    # Varsayilan 7: fetch_cves'in eski davranisi ve fetch_cve_task varsayilani ile ayni
    days = serializers.IntegerField(default=7, min_value=1, max_value=90)
```

- [ ] **Step 4: `views.py` — importlar ve yardimci**

Import blogunda su satiri **sil** (fetch_*_task'lar artik views'ta kullanilmayacak):

```python
from .tasks import fetch_news_task, fetch_cve_task, fetch_k8s_task, fetch_sre_task, fetch_devtools_task, fetch_ai_news_task
```

Silmeden once dogrula ki baska yerde kullanilmiyor:

```bash
grep -n "fetch_news_task\|fetch_cve_task\|fetch_k8s_task\|fetch_sre_task\|fetch_devtools_task\|fetch_ai_news_task" news/views.py
```

Beklenen: yalniz import satiri ve alti `.apply_async(` satiri (bunlar Step 5'te gidiyor).

`from .serializers import (` blogunun **ustune** ekle:

```python
from .api_v1 import refresh
```

`GENEL_SUNUCU_HATASI = ...` satirinin **altina** ekle:

```python


# Eski /api/*/fetch/ uclari: bolum -> (istek serializer'i, silinecek frontend cache
# anahtarlari, mesajdaki ad). Bolum adlari news/api_v1/refresh.py::SECTIONS ile ayni.
_FETCH_BOLUMLERI = {
    'news': (FetchNewsRequestSerializer, ('cybersecurity_news', 'last_update'), 'Haber'),
    'cve': (FetchCVERequestSerializer, ('cve_entries', 'cve_last_update'), 'CVE'),
    'kubernetes': (FetchK8sRequestSerializer, ('k8s_entries', 'k8s_last_update'), 'K8s haber'),
    'sre': (FetchSRERequestSerializer, ('sre_entries', 'sre_last_update'), 'SRE haber'),
    'devtools': (FetchDevToolsRequestSerializer, ('devtools_entries', 'devtools_last_update'), 'DevTools'),
    'ai': (FetchAINewsRequestSerializer, ('ai_entries', 'ai_last_update'), 'AI haber'),
}


def _tetikle(request, bolum):
    """Eski fetch uclarinin ortak govdesi: dogrula, v1 kapisindan gecir, yanitla.

    Kilit ve 15 dk soguma v1 (/api/v1/<bolum>/refresh/) ile paylasilir; kaynak
    sitelere giden yuk tetikleyenden bagimsiz sinirlanir (ADR-0003 karar 5).
    """
    serializer_sinifi, cache_anahtarlari, ad = _FETCH_BOLUMLERI[bolum]
    serializer = serializer_sinifi(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'message': 'Gecersiz istek'},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        sonuc = refresh.trigger(
            bolum,
            task_kwargs={'days': serializer.validated_data['days'],
                         'selected_sources': serializer.validated_data.get('sources')},
            # FetchRun.TETIKLEYICILER'de 'admin' "Arayuz" olarak gosterilir
            trigger_label='admin',
        )
    except Exception:
        logger.exception('%s cekimi tetiklenemedi', bolum)
        return Response({'success': False, 'message': GENEL_SUNUCU_HATASI, 'count': 0, 'data': []},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if sonuc.status == 'cooldown':
        dakika = -(-sonuc.retry_after // 60)  # yukari yuvarla
        yanit = Response({
            'success': False,
            'message': f'{ad} cekimi az once yapildi; {dakika} dk sonra tekrar deneyin.',
            'retry_after': sonuc.retry_after,
            'count': 0,
            'data': [],
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        yanit['Retry-After'] = str(sonuc.retry_after)
        return yanit

    if sonuc.status == 'started':
        # Yalniz yeni is basladiysa: calisan is ya da soguma varken silmek listeyi bosaltirdi
        cache.delete_many(cache_anahtarlari)
        mesaj = f'{ad} cekimi baslatildi. Otomatik yansiyacak.'
    else:
        mesaj = f'{ad} cekimi zaten suruyor. Kayitlar otomatik yansiyacak.'
    return Response({'success': True, 'message': mesaj, 'job_id': sonuc.job_id,
                     'count': 0, 'data': []})
```

Not: `_FETCH_BOLUMLERI` serializer siniflarini kullandigi icin `from .serializers import (...)` blogunun **altinda** tanimli olmali; `GENEL_SUNUCU_HATASI` zaten o blogun altinda — sorun yok.

- [ ] **Step 5: `views.py` — alti view govdesini degistir**

Her birinin decorator'lari (`@api_view(['POST'])`, `@permission_classes([AllowAny])`) ve adi aynen kalir; yalniz docstring ve govde degisir. Alti fonksiyonun tamami (decorator'larin altindaki `def` satirindan bir sonraki `@api_view`'a kadar) su hale gelir:

```python
def fetch_news(request):
    """Siber guvenlik haberi cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'news')
```

```python
def fetch_cves(request):
    """CVE cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'cve')
```

```python
def fetch_k8s(request):
    """Kubernetes haber cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'kubernetes')
```

```python
def fetch_sre(request):
    """SRE haber cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'sre')
```

```python
def fetch_devtools(request):
    """DevTools cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'devtools')
```

```python
def fetch_ai_news(request):
    """AI haber cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'ai')
```

Dikkat: `fetch_ai_news`'tan sonra gelen `@api_view` ile arasinda **iki bos satir** olmali (dosyada su an tek bos satir var; PEP 8'e getir).

Dogrula:

```bash
grep -c "apply_async" news/views.py
grep -n "request.data.get('days'" news/views.py
```

Beklenen: `0` ve cikti yok.

- [ ] **Step 6: Eski kablolama testini kaldir**

`news/tests/test_fetchrun.py`'deki `def test_views_admin_header_i_gecer(self):` metodunu (docstring'i ve govdesiyle, bir sonraki `def`/sinif sonuna kadar) sil. Kapsami `test_eski_fetch_kapisi.py::test_baslatir_ve_gun_kaynak_etiketi_gecer` ve `test_gun_verilmezse_varsayilan_bugunku_davranis` devraldi (views artik `fetch_cve_task`'i import etmedigi icin eski test `AttributeError` verirdi).

- [ ] **Step 7: Testler**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_eski_fetch_kapisi 2>&1 | grep -E "^Ran |^OK|^FAILED"
docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^Ran |^OK|^FAILED"
```

Beklenen: ilki `Ran 10 tests` `OK`; ikincisi `OK` (Task 3'ten sonra 335; Task 5 +3, Task 6 +10 -1 = **347**).

- [ ] **Step 8: Commit**

```bash
git add news/serializers.py news/views.py news/tests/test_eski_fetch_kapisi.py news/tests/test_fetchrun.py
git commit -m "fix: eski /api/*/fetch/ uclarini v1 bolum kilidi ve sogumasindan gecir

Alti kopya view tek _tetikle() yardimcisina toplandi; days/sources alti
bolumde de serializer ile dogrulaniyor. Soguma 429 + Retry-After doner,
cache yalniz is baslatilinca silinir.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Frontend — sunucu mesajini goster

**Files:**
- Modify: `frontend/src/services/api.js` (sona ekleme)
- Modify: `frontend/src/components/NewsComponent.jsx:13, 101`
- Modify: `frontend/src/components/CVEComponent.jsx:14, 109`
- Modify: `frontend/src/components/KubernetesComponent.jsx:14, 113`
- Modify: `frontend/src/components/SREComponent.jsx:14, 106`
- Modify: `frontend/src/components/DevToolsComponent.jsx:15, 112`
- Modify: `frontend/src/components/AINewsComponent.jsx:13, 107`

**Interfaces:**
- Consumes: Task 6'nin yanitlari — hata durumlarinda `err.response.data.message` (400/429/500) Turkce ASCII metin
- Produces: `istekHataMesaji(err, varsayilan: string) -> string` (`frontend/src/services/api.js`, named export)

Frontend'de test altyapisi yok (vitest/jest kurulu degil); dogrulama build + tarayicida yapilir (Task 8). Test altyapisi kurmak kapsam disi.

- [ ] **Step 1: Yardimci**

`frontend/src/services/api.js` dosyasinin **sonuna** (en alttaki `export default` varsa onun **ustune**) ekle:

```js
// Sunucunun dondurdugu mesaji tercih eder (ornegin soguma: 429 "... N dk sonra tekrar deneyin").
// Mesaj yoksa (ag hatasi vb.) varsayilan metin + axios hatasi gosterilir.
export const istekHataMesaji = (err, varsayilan) =>
  err.response?.data?.message || `${varsayilan}: ${err.message}`
```

Kontrol: `grep -n "export default" frontend/src/services/api.js` — varsa yardimci onun ustunde olmali.

- [ ] **Step 2: Alti bilesen**

Her bilesende iki degisiklik:

**(a)** `../services/api` import satirina `istekHataMesaji` ekle:

| Dosya | Eski | Yeni |
|---|---|---|
| `NewsComponent.jsx` | `import { newsApi } from '../services/api'` | `import { newsApi, istekHataMesaji } from '../services/api'` |
| `CVEComponent.jsx` | `import { cveApi } from '../services/api'` | `import { cveApi, istekHataMesaji } from '../services/api'` |
| `KubernetesComponent.jsx` | `import { k8sApi } from '../services/api'` | `import { k8sApi, istekHataMesaji } from '../services/api'` |
| `SREComponent.jsx` | `import { sreApi } from '../services/api'` | `import { sreApi, istekHataMesaji } from '../services/api'` |
| `DevToolsComponent.jsx` | `import { devtoolsApi } from '../services/api'` | `import { devtoolsApi, istekHataMesaji } from '../services/api'` |
| `AINewsComponent.jsx` | `import { aiApi } from '../services/api'` | `import { aiApi, istekHataMesaji } from '../services/api'` |

**(b)** Fetch `catch` blogundaki `setError(...)` satiri:

| Dosya | Eski | Yeni |
|---|---|---|
| `NewsComponent.jsx` | `setError('Siber güvenlik haberleri getirilirken hata oluştu: ' + err.message)` | `setError(istekHataMesaji(err, 'Siber güvenlik haberleri getirilirken hata oluştu'))` |
| `CVEComponent.jsx` | `setError('CVE verileri getirilirken hata oluştu: ' + err.message)` | `setError(istekHataMesaji(err, 'CVE verileri getirilirken hata oluştu'))` |
| `KubernetesComponent.jsx` | `setError('Kubernetes haberleri getirilirken hata oluştu: ' + err.message)` | `setError(istekHataMesaji(err, 'Kubernetes haberleri getirilirken hata oluştu'))` |
| `SREComponent.jsx` | `setError('SRE haberleri getirilirken hata oluştu: ' + err.message)` | `setError(istekHataMesaji(err, 'SRE haberleri getirilirken hata oluştu'))` |
| `DevToolsComponent.jsx` | `setError('DevTools güncellemeleri getirilirken hata oluştu: ' + err.message)` | `setError(istekHataMesaji(err, 'DevTools güncellemeleri getirilirken hata oluştu'))` |
| `AINewsComponent.jsx` | `setError('AI haberleri getirilirken hata oluştu: ' + err.message)` | `setError(istekHataMesaji(err, 'AI haberleri getirilirken hata oluştu'))` |

Dogrula:

```bash
grep -c "istekHataMesaji" frontend/src/components/*.jsx
grep -n "getirilirken hata oluştu: ' + err.message" frontend/src/components/*.jsx
```

Beklenen: alti bilesende de `2`; ikinci komut cikti vermez.

- [ ] **Step 3: Build**

```bash
docker run --rm -v "$(pwd -W 2>/dev/null || pwd)/frontend:/app" -w /app node:22-alpine sh -c "npm ci --no-audit --no-fund >/dev/null && npm run build" 2>&1 | tail -5
```

Beklenen: `✓ built in ...`, hata yok. (Bu komut `frontend/dist` ve `node_modules`'u yeniden uretir; ikisi de gitignore'da.)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api.js frontend/src/components/*.jsx
git commit -m "feat: fetch hatalarinda sunucunun mesajini goster (soguma 429)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: ADR notu, tam kapi, canli dogrulama ve merge

**Files:**
- Modify: `docs/ADR-0003-Entegrasyon-API-v1.md` (`### Uygulama sirasinda duzeltilen varsayimlar` basligindan hemen once)
- Modify: `docs/superpowers/specs/2026-09-30-hizli-isler-design.md` (Durum satiri)

**Interfaces:**
- Consumes: Task 5-7
- Produces: yok

- [ ] **Step 1: ADR-0003 notu**

`docs/ADR-0003-Entegrasyon-API-v1.md`'de `### Uygulama sirasinda duzeltilen varsayimlar` satirinin **hemen ustune** ekle:

```markdown
### Degisiklik (2026-09-30) — eski fetch uclari v1 kapisindan gecer

Karar 1'in "`news/views.py` dokunulmaz" maddesinden ikinci bilincli sapma
(birincisi [ADR-0006](ADR-0006-FetchRun-Gorunurlugu-ve-Status-Ucu.md) karar 5).
Eski `POST /api/*/fetch/` uclari anonim kullanima acik kaldi ama artik
`refresh.trigger()` uzerinden gecer: karar 5'teki bolum kilidi ve 15 dk soguma
**v1 ile paylasilir**, yani arayuz butonu ve v1 tuketicisi ayni sinira tabidir.
URL'ler ve basari yaniti zarfi degismedi; yeni olanlar `429 + Retry-After`,
`job_id` ve `retry_after` alanlaridir. `days`/`sources` alti bolumde de
serializer ile dogrulanir. Tasarim:
[`superpowers/specs/2026-09-30-hizli-isler-design.md`](superpowers/specs/2026-09-30-hizli-isler-design.md).

```

- [ ] **Step 2: Spec durumu**

`docs/superpowers/specs/2026-09-30-hizli-isler-design.md`'de:

`- **Durum:** Onaylandi (2026-09-30). Plan: ...`

->

`- **Durum:** UYGULANDI (<bugunun tarihi>). Plan: [`../plans/2026-09-30-hizli-isler.md`](../plans/2026-09-30-hizli-isler.md)`

(`<bugunun tarihi>` yerine `date +%F` ciktisini yaz.) Task 1 veya 2 merge edilemediyse ayni satira ekle: `PR #4x merge edilmedi: <neden>.`

- [ ] **Step 3: Commit**

```bash
git add docs/ADR-0003-Entegrasyon-API-v1.md docs/superpowers/specs/2026-09-30-hizli-isler-design.md
git commit -m "docs: eski fetch uclarinin v1 kapisina baglanmasini ADR-0003'e isle

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 4: Tam kapi**

Yukaridaki "Tam kapi"yi eksiksiz calistir. Beklenen test sayisi **347**.

- [ ] **Step 5: Canli uc davranisi (gercek, kisa bir cekim)**

SRE bolumu secilir (kisa surer; 2026-09-21'de 150 sn). Gercek bir cekim baslatir; Beat'in de 6 saatte bir yaptigi is, zararsiz.

```bash
curl -s -X POST http://localhost:8000/api/sre/fetch/ -H "Content-Type: application/json" -d '{"days": 7}'; echo
curl -s -X POST http://localhost:8000/api/sre/fetch/ -H "Content-Type: application/json" -d '{"days": 7}'; echo
curl -s -o /dev/null -w "gecersiz:%{http_code}\n" -X POST http://localhost:8000/api/sre/fetch/ -H "Content-Type: application/json" -d '{"days": 0}'
```

Beklenen: 1. `"success":true` + `"cekimi baslatildi"` + `job_id`; 2. `"success":true` + `"zaten suruyor"` + ayni `job_id`; 3. `gecersiz:400`.

Isin bitmesini bekle (en fazla ~5 dk), sonra:

```bash
docker compose exec -T teknoloji-api python manage.py shell -c "
from news.models import FetchRun
r = FetchRun.objects.filter(section='sre').order_by('-started_at').first()
print(r.status, r.trigger, r.fetched_count, r.saved_count)
"
curl -s -i -X POST http://localhost:8000/api/sre/fetch/ -H "Content-Type: application/json" -d '{"days": 7}' | grep -iE "^HTTP|^Retry-After|message"
```

Beklenen: `success admin <n> <m>` (status `running` ise biraz daha bekle); ardindan `HTTP/1.1 429`, `Retry-After: <sayi>` ve `"... dk sonra tekrar deneyin."`.

- [ ] **Step 6: Tarayici kontrolu — KOORDINATOR (ana oturum) yapar**

Uygulayici alt ajan bu adimi atlar ve raporunda "Step 6 koordinatore birakildi" yazar. Koordinator: `http://localhost:3000/sre` sayfasinda "Çek" butonuna basar, soguma mesajinin ("SRE haber cekimi az once yapildi; N dk sonra tekrar deneyin.") hata alaninda gorundugunu ve konsolda beklenmeyen hata olmadigini dogrular; sonra `/cve`'de bir kez basarak toast'in ("CVE çekimi başladı!") geldigini gorur.

- [ ] **Step 7: Merge ve push**

```bash
git checkout main
git merge --no-ff fix/eski-fetch-kapisi -m "Merge fix/eski-fetch-kapisi: eski fetch uclari v1 bolum kilidi ve sogumasindan gecer"
git push origin main
git branch -d fix/eski-fetch-kapisi
```

~5 dk sonra:

```bash
gh run list --branch main --limit 10 --json name,conclusion,status --jq '.[] | "\(.name) \(.status) \(.conclusion)"'
```

Beklenen: tum koşular `success`. `DAST (ZAP baseline)` 429 donen uclari yeni bulgu olarak isaretlerse (FAIL-NEW) rapor et; merge geri alinmaz, koordinator triaj eder.

---

## Self-Review Notlari (plan yazari)

- Spec bolum 2 madde 1 -> Task 5; madde 2-5 -> Task 6; madde 6 -> Task 7; madde 7 (etiket `admin`) -> Task 6 `_tetikle`; ADR notu -> Task 8.
- Spec bolum 3 madde 1-2 -> Task 3; madde 3 (compose) ve 4'un yerel `.env` kismi -> Task 3 Step 1b (settings'ten once: gunicorn `--preload` yok, yeniden dogan worker placeholder'la cokerdi); madde 4 (`.env.example`) ve 5-9 -> Task 4; Faz B notu -> Task 4 Step 8 (README ALLOWED_HOSTS satiri).
- Spec bolum 4 -> Task 1-2. Bolum 5 kapilari -> Task 4 Step 11, Task 8 Step 4-6.
- Test sayisi zinciri: 326 -> Task 3 +9 = 335 -> Task 5 +3 = 338 -> Task 6 +10 -1 = 347.
