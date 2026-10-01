# Faz B1 — SQLite'tan PostgreSQL'e Gecis — Uygulama Plani

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Canli yerel compose yiginini SQLite'tan PostgreSQL 16'ya, v1 delta sozlesmesini bozmadan ve kayipsiz tasimak.

**Architecture:** `settings.py` veritabanini saf bir fonksiyondan (`veritabani_ayari`) alir: `DB_HOST` doluysa PostgreSQL, bossa yalniz `DEBUG=True` iken SQLite. Veri, mikrosaniyeyi koruyan bir JSON dump komutu (`veri_tasi_dump`) ve standart `loaddata` ile tasinir; dogrulama serilestiriciden bagimsiz bir ozet komutuyla (`veri_ozeti`) yapilir. Kod ayri bir git worktree'de yazilir, testler tek kullanimlik bir PostgreSQL'de kosar; canli kopya yalniz gecis aninda degisir.

**Tech Stack:** Django 5.2.17, DRF 3.18.1, Celery 5.6.3, psycopg2-binary 2.9.13, PostgreSQL 16.15, Redis 7.4, Docker Compose, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-01-faz-b-postgres-helm-design.md` (bolum 2, 3, 4, 5, 6, 11, 12). Planla celiskide asagidaki "Spec'e Gore Netlestirmeler" gecerlidir.

## Global Constraints

- **Yalniz yerel.** Registry, uzak kume, git tag, GitHub release yok. `git push` yalniz kullanici acikca istediginde. B1 hicbir `kubectl`/`helm` komutu calistirmaz.
- **Canli yigina dokunma (Task 0-7):** `teknoloji-*` konteynerleri durdurulmaz, yeniden baslatilmaz, `docker compose up/down/restart` calistirilmaz. Canli calisma kopyasinda (`C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news`) dal degistirilmez, dosya duzenlenmez. Tek istisna Task 7 Step 1'deki salt okunur SQLite yedegi.
- **Tum kod isi worktree'de:** `C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news-fazb1`, dal `feat/faz-b1-postgres`.
- **Testler yalniz `scripts/pg_test.sh` ile** (kendi PostgreSQL + Redis konteynerleri; canli Redis'e de dokunmaz). Beklenen taban: `Ran 347 tests ... OK`.
- **Imajlar (digest'e sabit):**
  - `postgres:16.15-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea`
  - `redis:7.4.10-alpine@sha256:e7723ff73d963f5cc6d9c4643ea3d989527a402a319239054e9472a7fb9219a2`
- **Hassas dosyalar:** `.fazb/` altindaki dump'lar ve SQLite kopyalari parola hash'i ve API token'i icerir; commit edilmez, gorev bitince silinir. Parolalar (`POSTGRES_PASSWORD`, `SECRET_KEY`) hicbir komut ciktisina basilmaz.
- **Depo kalibi:** kod, yorum ve commit mesajlari ASCII Turkce; her commit mesaji oturumun verdigi `Co-Authored-By` satiriyla biter; dallar `--no-ff` ile merge edilir.
- **Review politikasi:** varsayilan subagent review yok (kullanici token butcesi karari). Tek istisna: Task 4 bittikten sonra Task 3-4 diff'i icin tek bir sonnet review (veri sadakati riskli). Diger gorevlerde kapi = testler + bu plandaki dogrulama komutlari.
- **Windows/Git Bash:** komutlar Bash aracinda kosar. `docker run -v` icin yol `$(pwd -W)` ile verilir ve `MSYS_NO_PATHCONV=1` kullanilir (betik bunu kendisi yapar).

## Spec'e Gore Netlestirmeler

1. **Merge zamani.** Spec 6 "on kosul: B1 `main`'e merge edilmis" der. Compose bind mount (`./:/app`) ile calistigi icin `main`'e merge etmek canli koddaki `settings.py`'yi degistirir ve ilk konteyner yeniden baslatmasinda (`DB_HOST` yok, `DEBUG=False`) yigin duser. Bu yuzden **merge, gecisin Adim 3'unde, servisler durduktan sonra** yapilir (Task 8 Step 4).
2. **Dogal birincil anahtar kullanilmaz.** Spec 5.3 `use_natural_primary_keys=True` der. Bu, `auth.User`'i `pk`'siz yazar ve bos veritabaninda yeni `pk` verdirir. `pk`'lerin aynen korunmasi icin yalniz `use_natural_foreign_keys=True` kullanilir (ContentType/Permission referanslari icin gereken budur). Ozet karsilastirmasi `pk`'leri de kapsar.
3. **`veri_ozeti --json` yazilmaz** (YAGNI): karsilastirma metin ciktisinin `diff`'idir.
4. **Prova `-p fazb-prova` ile yapilamaz:** `docker-compose.yml`'de `container_name` ve host portlari sabit oldugu icin ikinci bir compose projesi canli konteynerlerle cakisir. Prova (Task 7) `scripts/pg_test.sh`'in kendi konteynerleriyle yapilir ve geri donus yonunu de (PostgreSQL -> SQLite) prova eder.
5. **Yeni yardimci `scripts/pg_test.sh`** (spec'te yok): tek kullanimlik PostgreSQL + Redis'e karsi `manage.py` calistirir; B2'de de kullanilir.

## Dosya Haritasi

| Dosya | Sorumluluk | Gorev |
|---|---|---|
| `scripts/pg_test.sh` (yeni) | Gecici PostgreSQL/Redis ile `manage.py` | 0 |
| `cybernews/ayar_dogrulama.py` | `veritabani_ayari()` | 1 |
| `cybernews/settings.py` | `DATABASES` -> `veritabani_ayari` | 1 |
| `news/tests/test_ayar_dogrulama.py` | DB secimi testleri | 1 |
| `news/models.py`, `news/migrations/0013_link_max_length_500.py` (yeni) | Uc `link` 500 | 2 |
| `news/tests/test_modeller.py` | Link uzunlugu testleri | 2 |
| `news/veri_tasima.py` (yeni) | Model kumesi, kodlayici, ozet, yazim | 3, 4 |
| `news/management/commands/veri_ozeti.py` (yeni) | Ozet komutu | 3 |
| `news/management/commands/veri_tasi_dump.py` (yeni) | Dump komutu | 4 |
| `news/tests/test_veri_tasima.py` (yeni) | Kodlayici, ozet, gidis-donus testleri | 3, 4 |
| `docker-compose.yml`, `.env.example`, `.gitignore`, `.dockerignore` | PostgreSQL servisi, env, yok sayilanlar | 5 |
| `.github/workflows/ci.yml` | Backend testleri PostgreSQL'de | 5 |
| `README.md` | Compose, env tablosu, veri tasima | 6 |
| `docs/ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md` (yeni), `docs/ADR-0005...`, `docs/ADR-0006...` | Karar kaydi | 9, 10 |

---

### Task 0: Worktree ve test yardimcisi

**Files:**
- Create: `scripts/pg_test.sh`

**Interfaces:**
- Consumes: canli imaj `teknoloji-haberleri-api:latest` (bagimliliklar yuklu; B1 `requirements.txt`'i degistirmez)
- Produces: `scripts/pg_test.sh [--sqlite] <manage.py argumanlari...>` ve `scripts/pg_test.sh temizle`. Konteynerler: ag `fazb-test`, `fazb-test-pg` (kullanici/db `cybernews`), `fazb-test-redis`. `--sqlite`: `DEBUG=True`, `DB_HOST` bos -> depo kokundeki `db.sqlite3`. Depo koku konteynerde `/app`'tir.

- [ ] **Step 1: Canli kopyanin temiz oldugunu dogrula ve worktree ac**

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news
git status --short
git log --oneline -1
git worktree add ../cybersecurity_news-fazb1 -b feat/faz-b1-postgres main
cd ../cybersecurity_news-fazb1 && git branch --show-current
```

Expected: `git status --short` bos; son satir `feat/faz-b1-postgres`. Bundan sonraki tum gorevler (Task 8 haric) bu dizinde calisir.

- [ ] **Step 2: `scripts/pg_test.sh` yaz**

```bash
#!/usr/bin/env bash
# Tek kullanimlik PostgreSQL + Redis'e karsi manage.py calistirir (Faz B1).
# Canli compose yiginina (teknoloji-*) ve canli Redis'e dokunmaz.
#
#   scripts/pg_test.sh test news --noinput    # testler PostgreSQL'de
#   scripts/pg_test.sh --sqlite <komut>       # DEBUG=True, DB_HOST bos -> depo kokundeki db.sqlite3
#   scripts/pg_test.sh temizle                # konteynerleri ve agi siler
#
# Depo koku konteynerde /app'tir; komut bu betigin bulundugu deponun kodunu kullanir.
set -euo pipefail

AG=fazb-test
PG=fazb-test-pg
REDIS=fazb-test-redis
PG_IMAJ='postgres:16.15-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea'
REDIS_IMAJ='redis:7.4.10-alpine@sha256:e7723ff73d963f5cc6d9c4643ea3d989527a402a319239054e9472a7fb9219a2'
UYGULAMA_IMAJ="${UYGULAMA_IMAJ:-teknoloji-haberleri-api:latest}"
# Yalniz bu gecici konteyner icin; hicbir gercek veritabaninda kullanilmaz.
PAROLA=yerel-gecici-test

KOK="$(cd "$(dirname "$0")/.." && (pwd -W 2>/dev/null || pwd))"

if [ "${1:-}" = "temizle" ]; then
  docker rm -f "$PG" "$REDIS" >/dev/null 2>&1 || true
  docker network rm "$AG" >/dev/null 2>&1 || true
  echo "temizlendi"
  exit 0
fi

docker network inspect "$AG" >/dev/null 2>&1 || docker network create "$AG" >/dev/null
if ! docker inspect "$PG" >/dev/null 2>&1; then
  docker run -d --name "$PG" --network "$AG" \
    -e POSTGRES_USER=cybernews -e POSTGRES_PASSWORD="$PAROLA" -e POSTGRES_DB=cybernews \
    "$PG_IMAJ" >/dev/null
fi
if ! docker inspect "$REDIS" >/dev/null 2>&1; then
  docker run -d --name "$REDIS" --network "$AG" "$REDIS_IMAJ" >/dev/null
fi
# -h 127.0.0.1: ilk acilistaki gecici sunucu yalniz unix soketini dinler; TCP hazir olunca gecer.
hazir=0
for _ in $(seq 1 60); do
  if docker exec "$PG" pg_isready -h 127.0.0.1 -U cybernews -d cybernews >/dev/null 2>&1; then
    hazir=1; break
  fi
  sleep 1
done
[ "$hazir" = 1 ] || { echo "PostgreSQL 60 sn icinde hazir olmadi" >&2; exit 1; }

ORTAM=(-e "REDIS_URL=redis://$REDIS:6379/0" -e "CELERY_BROKER_URL=redis://$REDIS:6379/1"
       -e "SECRET_KEY=$(openssl rand -hex 32)")
if [ "${1:-}" = "--sqlite" ]; then
  shift
  ORTAM+=(-e DEBUG=True -e DB_HOST=)
else
  ORTAM+=(-e DEBUG=False -e "DB_HOST=$PG" -e DB_NAME=cybernews -e DB_USER=cybernews
          -e "DB_PASSWORD=$PAROLA" -e DB_PORT=5432)
fi

MSYS_NO_PATHCONV=1 docker run --rm -i --network "$AG" -v "$KOK:/app" "${ORTAM[@]}" \
  --entrypoint python "$UYGULAMA_IMAJ" manage.py "$@"
```

- [ ] **Step 3: Taban test kosusu (bugunku kodla, PostgreSQL'de)**

Bugunku `settings.py` PostgreSQL'e `DATABASE_URL` doluysa gecer. Bu kosu yalniz tabani olcer; o yuzden ortami gecici olarak elle verir:

```bash
chmod +x scripts/pg_test.sh
scripts/pg_test.sh check >/dev/null 2>&1 || true   # konteynerleri baslatir (bugunku settings SQLite'a duser, sonuc onemsiz)
MSYS_NO_PATHCONV=1 docker run --rm --network fazb-test -v "$(pwd -W):/app" \
  -e DEBUG=False -e SECRET_KEY=$(openssl rand -hex 32) -e DATABASE_URL=postgresql \
  -e DB_HOST=fazb-test-pg -e DB_USER=cybernews -e DB_PASSWORD=yerel-gecici-test -e DB_NAME=cybernews \
  -e REDIS_URL=redis://fazb-test-redis:6379/0 -e CELERY_BROKER_URL=redis://fazb-test-redis:6379/1 \
  --entrypoint python teknoloji-haberleri-api:latest manage.py test news --noinput 2>&1 | grep -E "^Ran |^OK|^FAILED"
```

Expected: `Ran 347 tests in ...` ve `OK`.

- [ ] **Step 4: Commit**

```bash
git add --chmod=+x scripts/pg_test.sh
git commit -m "test: gecici PostgreSQL + Redis ile manage.py calistiran pg_test.sh"
```

---

### Task 1: Veritabani secimi (`veritabani_ayari`)

**Files:**
- Modify: `cybernews/ayar_dogrulama.py` (dosya sonuna fonksiyon; ust kisma import)
- Modify: `cybernews/settings.py` (`# Database — PostgreSQL ...` blogu)
- Test: `news/tests/test_ayar_dogrulama.py`

**Interfaces:**
- Consumes: `scripts/pg_test.sh` (Task 0)
- Produces: `veritabani_ayari(ortam: Mapping[str, str], debug: bool, base_dir: Path) -> dict` — `{'default': {...}}`. `DB_HOST` dolu (bosluk degil) -> PostgreSQL; bos ve `debug=False` -> `ImproperlyConfigured`; bos ve `debug=True` -> SQLite `base_dir / 'db.sqlite3'`. `DATABASE_URL` okunmaz.

- [ ] **Step 1: Basarisiz testleri yaz**

`news/tests/test_ayar_dogrulama.py`'de import blogunu degistir:

```python
from cybernews.ayar_dogrulama import (
    BILINEN_ORNEKLER, GELISTIRME_ANAHTARI, dogrulanmis_secret_key,
)
```

yerine:

```python
from pathlib import Path

from django.db import connection

from cybernews.ayar_dogrulama import (
    BILINEN_ORNEKLER, GELISTIRME_ANAHTARI, dogrulanmis_secret_key, veritabani_ayari,
)
```

(Bu satirlar dosyadaki `from django.core.exceptions ...` ve `from django.test ...` importlarinin altinda kalir.) Dosya sonuna ekle:

```python


KOK = Path('/uygulama')


class VeritabaniAyariTest(SimpleTestCase):
    """Faz B1 (spec 5.1): DB_HOST doluysa PostgreSQL; bossa yalniz DEBUG=True iken SQLite."""

    def test_db_host_doluysa_postgresql(self):
        ayar = veritabani_ayari({
            'DB_HOST': 'teknoloji-postgres', 'DB_NAME': 'ad', 'DB_USER': 'kul',
            'DB_PASSWORD': 'p', 'DB_PORT': '6543',
        }, debug=False, base_dir=KOK)['default']
        self.assertEqual(ayar['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(
            (ayar['HOST'], ayar['NAME'], ayar['USER'], ayar['PASSWORD'], ayar['PORT']),
            ('teknoloji-postgres', 'ad', 'kul', 'p', '6543'))
        self.assertEqual(ayar['CONN_MAX_AGE'], 600)
        self.assertTrue(ayar['CONN_HEALTH_CHECKS'])
        self.assertEqual(ayar['OPTIONS'], {'connect_timeout': 10})

    def test_postgresql_varsayilanlari(self):
        ayar = veritabani_ayari({'DB_HOST': 'h'}, debug=False, base_dir=KOK)['default']
        self.assertEqual(
            (ayar['NAME'], ayar['USER'], ayar['PASSWORD'], ayar['PORT']),
            ('cybernews', 'cybernews', '', '5432'))

    def test_uretimde_db_host_yoksa_reddedilir(self):
        for ortam in ({}, {'DB_HOST': ''}, {'DB_HOST': '   '}):
            with self.subTest(ortam=ortam), self.assertRaises(ImproperlyConfigured):
                veritabani_ayari(ortam, debug=False, base_dir=KOK)

    def test_hata_mesaji_parolayi_icermez(self):
        with self.assertRaises(ImproperlyConfigured) as baglam:
            veritabani_ayari({'DB_PASSWORD': 'cok-gizli-parola'}, debug=False, base_dir=KOK)
        self.assertNotIn('cok-gizli-parola', str(baglam.exception))

    def test_gelistirmede_sqlite(self):
        ayar = veritabani_ayari({}, debug=True, base_dir=KOK)['default']
        self.assertEqual(ayar['ENGINE'], 'django.db.backends.sqlite3')
        self.assertEqual(ayar['NAME'], KOK / 'db.sqlite3')

    def test_database_url_okunmaz(self):
        """Eski settings DATABASE_URL doluysa PostgreSQL'e geciyor ama degerini hic okumuyordu."""
        ayar = veritabani_ayari({'DATABASE_URL': 'postgresql'}, debug=True, base_dir=KOK)['default']
        self.assertEqual(ayar['ENGINE'], 'django.db.backends.sqlite3')
        with self.assertRaises(ImproperlyConfigured):
            veritabani_ayari({'DATABASE_URL': 'postgresql'}, debug=False, base_dir=KOK)

    def test_test_ortami_postgresql(self):
        """settings.py fonksiyona bagli mi: testler yalniz PostgreSQL'de kosar (CI, pg_test.sh)."""
        self.assertEqual(connection.vendor, 'postgresql')
```

- [ ] **Step 2: Testin kirmizi oldugunu gor**

```bash
scripts/pg_test.sh test news.tests.test_ayar_dogrulama --noinput 2>&1 | tail -5
```

Expected: `ImportError: cannot import name 'veritabani_ayari'` (ya da `FAILED (errors=1)`).

- [ ] **Step 3: Fonksiyonu yaz**

`cybernews/ayar_dogrulama.py`'de `from typing import Optional` satirini su iki satirla degistir:

```python
from pathlib import Path
from typing import Mapping, Optional
```

Dosya sonuna ekle:

```python


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
```

- [ ] **Step 4: `settings.py`'yi bagla**

`from cybernews.ayar_dogrulama import dogrulanmis_secret_key` satirini su satirla degistir:

```python
from cybernews.ayar_dogrulama import dogrulanmis_secret_key, veritabani_ayari
```

`# Database — PostgreSQL (Kubernetes/Production) veya SQLite (lokal geliştirme)` satirindan baslayip `# Cache — Redis` satirindan hemen onceki bos satira kadar olan blogun TAMAMINI (iki yorum satiri, `DATABASE_URL = ...`, `if DATABASE_URL:` ve `else:` dallari) su iki satirla degistir:

```python
# Database — DB_HOST doluysa PostgreSQL; bossa yalniz DEBUG=True iken SQLite (Faz B1)
DATABASES = veritabani_ayari(os.environ, DEBUG, BASE_DIR)
```

Kontrol:

```bash
grep -n "DATABASE_URL\|sqlite3\|veritabani_ayari" cybernews/settings.py
```

Expected: yalniz iki satir (`import` ve `DATABASES = veritabani_ayari(...)`); `DATABASE_URL` ve `sqlite3` yok.

- [ ] **Step 5: Testleri ve tum paketi kostur**

```bash
scripts/pg_test.sh test news.tests.test_ayar_dogrulama --noinput 2>&1 | grep -E "^Ran |^OK|^FAILED"
scripts/pg_test.sh test news --noinput 2>&1 | grep -E "^Ran |^OK|^FAILED"
scripts/pg_test.sh --sqlite check
```

Expected: ilk kosu `Ran 16 tests` `OK`; ikinci `Ran 354 tests` `OK`; ucuncu `System check identified no issues (0 silenced).`

- [ ] **Step 6: Commit**

```bash
git add cybernews/ayar_dogrulama.py cybernews/settings.py news/tests/test_ayar_dogrulama.py
git commit -m "feat: veritabani DB_HOST'tan secilir, DEBUG=False iken SQLite'a dusulmez"
```

---

### Task 2: Migration 0013 — uc `link` alani 500 karakter

**Files:**
- Modify: `news/models.py` (`NewsArticle.link`, `CVEEntry.link`, `KubernetesEntry.link`)
- Create: `news/migrations/0013_link_max_length_500.py`
- Test: `news/tests/test_modeller.py`

**Interfaces:**
- Consumes: `scripts/pg_test.sh`
- Produces: migration `('news', '0013_link_max_length_500')`; uc modelde `link.max_length == 500`.

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_modeller.py`'de `from news.models import NewsArticle` satirini su satirla degistir:

```python
from news.models import CVEEntry, KubernetesEntry, NewsArticle
```

Dosya sonuna ekle:

```python


class LinkUzunluguTests(TestCase):
    """Faz B1 / 0013: PostgreSQL max_length uygular (SQLite uygulamazdi); uc bolumde link 500."""

    UZUN = 'https://ornek.com/' + 'a' * 450

    def test_alan_sinirlari(self):
        for model in (NewsArticle, CVEEntry, KubernetesEntry):
            with self.subTest(model=model.__name__):
                self.assertEqual(model._meta.get_field('link').max_length, 500)

    def test_uzun_link_yazilir(self):
        NewsArticle.objects.create(
            source='Ornek', original_title='t', turkish_title='t', link=self.UZUN,
            date=date(2026, 9, 18), original_date='18 Sep 2026')
        CVEEntry.objects.create(
            cve_id='CVE-2026-9999', source='NVD', original_title='t', original_description='d',
            published_date=date(2026, 9, 18), link=self.UZUN)
        KubernetesEntry.objects.create(
            source='Kubernetes', original_title='t', original_description='d', link=self.UZUN,
            published_date=date(2026, 9, 18))
        self.assertEqual(KubernetesEntry.objects.get().link, self.UZUN)
```

- [ ] **Step 2: Kirmizi oldugunu gor**

```bash
scripts/pg_test.sh test news.tests.test_modeller --noinput 2>&1 | grep -E "^Ran |^OK|^FAILED|DataError|AssertionError" | head
```

Expected: `FAILED` — `test_alan_sinirlari` `AssertionError: 200 != 500`, `test_uzun_link_yazilir` `DataError: value too long for type character varying(200)`.

- [ ] **Step 3: Modelleri degistir**

`news/models.py`'de uc satiri degistir:

```python
    link = models.URLField(unique=True, verbose_name='Link')
```
->
```python
    link = models.URLField(unique=True, max_length=500, verbose_name='Link')
```

(`NewsArticle` icinde.) `CVEEntry` icinde:

```python
    link = models.URLField(verbose_name='Link')
```
->
```python
    link = models.URLField(max_length=500, verbose_name='Link')
```

`KubernetesEntry` icinde:

```python
    link = models.URLField(verbose_name='Link', unique=True)
```
->
```python
    link = models.URLField(verbose_name='Link', max_length=500, unique=True)
```

Kontrol: `grep -n "link = models.URLField" news/models.py` alti satirin hepsinde `max_length=500` gorulmeli.

- [ ] **Step 4: Migration dosyasini yaz**

`news/migrations/0013_link_max_length_500.py`:

```python
# Faz B1: PostgreSQL max_length uygular (SQLite uygulamazdi). news, cve ve
# kubernetes bolumlerinin link alani diger uc bolumle ayni 500 karaktere cikar.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0012_alter_newsarticle_link'),
    ]

    operations = [
        migrations.AlterField(
            model_name='newsarticle',
            name='link',
            field=models.URLField(max_length=500, unique=True, verbose_name='Link'),
        ),
        migrations.AlterField(
            model_name='cveentry',
            name='link',
            field=models.URLField(max_length=500, verbose_name='Link'),
        ),
        migrations.AlterField(
            model_name='kubernetesentry',
            name='link',
            field=models.URLField(max_length=500, unique=True, verbose_name='Link'),
        ),
    ]
```

- [ ] **Step 5: Migration tutarliligi ve testler**

```bash
scripts/pg_test.sh makemigrations --check --dry-run
scripts/pg_test.sh test news --noinput 2>&1 | grep -E "^Ran |^OK|^FAILED"
```

Expected: `No changes detected`; `Ran 356 tests` `OK`.

- [ ] **Step 6: Commit**

```bash
git add news/models.py news/migrations/0013_link_max_length_500.py news/tests/test_modeller.py
git commit -m "feat: news/cve/kubernetes link alani 500 karakter (migration 0013)"
```

---

### Task 3: `news/veri_tasima.py` ve `veri_ozeti` komutu

**Files:**
- Create: `news/veri_tasima.py`
- Create: `news/management/commands/veri_ozeti.py`
- Test: `news/tests/test_veri_tasima.py`

**Interfaces:**
- Consumes: `scripts/pg_test.sh`
- Produces (Task 4 ve 7-8 kullanir):
  - `HARIC: frozenset[str]` — `{'contenttypes.contenttype', 'auth.permission', 'sessions.session', 'admin.logentry'}`
  - `TamHassasKodlayici(DjangoJSONEncoder)` — `datetime` -> `o.isoformat()`
  - `tasinacak_modeller() -> list[type[Model]]` — proxy ve managed olmayanlar ile `HARIC` disarida, `sort_dependencies` sirasiyla
  - `ozet() -> list[tuple[str, int, str, str]]` — `(model._meta.label, satir_sayisi, alan_sha256, delta_sha256 ya da '-')`
  - Komut: `python manage.py veri_ozeti` — her model icin bir satir, `"{label} {sayi} {alan} {delta}"`

- [ ] **Step 1: Basarisiz testleri yaz**

`news/tests/test_veri_tasima.py`:

```python
"""news/veri_tasima.py ve veri_tasi_dump / veri_ozeti komutlari (Faz B1, spec 5.3).

Testler PostgreSQL'de kosar (CI ve scripts/pg_test.sh). Gidis-donus testi Task 4'te
eklenir: yazilan dosya standart loaddata ile yuklenince ozet birebir ayni kalmali.
"""
import io
import json
from datetime import date, datetime, timezone

from django.core.management import call_command
from django.core.serializers.json import DjangoJSONEncoder
from django.test import SimpleTestCase, TestCase

from news.models import CVEEntry, FetchRun
from news.veri_tasima import TamHassasKodlayici, ozet, tasinacak_modeller

AN = datetime(2026, 9, 18, 12, 41, 6, 25667, tzinfo=timezone.utc)


def cve_olustur(cve_id='CVE-2026-0001', aciklama='Satir bir\r\n \r\nSatir iki '):
    return CVEEntry.objects.create(
        cve_id=cve_id, source='NVD', original_title=f'{cve_id} - ornek',
        original_description=aciklama, published_date=date(2026, 9, 18),
        link=f'https://nvd.example/{cve_id}', cwe_ids=['CWE-79'],
        references=['https://a.example', 'https://b.example'])


class KodlayiciTests(SimpleTestCase):

    def test_mikrosaniye_korunur(self):
        self.assertEqual(json.dumps(AN, cls=TamHassasKodlayici),
                         '"2026-09-18T12:41:06.025667+00:00"')

    def test_django_kodlayicisi_kirpar(self):
        """Ayri kodlayicinin nedeni: Django'nunki milisaniyeye kirpar (spec 2.3)."""
        self.assertEqual(json.dumps(AN, cls=DjangoJSONEncoder), '"2026-09-18T12:41:06.025Z"')


class ModelKumesiTests(SimpleTestCase):

    def test_haric_ve_proxy_modeller_yok(self):
        etiketler = {m._meta.label_lower for m in tasinacak_modeller()}
        for haric in ('contenttypes.contenttype', 'auth.permission', 'sessions.session',
                      'admin.logentry', 'authtoken.tokenproxy'):
            self.assertNotIn(haric, etiketler)
        for gerekli in ('auth.user', 'authtoken.token', 'news.cveentry', 'news.fetchrun',
                        'news.newsarticle', 'news.ainewsentry'):
            self.assertIn(gerekli, etiketler)

    def test_bagimlilik_sirasi(self):
        sira = [m._meta.label_lower for m in tasinacak_modeller()]
        self.assertLess(sira.index('auth.user'), sira.index('authtoken.token'))


class OzetTests(TestCase):

    def setUp(self):
        self.cve = cve_olustur()
        self.run = FetchRun.objects.create(section='cve', status='success',
                                           by_provider={'a': 1, 'b': 2})

    def _delta(self, etiket):
        return {e: d for e, _, _, d in ozet()}[etiket]

    def test_ayni_veride_ayni_ozet(self):
        self.assertEqual(ozet(), ozet())

    def test_metin_degisikligini_yakalar(self):
        once = ozet()
        CVEEntry.objects.filter(pk=self.cve.pk).update(original_description='degisti')
        self.assertNotEqual(ozet(), once)

    def test_mikrosaniye_degisikligini_delta_ozetinde_yakalar(self):
        CVEEntry.objects.filter(pk=self.cve.pk).update(updated_at=AN)
        once = self._delta('news.CVEEntry')
        CVEEntry.objects.filter(pk=self.cve.pk).update(updated_at=AN.replace(microsecond=25000))
        self.assertNotEqual(self._delta('news.CVEEntry'), once)

    def test_json_anahtar_sirasina_duyarsiz(self):
        """PostgreSQL jsonb nesne anahtar sirasini korumaz; ozet bunu fark saymamali."""
        once = ozet()
        FetchRun.objects.filter(pk=self.run.pk).update(by_provider={'b': 2, 'a': 1})
        self.assertEqual(ozet(), once)

    def test_updated_at_olmayan_modelde_delta_tire(self):
        self.assertEqual(self._delta('news.FetchRun'), '-')
        self.assertNotEqual(self._delta('news.CVEEntry'), '-')

    def test_komut_cikti_bicimi(self):
        cikti = io.StringIO()
        call_command('veri_ozeti', stdout=cikti)
        satirlar = cikti.getvalue().strip().splitlines()
        self.assertEqual(len(satirlar), len(tasinacak_modeller()))
        for satir in satirlar:
            self.assertEqual(len(satir.split(' ')), 4, satir)
        self.assertIn('news.CVEEntry 1 ', cikti.getvalue())
```

- [ ] **Step 2: Kirmizi oldugunu gor**

```bash
scripts/pg_test.sh test news.tests.test_veri_tasima --noinput 2>&1 | tail -3
```

Expected: `ModuleNotFoundError: No module named 'news.veri_tasima'`.

- [ ] **Step 3: Modulu yaz**

`news/veri_tasima.py`:

```python
"""Faz B1: SQLite <-> PostgreSQL kayipsiz veri tasima yardimcilari (spec 2.3-2.4, 5.3).

Django'nun hazir serilestiricileri kayiplidir: JSON datetime'i milisaniyeye
kirpar (v1 imleci mikrosaniye tasir), XML metin alanlarini strip eder ve CR'i
kaybeder. Burada yazim JSON'dur ama datetime isoformat() ile tam yazilir; yukleme
standart `loaddata`'dir (raw=True: auto_now updated_at'i ezmez; sequence'leri
kendisi sifirlar).

Ozet serilestiriciden bagimsizdir: iki veritabaninda ayni cikiyorsa tasima kayipsizdir.
"""
import hashlib
import json
from datetime import datetime

from django.apps import apps
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder

# migrate'in kendisinin urettigi ya da tasinmasi anlamsiz tablolar
HARIC = frozenset({
    'contenttypes.contenttype', 'auth.permission', 'sessions.session', 'admin.logentry',
})


class TamHassasKodlayici(DjangoJSONEncoder):
    """DjangoJSONEncoder'in datetime'i milisaniyeye kirpmasini engeller."""

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def tasinacak_modeller():
    """Tasinacak modeller, yukleme sirasina gore (bagimlilar sonra)."""
    adaylar = [
        model for model in apps.get_models()
        if not model._meta.proxy and model._meta.managed
        and model._meta.label_lower not in HARIC
    ]
    return serializers.sort_dependencies([(None, adaylar)], allow_cycles=True)


def _kanonik(deger):
    if isinstance(deger, datetime):
        return deger.isoformat()
    if isinstance(deger, (dict, list)):
        # jsonb nesne anahtar sirasini korumaz; listeler sirayi korur
        return json.dumps(deger, sort_keys=True, ensure_ascii=False)
    return deger


def ozet():
    """Model basina (etiket, satir sayisi, tum alanlarin sha256'si, delta sha256'si).

    Delta ozeti v1 imlec sirasidir: updated_at ASC, id ASC. updated_at alani
    olmayan modelde '-'.
    """
    satirlar = []
    for model in tasinacak_modeller():
        alanlar = [alan.attname for alan in model._meta.concrete_fields]
        alan_ozeti = hashlib.sha256()
        sayi = 0
        for satir in model._default_manager.order_by('pk').values_list(*alanlar).iterator():
            sayi += 1
            alan_ozeti.update(repr(tuple(_kanonik(v) for v in satir)).encode('utf-8'))
        delta = '-'
        if any(alan.name == 'updated_at' for alan in model._meta.concrete_fields):
            delta_ozeti = hashlib.sha256()
            sirali = model._default_manager.order_by('updated_at', 'id')
            for guncellendi, kimlik in sirali.values_list('updated_at', 'id').iterator():
                delta_ozeti.update(f'{guncellendi.isoformat()}|{kimlik};'.encode('utf-8'))
            delta = delta_ozeti.hexdigest()
        satirlar.append((model._meta.label, sayi, alan_ozeti.hexdigest(), delta))
    return satirlar
```

`news/management/commands/veri_ozeti.py`:

```python
"""Tasinacak modellerin serilestiriciden bagimsiz ozeti (Faz B1, spec 5.3).

Iki veritabaninda calistirilip ciktilari diff ile karsilastirilir; fark yoksa
tasima kayipsizdir (tum alanlar ve v1 delta sirasi dahil).
"""
from django.core.management.base import BaseCommand

from news.veri_tasima import ozet


class Command(BaseCommand):
    help = ('Model basina satir sayisi, tum alanlarin sha256 ozeti ve (updated_at, id) '
            'delta ozeti. Iki veritabaninin ciktisi diff ile karsilastirilir.')

    def handle(self, *args, **options):
        for etiket, sayi, alan, delta in ozet():
            self.stdout.write(f'{etiket} {sayi} {alan} {delta}')
```

- [ ] **Step 4: Testler yesil**

```bash
scripts/pg_test.sh test news.tests.test_veri_tasima --noinput 2>&1 | grep -E "^Ran |^OK|^FAILED"
scripts/pg_test.sh test news --noinput 2>&1 | grep -E "^Ran |^OK|^FAILED"
```

Expected: `Ran 10 tests` `OK`; `Ran 366 tests` `OK`.

- [ ] **Step 5: Commit**

```bash
git add news/veri_tasima.py news/management/commands/veri_ozeti.py news/tests/test_veri_tasima.py
git commit -m "feat: serilestiriciden bagimsiz veri_ozeti komutu (Faz B1 tasima dogrulamasi)"
```

---

### Task 4: `veri_tasi_dump` komutu ve gidis-donus testi

**Files:**
- Modify: `news/veri_tasima.py` (dosya sonuna `yaz`)
- Create: `news/management/commands/veri_tasi_dump.py`
- Test: `news/tests/test_veri_tasima.py` (dosya sonuna `GidisDonusTests`)

**Interfaces:**
- Consumes: `tasinacak_modeller()`, `TamHassasKodlayici`, `ozet()` (Task 3)
- Produces: `yaz(akis) -> dict[str, int]` (model etiketi -> yazilan nesne sayisi); komut `python manage.py veri_tasi_dump <cikti_dosyasi>` (stderr'e model basina sayi ve toplam). Dosya standart `python manage.py loaddata <dosya>` ile yuklenir.

- [ ] **Step 1: Basarisiz testleri yaz**

`news/tests/test_veri_tasima.py`'nin import bloguna ekle (mevcut importlarin yanina):

```python
import os
import tempfile

from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token

from news.models import NewsArticle
```

Dosya sonuna ekle:

```python


class GidisDonusTests(TestCase):
    """dump -> tabloyu bosalt -> loaddata: ozet birebir ayni (spec 2.4)."""

    def setUp(self):
        kullanici = get_user_model().objects.create_user('tasima')
        Token.objects.create(user=kullanici)
        NewsArticle.objects.create(
            source='Ornek', original_title='Baslik ', turkish_title='Baslik',
            link='https://ornek.com/haber-1', date=date(2026, 9, 18), original_date='18 Sep 2026')
        cve = cve_olustur()
        CVEEntry.objects.filter(pk=cve.pk).update(updated_at=AN)
        FetchRun.objects.create(section='cve', status='success',
                                by_provider={'libretranslate': 2, 'gemini': 1})

    def _dump(self):
        yol = os.path.join(tempfile.mkdtemp(), 'dump.json')
        call_command('veri_tasi_dump', yol, stderr=io.StringIO())
        return yol

    def _hepsini_sil(self):
        for model in reversed(tasinacak_modeller()):
            model._default_manager.all().delete()

    def test_gidis_donus_ozet_birebir(self):
        once = ozet()
        yol = self._dump()
        self._hepsini_sil()
        self.assertEqual(CVEEntry.objects.count(), 0)
        call_command('loaddata', yol, verbosity=0)
        self.assertEqual(ozet(), once)

    def test_metin_ve_mikrosaniye_aynen_doner(self):
        yol = self._dump()
        with open(yol, encoding='utf-8') as dosya:
            self.assertIn('2026-09-18T12:41:06.025667+00:00', dosya.read())
        self._hepsini_sil()
        call_command('loaddata', yol, verbosity=0)
        cve = CVEEntry.objects.get(cve_id='CVE-2026-0001')
        self.assertEqual(cve.original_description, 'Satir bir\r\n \r\nSatir iki ')
        self.assertEqual(cve.updated_at, AN)
        self.assertEqual(cve.cwe_ids, ['CWE-79'])
        self.assertEqual(NewsArticle.objects.get().original_title, 'Baslik ')

    def test_kullanici_pk_ve_token_korunur(self):
        kullanici = get_user_model().objects.get(username='tasima')
        pk, anahtar = kullanici.pk, Token.objects.get(user=kullanici).key
        yol = self._dump()
        self._hepsini_sil()
        call_command('loaddata', yol, verbosity=0)
        self.assertEqual(get_user_model().objects.get(username='tasima').pk, pk)
        self.assertEqual(Token.objects.get(user__username='tasima').key, anahtar)

    def test_komut_sayilari_stderr_e_yazar(self):
        hata = io.StringIO()
        yol = os.path.join(tempfile.mkdtemp(), 'alt', 'dump.json')
        call_command('veri_tasi_dump', yol, stderr=hata)
        self.assertTrue(os.path.exists(yol))
        self.assertIn('news.CVEEntry 1', hata.getvalue())
        self.assertIn('toplam ', hata.getvalue())
```

- [ ] **Step 2: Kirmizi oldugunu gor**

```bash
scripts/pg_test.sh test news.tests.test_veri_tasima --noinput 2>&1 | grep -E "^Ran |^OK|^FAILED|Unknown command"
```

Expected: `FAILED`; hatalarda `CommandError: Unknown command: 'veri_tasi_dump'`.

- [ ] **Step 3: `yaz` fonksiyonunu ve komutu yaz**

`news/veri_tasima.py` sonuna ekle:

```python


def yaz(akis):
    """Tasinacak tum modelleri `akis`'a tam hassasiyetli JSON olarak yazar.

    pk'ler aynen yazilir (dogal birincil anahtar kullanilmaz; auth.User pk'si
    korunur). Dogal yabanci anahtarlar ContentType/Permission referanslari
    icindir: hedefte bu tablolari migrate yeniden uretir.
    Donus: model etiketi -> yazilan nesne sayisi.
    """
    sayilar = {}

    def nesneler():
        for model in tasinacak_modeller():
            sayi = 0
            for nesne in model._default_manager.order_by('pk').iterator():
                sayi += 1
                yield nesne
            sayilar[model._meta.label] = sayi

    serializers.serialize(
        'json', nesneler(), stream=akis, cls=TamHassasKodlayici, indent=1,
        use_natural_foreign_keys=True, use_natural_primary_keys=False)
    return sayilar
```

`news/management/commands/veri_tasi_dump.py`:

```python
"""Tam hassasiyetli veri dump'i (Faz B1, spec 5.3).

Cikti standart `manage.py loaddata <dosya>` ile yuklenir. Dosya HASSASTIR: parola
hash'leri ve API token'lari icerir; commit edilmez, is bitince silinir.
"""
from pathlib import Path

from django.core.management.base import BaseCommand

from news.veri_tasima import yaz


class Command(BaseCommand):
    help = ("Tasinacak tum modelleri mikrosaniyeyi koruyan JSON olarak yazar "
            "(loaddata ile yuklenir). Dosya hassastir: commit etmeyin.")

    def add_arguments(self, parser):
        parser.add_argument('cikti', help='Yazilacak JSON dosyasinin yolu.')

    def handle(self, *args, **options):
        yol = Path(options['cikti'])
        yol.parent.mkdir(parents=True, exist_ok=True)
        with yol.open('w', encoding='utf-8') as akis:
            sayilar = yaz(akis)
        for etiket, sayi in sayilar.items():
            self.stderr.write(f'{etiket} {sayi}')
        self.stderr.write(f'toplam {sum(sayilar.values())} nesne -> {yol}')
```

- [ ] **Step 4: Testler yesil**

```bash
scripts/pg_test.sh test news.tests.test_veri_tasima --noinput 2>&1 | grep -E "^Ran |^OK|^FAILED"
scripts/pg_test.sh test news --noinput 2>&1 | grep -E "^Ran |^OK|^FAILED"
```

Expected: `Ran 14 tests` `OK`; `Ran 370 tests` `OK`.

- [ ] **Step 5: Commit**

```bash
git add news/veri_tasima.py news/management/commands/veri_tasi_dump.py news/tests/test_veri_tasima.py
git commit -m "feat: mikrosaniyeyi koruyan veri_tasi_dump komutu ve gidis-donus testi"
```

- [ ] **Step 6: Tek review (Global Constraints istisnasi)**

Task 3-4 diff'i (`git diff main -- news/veri_tasima.py news/management/commands/ news/tests/test_veri_tasima.py`) icin tek bir sonnet code review ac. Odak: (a) model kumesinin eksik ya da fazla tablo icermesi, (b) ozetin iki veritabaninda farkli uretebilecegi deger tipleri, (c) `loaddata` ile `pk`/sequence davranisi. Bulgu varsa duzelt, testleri yeniden kostur, ayri commit at.

---

### Task 5: Compose, ortam dosyalari ve CI

**Files:**
- Modify: `docker-compose.yml` (tam icerik asagida)
- Modify: `.env.example`, `.gitignore`, `.dockerignore`
- Modify: `.github/workflows/ci.yml` (`backend` isi ve `manifests` isindeki compose adimi)

**Interfaces:**
- Consumes: `veritabani_ayari` (Task 1) — compose `DB_*` env'leri
- Produces: compose servisi `teknoloji-postgres` (konteyner `teknoloji-postgres`, volume `teknoloji-postgres-data`, db/kullanici `cybernews`); `.env` anahtari `POSTGRES_PASSWORD`; yok sayilan `.fazb/` ve `db.sqlite3.*`.

- [ ] **Step 1: `docker-compose.yml`'yi bu icerikle degistir**

```yaml
services:
  # Django Backend API
  teknoloji-api:
    build: .
    image: teknoloji-haberleri-api:latest
    container_name: teknoloji-api
    user: root
    ports:
      - "8000:8000"
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY:?SECRET_KEY .env icinde tanimli olmali (openssl rand -hex 32)}
      - ALLOWED_HOSTS=localhost,127.0.0.1,teknoloji-api
      - DB_HOST=teknoloji-postgres
      - DB_PORT=5432
      - DB_NAME=cybernews
      - DB_USER=cybernews
      - DB_PASSWORD=${POSTGRES_PASSWORD:?POSTGRES_PASSWORD .env icinde tanimli olmali (openssl rand -hex 24)}
      - REDIS_URL=redis://teknoloji-redis:6379/0
      - CELERY_BROKER_URL=redis://teknoloji-redis:6379/1
      - LIBRETRANSLATE_URL=http://teknoloji-translate:5000
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - RETENTION_DAYS=90
      - GEMINI_CVE_RESERVE=0.5
    depends_on:
      teknoloji-postgres:
        condition: service_healthy
      teknoloji-redis:
        condition: service_started
    volumes:
      - ./:/app
    restart: unless-stopped
    networks:
      - teknoloji-network

  # React Frontend (Vite Dev Server)
  teknoloji-frontend:
    image: node:22-alpine
    container_name: teknoloji-frontend
    working_dir: /app
    ports:
      - "3000:3000"
    volumes:
      - ./frontend:/app
    command: sh -c "npm install && npm run dev -- --host"
    environment:
      - VITE_API_URL=http://localhost:8000/api
    depends_on:
      - teknoloji-api
    restart: unless-stopped
    networks:
      - teknoloji-network

  # LibreTranslate (cekim aninda tek ceviri saglayicisi; Gemini yalniz retranslate'te)
  teknoloji-translate:
    image: libretranslate/libretranslate:v1.9.6
    container_name: teknoloji-translate
    environment:
      - LT_LOAD_ONLY=en,tr
      - LT_UPDATE_MODELS=false
    volumes:
      # Modeller imajda yok, ilk acilista iner (258 MB). Volume olmazsa her
      # yeniden olusturmada tekrar iner ve internet yoksa servis acilmaz.
      - teknoloji-translate-models:/home/libretranslate/.local
    # Denemede yuk altinda 12 cekirdegin tamamini doyurdu; diger servisleri ac birakmasin
    cpus: '4'
    mem_limit: 2g
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/languages', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s
    restart: unless-stopped
    networks:
      - teknoloji-network

  # PostgreSQL (Faz B1: SQLite'in yerine). Veri isimli volume'da; hosta port acilmaz.
  # POSTGRES_USER konteyner icinde superuser'dir: test calistiricisi test_cybernews'i acabilir.
  teknoloji-postgres:
    image: postgres:16.15-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea
    container_name: teknoloji-postgres
    environment:
      - POSTGRES_DB=cybernews
      - POSTGRES_USER=cybernews
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:?POSTGRES_PASSWORD .env icinde tanimli olmali (openssl rand -hex 24)}
    volumes:
      - teknoloji-postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U cybernews -d cybernews"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped
    networks:
      - teknoloji-network

  # Redis Cache & Message Broker
  teknoloji-redis:
    image: redis:7-alpine
    container_name: teknoloji-redis
    ports:
      - "6379:6379"
    volumes:
      - teknoloji-redis-data:/data
    restart: unless-stopped
    networks:
      - teknoloji-network

  # Celery Worker (Arka Plan Görev İşleyici)
  teknoloji-worker:
    build: .
    image: teknoloji-haberleri-api:latest
    container_name: teknoloji-worker
    user: root
    command: celery -A cybernews worker -l info
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY:?SECRET_KEY .env icinde tanimli olmali (openssl rand -hex 32)}
      - ALLOWED_HOSTS=localhost,127.0.0.1,teknoloji-api
      - DB_HOST=teknoloji-postgres
      - DB_PORT=5432
      - DB_NAME=cybernews
      - DB_USER=cybernews
      - DB_PASSWORD=${POSTGRES_PASSWORD:?POSTGRES_PASSWORD .env icinde tanimli olmali (openssl rand -hex 24)}
      - REDIS_URL=redis://teknoloji-redis:6379/0
      - CELERY_BROKER_URL=redis://teknoloji-redis:6379/1
      - LIBRETRANSLATE_URL=http://teknoloji-translate:5000
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - RETENTION_DAYS=90
      - GEMINI_CVE_RESERVE=0.5
    depends_on:
      teknoloji-postgres:
        condition: service_healthy
      teknoloji-redis:
        condition: service_started
      teknoloji-api:
        condition: service_started
    volumes:
      - ./:/app
    restart: unless-stopped
    networks:
      - teknoloji-network

  # Celery Beat Scheduler (Zamanlayıcı)
  teknoloji-scheduler:
    build: .
    image: teknoloji-haberleri-api:latest
    container_name: teknoloji-scheduler
    user: root
    command: celery -A cybernews beat -l info
    environment:
      - DEBUG=False
      - SECRET_KEY=${SECRET_KEY:?SECRET_KEY .env icinde tanimli olmali (openssl rand -hex 32)}
      - ALLOWED_HOSTS=localhost,127.0.0.1,teknoloji-api
      - DB_HOST=teknoloji-postgres
      - DB_PORT=5432
      - DB_NAME=cybernews
      - DB_USER=cybernews
      - DB_PASSWORD=${POSTGRES_PASSWORD:?POSTGRES_PASSWORD .env icinde tanimli olmali (openssl rand -hex 24)}
      - REDIS_URL=redis://teknoloji-redis:6379/0
      - CELERY_BROKER_URL=redis://teknoloji-redis:6379/1
    depends_on:
      teknoloji-postgres:
        condition: service_healthy
      teknoloji-redis:
        condition: service_started
      teknoloji-api:
        condition: service_started
    volumes:
      - ./:/app
    restart: unless-stopped
    networks:
      - teknoloji-network

volumes:
  teknoloji-redis-data:
  teknoloji-translate-models:
  teknoloji-postgres-data:

networks:
  teknoloji-network:
    driver: bridge
```

- [ ] **Step 2: `.env.example` sonuna ekle**

```
# PostgreSQL parolasi: teknoloji-postgres servisi ve uygulama ayni degeri kullanir.
# Zorunlu; bos birakilirsa compose acilmaz. Uretmek icin: openssl rand -hex 24
# Veritabani ilk acilista bu parolayla olusturulur; sonradan degistirmek icin
# volume'daki kullanicinin parolasini da ALTER USER ile degistirmek gerekir.
POSTGRES_PASSWORD=
```

- [ ] **Step 3: `.gitignore` ve `.dockerignore`**

`.gitignore`'da `db.sqlite3-journal` satirinin altina ekle:

```
# Faz B1 gecisi: SQLite yedekleri ve hassas tasima dosyalari (dump, ozet)
db.sqlite3.*
.fazb/
```

`.dockerignore`'da `db.sqlite3-journal` satirinin altina ekle:

```
db.sqlite3.*
.fazb/
```

- [ ] **Step 4: CI `backend` isini PostgreSQL'e bagla**

`.github/workflows/ci.yml`'de `backend` isinin `services:` blogu su anda yalniz `redis` icerir. `redis:` blogunun (son satiri `--health-retries 10`) hemen altina, ayni girintiyle ekle:

```yaml
      postgres:
        image: postgres:16.15-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea
        env:
          POSTGRES_USER: cybernews
          POSTGRES_PASSWORD: ci-gecici-test
          POSTGRES_DB: cybernews
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -h 127.0.0.1 -U cybernews -d cybernews"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 20
```

Ayni isin `env:` blogunda `CELERY_BROKER_URL: redis://127.0.0.1:6379/1` satirinin altina ekle:

```yaml
      # Faz B1: testler PostgreSQL'de kosar; DEBUG=False iken DB_HOST zorunludur
      DB_HOST: 127.0.0.1
      DB_PORT: "5432"
      DB_NAME: cybernews
      DB_USER: cybernews
      DB_PASSWORD: ci-gecici-test
```

`manifests` isinde su satiri:

```yaml
        run: SECRET_KEY=ci-dogrulama-icin-sahte-deger docker compose -f docker-compose.yml config --quiet
```

su satirla degistir (bir ust satirdaki yorum `# SECRET_KEY ve POSTGRES_PASSWORD compose'da :? ile zorunlu; CI sahte deger verir` olur):

```yaml
        run: SECRET_KEY=ci-dogrulama-icin-sahte-deger POSTGRES_PASSWORD=ci-dogrulama-icin-sahte-parola docker compose -f docker-compose.yml config --quiet
```

- [ ] **Step 5: Dogrula**

```bash
SECRET_KEY=x POSTGRES_PASSWORD=y docker compose -f docker-compose.yml config --quiet && echo COMPOSE_OK
docker compose -f docker-compose.yml config --quiet 2>&1 | grep -c "POSTGRES_PASSWORD .env icinde"
SECRET_KEY=x POSTGRES_PASSWORD=y docker compose -f docker-compose.yml config --services | sort | tr '\n' ' '
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/app" --entrypoint python teknoloji-haberleri-api:latest \
  -c "import yaml; d=yaml.safe_load(open('/app/.github/workflows/ci.yml')); j=d['jobs']['backend']; print(sorted(j['services']), j['env']['DB_HOST'])"
git status --short
```

Expected: `COMPOSE_OK`; ikinci satir `1` ya da daha buyuk (parola yoksa compose reddeder); servisler `teknoloji-api teknoloji-frontend teknoloji-postgres teknoloji-redis teknoloji-scheduler teknoloji-translate teknoloji-worker`; `['postgres', 'redis'] 127.0.0.1`; `git status` yalniz bu gorevin bes dosyasi.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml .env.example .gitignore .dockerignore .github/workflows/ci.yml
git commit -m "feat: compose'a PostgreSQL servisi, CI testleri PostgreSQL'de"
```

---

### Task 6: README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1-5'in adlari (`POSTGRES_PASSWORD`, `teknoloji-postgres`, `veri_tasi_dump`, `veri_ozeti`)
- Produces: yok

- [ ] **Step 1: Satir degisiklikleri (her biri birebir eski -> yeni)**

1. `| **Veri** | SQLite (lokal), PostgreSQL 16 (K8s), Redis 7 (cache + broker) |`
   -> `| **Veri** | PostgreSQL 16 (compose ve K8s; SQLite yalniz `DEBUG=True` ile hostta), Redis 7 (cache + broker) |`
2. ``.env.example`'i `.env` olarak kopyalayin ve isterseniz `GEMINI_API_KEY` degerini girin (bos birakilirsa Gemini hic denenmez, sistem LibreTranslate ile calisir):``
   -> ``.env.example`'i `.env` olarak kopyalayin. `SECRET_KEY` (`openssl rand -hex 32`) ve `POSTGRES_PASSWORD` (`openssl rand -hex 24`) zorunludur; `GEMINI_API_KEY` istege baglidir (bos birakilirsa Gemini hic denenmez, sistem LibreTranslate ile calisir):``
3. `| `teknoloji-api` | `teknoloji-haberleri-api:latest` | 8000 | Django REST API, scraping, ceviri, veritabani |`
   -> `| `teknoloji-api` | `teknoloji-haberleri-api:latest` | 8000 | Django REST API, scraping, ceviri |`
4. `| `teknoloji-redis` | `redis:7-alpine` | 6379 | Cache + Celery message broker |` satirinin ALTINA ekle:
   `| `teknoloji-postgres` | `postgres:16.15-alpine` | — | Veritabani; veri `teknoloji-postgres-data` volume'unda, hosta port acilmaz |`
5. Yonetim komutlari kod blogunda `# Django shell` satirindan once ekle:
   ```
   # PostgreSQL shell
   docker compose exec teknoloji-postgres psql -U cybernews -d cybernews

   ```
6. Ortam degiskenleri tablosunda su iki satiri:
   `| `DATABASE_URL` | _(bos)_ | Herhangi bir deger atanirsa PostgreSQL aktif olur, bossa SQLite |`
   `| `DB_HOST` | `localhost` | PostgreSQL host |`
   su iki satirla degistir:
   `| `DB_HOST` | _(bos)_ | Doluysa PostgreSQL kullanilir. Bossa yalniz `DEBUG=True` iken SQLite (`db.sqlite3`); `DEBUG=False` iken uygulama acilmaz. Compose `teknoloji-postgres` verir |`
   `| `POSTGRES_PASSWORD` | (yok) | Yalniz compose: `.env`'den okunur; `teknoloji-postgres` servisi ve uygulamanin `DB_PASSWORD`'u bu degeri kullanir |`
7. `> kullanin ya da komutu konteynerde calistirin (`docker compose exec teknoloji-api ...`).` satirini su iki satirla degistir:
   `> kullanin ya da komutu konteynerde calistirin (`docker compose exec teknoloji-api ...`).`
   `> `DB_HOST` vermezseniz hostta `DEBUG=True` ile yerel `db.sqlite3` kullanilir.`
8. `├── docker-compose.yml          # 5 servis (lokal gelistirme)`
   -> `├── docker-compose.yml          # 7 servis (lokal; PostgreSQL dahil)`

- [ ] **Step 2: Yeni alt bolum**

`### Yonetici Hesabi` basligindan hemen once ekle:

````markdown
### Veri tasima (SQLite -> PostgreSQL)

2026-10'da canli veri SQLite'tan PostgreSQL'e tasindi ([ADR-0007](docs/ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md)). Ayni araclar her iki yonde calisir:

```bash
# Tam hassasiyetli dump (mikrosaniye ve metin bosluklari korunur). Dosya HASSASTIR:
# parola hash'leri ve API token'lari icerir; commit etmeyin, is bitince silin.
python manage.py veri_tasi_dump .fazb/dump.json
# Hedefte: migrate, sonra standart loaddata
python manage.py loaddata .fazb/dump.json
# Iki veritabaninda calistirip ciktilari karsilastirin; fark yoksa tasima kayipsizdir
python manage.py veri_ozeti
```

Django'nun `dumpdata` komutu bu is icin kullanilmaz: JSON bicimi tarihleri milisaniyeye kirpar (v1 imleci mikrosaniye tasir), XML bicimi metin bosluklarini kaybeder.

````

- [ ] **Step 3: Dogrula ve commit**

```bash
grep -c "DATABASE_URL" README.md; grep -c "teknoloji-postgres" README.md; grep -n "veri_tasi_dump" README.md | head -3
git add README.md
git commit -m "docs: README'ye PostgreSQL compose servisi ve veri tasima"
```

Expected: `DATABASE_URL` sayisi `0`; `teknoloji-postgres` sayisi >= 3; `veri_tasi_dump` satirlari gorulur.

---

### Task 7: Prova (canli verinin kopyasiyla, iki yon)

**Files:** yok (yalniz `.fazb/` ve gecici `db.sqlite3`, ikisi de commit edilmez ve sonda silinir)

**Interfaces:**
- Consumes: `scripts/pg_test.sh`, `veri_tasi_dump`, `veri_ozeti` (Task 0, 3, 4)
- Produces: Task 8 icin olculmus sureler ve beklenen nesne sayilari (prova notu, commit edilmez; Task 9'da ADR'ye yazilir)

- [ ] **Step 1: Canli SQLite'in tutarli kopyasi (salt okunur)**

SQLite online backup API'si canli yazicilar varken de tutarli kopya alir. Canli kopyada yalniz gecici bir dosya olusur ve hemen tasinir.

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news-fazb1
docker exec teknoloji-api python -c "
import sqlite3
kaynak = sqlite3.connect('/app/db.sqlite3')
hedef = sqlite3.connect('/app/.fazb-prova.sqlite3')
kaynak.backup(hedef); hedef.close(); kaynak.close(); print('kopya tamam')"
mv ../cybersecurity_news/.fazb-prova.sqlite3 ./db.sqlite3
ls -la db.sqlite3
```

Expected: `kopya tamam`; ~16 MB `db.sqlite3` worktree kokunde.

- [ ] **Step 2: SQLite tarafi (dump + ozet)**

```bash
scripts/pg_test.sh temizle
mkdir -p .fazb
time scripts/pg_test.sh --sqlite veri_tasi_dump /app/.fazb/dump.json
scripts/pg_test.sh --sqlite veri_ozeti > .fazb/ozet_sqlite.txt
cut -d' ' -f1,2 .fazb/ozet_sqlite.txt
```

Expected: stderr'de model basina sayilar ve `toplam ~4.6xx nesne`; ozet satirlarinda `news.CVEEntry ~33xx`, `news.FetchRun ~2xx`, `auth.User 2`, `authtoken.Token 1`.

- [ ] **Step 3: PostgreSQL tarafi (migrate + loaddata + ozet + sequence)**

```bash
scripts/pg_test.sh migrate --noinput -v 0
time scripts/pg_test.sh loaddata /app/.fazb/dump.json
scripts/pg_test.sh veri_ozeti > .fazb/ozet_pg.txt
diff .fazb/ozet_sqlite.txt .fazb/ozet_pg.txt && echo OZET_AYNI
scripts/pg_test.sh shell -v 0 -c "
from django.db import connection
from news.models import NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry, FetchRun
with connection.cursor() as c:
    for M in (NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry, FetchRun):
        c.execute('SELECT pg_get_serial_sequence(%s, %s)', [M._meta.db_table, 'id'])
        seq = c.fetchone()[0]
        c.execute(f'SELECT last_value FROM {seq}')
        son = c.fetchone()[0]
        en_buyuk = M.objects.order_by('-id').values_list('id', flat=True).first() or 0
        print(M.__name__, son, en_buyuk, 'OK' if son >= en_buyuk else 'HATA')
"
```

Expected: `Installed 4xxx object(s) from 1 fixture(s)`; `OZET_AYNI`; yedi satirin hepsi `OK`. `diff` cikti verirse DUR: fark eden modeli raporla, Task 8'e gecme.

- [ ] **Step 4: Geri donus yonu (PostgreSQL -> bos SQLite)**

```bash
scripts/pg_test.sh veri_tasi_dump /app/.fazb/dump_pg.json
mv db.sqlite3 .fazb/kopya.sqlite3
scripts/pg_test.sh --sqlite migrate --noinput -v 0
scripts/pg_test.sh --sqlite loaddata /app/.fazb/dump_pg.json
scripts/pg_test.sh --sqlite veri_ozeti > .fazb/ozet_geri.txt
diff .fazb/ozet_sqlite.txt .fazb/ozet_geri.txt && echo GERI_DONUS_AYNI
```

Expected: `GERI_DONUS_AYNI`.

- [ ] **Step 5: Temizlik ve not**

```bash
rm -rf .fazb db.sqlite3
scripts/pg_test.sh temizle
git status --short
```

Expected: `temizlendi`; `git status` bos. Step 2-3'teki `time` surelerini ve toplam nesne sayisini not al (Task 8'in pencere tahmini ve Task 9'daki ADR icin).

---

### Task 8: Canli gecis (spec 6, Adim 1-8)

> **KONTROL NOKTASI — kullanicidan acik onay al.** Bu gorev canli yigini durdurur. Baslamadan once kullaniciya (a) Task 7 sonuclarini, (b) onerilen pencereyi (asagidaki kurala uyan bir saat) bildir ve "evet" bekle. Onay yoksa durma noktasi burasidir.

**Files:** canli kopyada `git merge` (Task 0-6 commit'leri), `.env` (yalniz `POSTGRES_PASSWORD` eklenir), gecici `.fazb/`

**Interfaces:**
- Consumes: `feat/faz-b1-postgres` dali (Task 0-6), Task 7 notlari
- Produces: PostgreSQL'de calisan canli yigin; `ONCEKI` SHA (geri donus icin); Task 9 icin olcumler (nesne sayilari, sureler, kapatilan satir sayisi, eski en buyuk FetchRun id)

Bu gorevdeki TUM komutlar canli kopyada calisir:

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news
```

- [ ] **Step 1: `.env`'e `POSTGRES_PASSWORD` (deger basilmaz)**

```bash
if grep -qE '^POSTGRES_PASSWORD=.+' .env; then echo VAR; else printf '\nPOSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 24)" >> .env; echo EKLENDI; fi
grep -c '^POSTGRES_PASSWORD=' .env
```

Expected: `EKLENDI` (ya da `VAR`); sayi `1`.

- [ ] **Step 2: Pencere kontrolu (Adim 1)**

Kural: yerel saat 00/06/12/18 OLMAYAN bir **cift** saatte (02, 04, 08, 10, 14, 16, 20, 22), dakika :10-:55 arasi.

```bash
date '+%Y-%m-%d %H:%M'
docker compose exec -T teknoloji-worker celery -A cybernews inspect active --timeout 10
docker compose exec -T teknoloji-api python manage.py shell -v 0 -c "
from datetime import timedelta
from django.utils import timezone
from news.models import FetchRun
print('running_toplam', FetchRun.objects.filter(status='running').count())
print('son_1_saat_running', FetchRun.objects.filter(status='running', started_at__gte=timezone.now() - timedelta(hours=1)).count())
print('max_id', FetchRun.objects.order_by('-id').values_list('id', flat=True).first())"
```

Expected: saat kurala uyar; `inspect active` ciktisinda `- empty -`; `son_1_saat_running 0`. `running_toplam` ve `max_id`'yi not al. Herhangi biri tutmazsa bekle ve tekrar kontrol et.

- [ ] **Step 3: Durdur ve yedekle (Adim 2)**

```bash
docker compose stop teknoloji-scheduler
docker compose stop -t 600 teknoloji-worker
docker compose stop teknoloji-api
docker compose ps --format "{{.Service}} {{.Status}}"
ls db.sqlite3-journal 2>/dev/null && echo "JOURNAL VAR - DUR" || echo journal_yok
YEDEK="db.sqlite3.fazb-yedek-$(date +%Y%m%d)"
cp -p db.sqlite3 "$YEDEK"
python -c "import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute('PRAGMA integrity_check').fetchone()[0])" "$YEDEK"
ls -la db.sqlite3 "$YEDEK"
```

Expected: api/worker/scheduler `Exited`; `journal_yok`; `ok`; iki dosya ayni boyutta.

- [ ] **Step 4: Merge (Adim 3; Netlestirme 1)**

```bash
git status --short
ONCEKI=$(git rev-parse HEAD); echo "ONCEKI=$ONCEKI"
git merge --no-ff feat/faz-b1-postgres -m "Merge feat/faz-b1-postgres: SQLite'tan PostgreSQL'e gecis (Faz B1)"
git log --oneline -1
```

Expected: `git status` bos (yedek dosyasi `db.sqlite3.*` ile yok sayilir); `ONCEKI` SHA'sini not al; merge commit'i olusur.

- [ ] **Step 5: Dump ve SQLite ozeti (Adim 4)**

`--entrypoint python` ZORUNLU: aksi halde `entrypoint.sh` SQLite'a `migrate` uygular ve yedegi bozar.

```bash
mkdir -p .fazb
docker compose run --rm -T --no-deps --entrypoint python -e DEBUG=True -e DB_HOST= teknoloji-api manage.py veri_tasi_dump /app/.fazb/dump.json
docker compose run --rm -T --no-deps --entrypoint python -e DEBUG=True -e DB_HOST= teknoloji-api manage.py veri_ozeti > .fazb/ozet_sqlite.txt
cut -d' ' -f1,2 .fazb/ozet_sqlite.txt
```

Expected: toplam nesne sayisi Task 7 ile tutarli (arada yazilan kayitlar kadar fazla olabilir).

- [ ] **Step 6: PostgreSQL'e yukle ve karsilastir (Adim 5)**

```bash
docker compose up -d teknoloji-postgres
until [ "$(docker inspect -f '{{.State.Health.Status}}' teknoloji-postgres)" = healthy ]; do sleep 2; done; echo pg_healthy
docker compose run --rm -T --no-deps --entrypoint python teknoloji-api manage.py migrate --noinput
docker compose run --rm -T --no-deps --entrypoint python teknoloji-api manage.py loaddata /app/.fazb/dump.json
docker compose run --rm -T --no-deps --entrypoint python teknoloji-api manage.py veri_ozeti > .fazb/ozet_pg.txt
diff .fazb/ozet_sqlite.txt .fazb/ozet_pg.txt && echo OZET_AYNI
docker compose run --rm -T --no-deps --entrypoint python teknoloji-api manage.py shell -v 0 -c "
from django.db import connection
from news.models import NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry, FetchRun
with connection.cursor() as c:
    for M in (NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry, FetchRun):
        c.execute('SELECT pg_get_serial_sequence(%s, %s)', [M._meta.db_table, 'id'])
        seq = c.fetchone()[0]
        c.execute(f'SELECT last_value FROM {seq}')
        son = c.fetchone()[0]
        en_buyuk = M.objects.order_by('-id').values_list('id', flat=True).first() or 0
        print(M.__name__, son, en_buyuk, 'OK' if son >= en_buyuk else 'HATA')
"
```

Expected: `pg_healthy`; migrate `Applying news.0013_link_max_length_500... OK` dahil; `Installed N object(s)`; `OZET_AYNI`; yedi satir `OK`. **`diff` bos degilse ya da bir satir `HATA` ise: DUR, Step 9'daki "Adim 7'den once" geri donusunu kullaniciya oner.**

- [ ] **Step 7: Asili satirlari kapat (Adim 6)**

```bash
docker compose run --rm -T --no-deps --entrypoint python teknoloji-api manage.py shell -v 0 -c "
from news.models import FetchRun
n = FetchRun.objects.filter(status='running').update(
    status='failure', error='asili kaldi: SQLite kilit donemi, Faz B tasimasinda kapatildi')
print('kapatilan', n, 'kalan_running', FetchRun.objects.filter(status='running').count())"
```

Expected: `kapatilan` = Step 2'deki `running_toplam`; `kalan_running 0`.

- [ ] **Step 8: Kaldir ve tam kapi (Adim 7)**

```bash
docker compose up -d --force-recreate teknoloji-api teknoloji-worker teknoloji-scheduler
sleep 20
docker compose ps --format "{{.Service}} {{.Status}}"
docker compose exec -T teknoloji-api python manage.py test news --noinput 2>&1 | grep -E "^Ran |^OK|^FAILED"
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
curl -s -o /dev/null -w "health:%{http_code}\n" http://localhost:8000/api/v1/health/
curl -s -o /dev/null -w "schema:%{http_code}\n" http://localhost:8000/api/v1/schema/
curl -s -o /dev/null -w "admin:%{http_code}\n" http://localhost:8000/admin/login/
curl -s -o /dev/null -w "frontend:%{http_code}\n" http://localhost:3000/
docker compose exec -T teknoloji-api python manage.py shell -v 0 -c "from django.db import connection; print(connection.vendor)"
```

Expected: 7 servis `Up` (postgres `healthy`); `Ran 370 tests` `OK`; `warnings: {}` `errors: {}`; `health:200` `schema:401` `admin:200` `frontend:200`; `postgresql`.

Uctan uca istemci:

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

Expected: alti bolum icin `degisen=` satirlari ve `... kayit upsert edildi`, sonra `silindi`.

Gercek bir cekim ("Cek" butonunun ucu; 429 donerse bolum sogumada demektir, `devtools` ya da `ai` ile tekrarla):

```bash
curl -s -X POST -H 'Content-Type: application/json' -d '{}' http://localhost:8000/api/sre/fetch/; echo
for i in $(seq 1 60); do
  S=$(docker compose exec -T teknoloji-api python manage.py shell -v 0 -c "
from news.models import FetchRun
r = FetchRun.objects.filter(section='sre').order_by('-id').first()
print(r.id, r.status)" | tr -d '\r' | tail -1)
  echo "$S"; case "$S" in *success|*failure) break;; esac; sleep 10
done
```

Expected: ilk satir `"success":true` ve `job_id`; dongu `<id> success` ile biter ve `<id>` Step 2'deki `max_id`'den buyuktur.

Kapilardan biri dusarse: DUR, ciktiyi kullaniciya raporla ve Step 9'daki "Adim 7'den sonra" yolunu oner. Kendi basina geri alma.

- [ ] **Step 9: Geri donus (YALNIZ gerekirse ve kullanici onayiyla)**

*Adim 7'den once* (Step 8 calismadiysa; SQLite'a dokunulmadi, kayip sifir):

```bash
docker compose stop teknoloji-postgres
git reset --hard "$ONCEKI"        # merge push edilmedi; kullanici onayi sart
docker rm -f teknoloji-postgres   # eski compose bu servisi tanimaz; volume korunur
docker compose up -d --force-recreate teknoloji-api teknoloji-worker teknoloji-scheduler
```

*Adim 7'den sonra* (PostgreSQL'e yeni kayit yazildiysa): servisleri durdur (Step 3 sirasiyla), `veri_tasi_dump`'i PostgreSQL'den al (Step 5 komutu, `-e DEBUG=True -e DB_HOST=` OLMADAN), `db.sqlite3`'u kenara al, `git reset --hard "$ONCEKI"`, bos SQLite'i `docker compose run --rm -T --no-deps teknoloji-api python manage.py migrate --noinput` ile kur, `loaddata` ile yukle, iki ozeti karsilastir, sonra `up -d --force-recreate`. Bu yol Task 7 Step 4'te prova edildi.

- [ ] **Step 10: Temizlik (Adim 8)**

```bash
rm -rf .fazb
ls db.sqlite3.fazb-yedek-*
git status --short
```

Expected: yedek dosyasi duruyor (14 gun tutulur); `git status` bos.

---

### Task 9: ADR-0007 (B1 bolumu) ve iliskili ADR notlari

**Files:**
- Create: `docs/ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md`
- Modify: `docs/ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md`, `docs/ADR-0006-FetchRun-Gorunurlugu-ve-Status-Ucu.md`, `README.md` (ADR tablosu)

**Interfaces:**
- Consumes: Task 7 ve 8'de not alinan olcumler
- Produces: ADR-0007 (B2 Task 6 "Helm" bolumunu ekler ve durumu gunceller)

Canli kopyada (`main`) calisilir.

- [ ] **Step 1: ADR-0007'yi yaz**

Asagidaki metni yaz. `[olcum]` ile isaretli yerlere Task 7/8 ciktilarindaki GERCEK degerleri yaz (sayilar, sureler, SHA); baska hicbir sey uydurma.

```markdown
# ADR 0007: PostgreSQL Gecisi ve Helm Dogrulamasi (Faz B)

## Status
Accepted — 2026-10-01. **B1 (PostgreSQL) uygulandi** ([olcum: gecis tarihi], merge commit [olcum: SHA]). B2 (Helm dogrulamasi) acik.

Tasarim: [`superpowers/specs/2026-10-01-faz-b-postgres-helm-design.md`](superpowers/specs/2026-10-01-faz-b-postgres-helm-design.md). Planlar: `superpowers/plans/2026-10-01-faz-b1-postgres.md`, `superpowers/plans/2026-10-01-faz-b2-helm.md`. Spec ile plan celistiginde planlarin "Spec'e Gore Netlestirmeler" bolumleri gecerlidir.

## Context
SQLite yazma kilidi canli isleri dusuruyordu: 2026-09-23..30 arasinda 194 FetchRun'in 10'u `database is locked` ile dustu, 5 satir `running`'de asili kaldi (`journal_mode=delete`, `busy_timeout=5000`, 12 prefork worker + gunicorn + beat ayni dosyaya yaziyor). Helm chart'i hic deploy edilmemisti ve guncel kodun gerisindeydi.

Tasarim sirasindaki problar (2026-09-30) yontemi belirledi:
- 347 test PostgreSQL 16.15'te degisiklik yapilmadan gecti.
- Django'nun `dumpdata` JSON bicimi datetime'i milisaniyeye kirpar (CVE'lerin 3305/3308'i etkilenir; v1 imleci mikrosaniye tasir); XML bicimi metin alanlarini `strip()` eder ve CR'i kaybeder (381 satir).
- Tam hassasiyetli JSON (`isoformat()`) + standart `loaddata` dokuz modelde tum alan ve `(updated_at, id)` delta ozetlerini birebir korudu; sequence'ler sifirlandi.

## Decision
1. **Veritabani `DB_HOST`'tan secilir** (`cybernews/ayar_dogrulama.py::veritabani_ayari`). Bossa yalniz `DEBUG=True` iken SQLite; `DEBUG=False` iken acilis reddedilir. `DATABASE_URL` okunmaz.
2. **Compose'a `teknoloji-postgres`** (16.15, digest'e sabit, isimli volume, hosta port yok); parola `.env`'deki `POSTGRES_PASSWORD`.
3. **Tasima `veri_tasi_dump` + `loaddata`, dogrulama `veri_ozeti`.** Ozet serilestiriciden bagimsizdir (model basina satir sayisi, tum alanlarin ve delta sirasinin sha256'si). Dogal birincil anahtar kullanilmaz: `pk`'ler aynen korunur.
4. **Migration 0013:** `news`/`cve`/`kubernetes` `link` 200 -> 500 (PostgreSQL `max_length` uygular).
5. **CI testleri yalniz PostgreSQL'de.**
6. **Asili 5 FetchRun satiri `failure` olarak kapatildi** (`error`: "asili kaldi: SQLite kilit donemi, Faz B tasimasinda kapatildi"; `finished_at` bos).

### Elenen alternatifler
| Alternatif | Neden elendi |
|---|---|
| `dumpdata` JSON / XML | Mikrosaniye / metin bosluklari kaybi (Context) |
| pgloader | Dogrulamanin disinda bir tip cevirim katmani |
| Iki DB takma adi arasinda ORM kopyasi | Settings'e yalniz tasima icin dal; sequence sifirlama elle |
| Sifir kesintili cift yazma | ~4.600 satir icin orantisiz |
| `DATABASE_URL` ayristirma (`dj-database-url`) | Yeni bagimlilik; `DB_*` kalibi zaten her yerde |

## Gecis (B1)
| Olcut | Deger |
|---|---|
| Prova (Task 7): dump / loaddata suresi | [olcum] / [olcum] |
| Prova: ozet ve geri donus ozeti | ayni / ayni |
| Canli gecis penceresi | [olcum: saat araligi] |
| Tasinan nesne | [olcum: toplam ve model basina] |
| Ozet farki | yok |
| Sequence kontrolu | 7/7 OK |
| Kapatilan asili satir | [olcum] |
| Tam kapi | [olcum: test sayisi] test OK, health 200, schema 401, istemci uctan uca |
| Ilk PostgreSQL cekimi | FetchRun [olcum: id] `success` |

48 saatlik olcum: (B1 Task 10'da eklenir)

## Consequences
- **Positive:** Yazma kilidi kalkar; worker ve api eszamanli yazabilir. v1 imleci gecisten etkilenmedi (delta ozeti ayni). Env'i eksik bir kurulum acilista hata verir.
- **Negative / kabul edilen sinirlar:** SQLite yolu yalniz hostta `DEBUG=True` ile kalir ve CI'da test edilmez. `jsonb` nesne anahtar sirasini korumaz (`by_provider` admin'de farkli sirada gorunebilir). Geri donus Adim 7'den sonra ters yonde dump/yukleme gerektirir. SQLite yedegi (`db.sqlite3.fazb-yedek-*`) 14 gun tutulur.
```

- [ ] **Step 2: ADR-0005 ve ADR-0006 notlari**

`docs/ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md`'de:
`Faz B — `RETENTION_DAYS` ve `GEMINI_CVE_RESERVE` configmap'e girer.`
-> `Faz B — `RETENTION_DAYS` ve `GEMINI_CVE_RESERVE` configmap'e girer (Helm, B2). Veri PostgreSQL'e tasindi: [ADR-0007](ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md).`

`docs/ADR-0006-FetchRun-Gorunurlugu-ve-Status-Ucu.md`'de:
`Faz B — PostgreSQL ve Helm; `FetchRun` tablosu tasinacak veriye eklenir.`
-> `Faz B — PostgreSQL ve Helm; `FetchRun` tablosu tasinacak veriye eklenir. **B1 tamamlandi:** FetchRun dahil tum veri ozet esitligiyle PostgreSQL'e tasindi, asili 5 satir kapatildi ([ADR-0007](ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md)).`

`README.md` ADR tablosunda ADR-0006 satirinin altina:
`| [ADR-0007](docs/ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md) | SQLite'tan PostgreSQL'e kayipsiz gecis ve Helm chart dogrulamasi (Faz B) | Accepted (B1 uygulandi; B2 acik) |`

- [ ] **Step 3: Commit ve push sorusu**

```bash
git add docs/ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md docs/ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md docs/ADR-0006-FetchRun-Gorunurlugu-ve-Status-Ucu.md README.md
git commit -m "docs: ADR-0007 Faz B1 PostgreSQL gecisi ve olcumleri"
git log --oneline -3
```

Kullaniciya sor: "B1 `main`'de (push edilmedi). Push edip CI'i (PostgreSQL'li backend isi) kosturalim mi?" Push yalniz "evet" gelirse: `git push origin main`; ardindan CI'in `backend` ve `manifests` islerinin yesil oldugunu `gh run list --branch main --limit 5` ile kontrol et.

- [ ] **Step 4: Worktree'yi kaldir**

```bash
git worktree remove ../cybersecurity_news-fazb1
git branch -d feat/faz-b1-postgres
git worktree list
```

Expected: yalniz canli kopya listelenir.

---

### Task 10: 48 saatlik olcum (gecisten en az 48 saat sonra, ayri oturum)

**Files:**
- Modify: `docs/ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md` ("48 saatlik olcum" satiri)

**Interfaces:**
- Consumes: Task 8 Step 2'deki `max_id` (gecis oncesi en buyuk FetchRun id)
- Produces: ADR-0007'de olcum

- [ ] **Step 1: Olc**

`<max_id>` yerine Task 8 Step 2'de not alinan sayiyi yaz:

```bash
cd C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news
docker compose exec -T teknoloji-api python manage.py shell -v 0 -c "
from datetime import timedelta
from django.db.models import Count
from django.utils import timezone
from news.models import FetchRun
yeni = FetchRun.objects.filter(id__gt=<max_id>)
print('tur', yeni.count())
print('durum', list(yeni.values('status').annotate(n=Count('id')).order_by('status')))
print('locked', yeni.filter(error__icontains='locked').count())
print('asili', yeni.filter(status='running', started_at__lt=timezone.now() - timedelta(hours=2)).count())
print('ilk', yeni.order_by('started_at').values_list('started_at', flat=True).first())"
```

Expected: `locked 0`; `asili 0`.

- [ ] **Step 2: ADR'ye yaz ve commit**

`48 saatlik olcum: (B1 Task 10'da eklenir)` satirini su bicimde degistir: `48 saatlik olcum ([tarih]): [tur] tur, durumlar [durum], 'database is locked' 0, asili running 0.` (degerler Step 1 ciktisindan). Sonuc beklenenden farkliysa (locked > 0 ya da asili > 0) ADR'ye oldugu gibi yaz ve kullaniciya systematic-debugging ile inceleme oner.

```bash
git add docs/ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md
git commit -m "docs: ADR-0007'ye 48 saatlik PostgreSQL olcumu"
```

Push yalniz kullanici isterse.
