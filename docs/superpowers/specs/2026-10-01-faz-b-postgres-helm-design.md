# Faz B — PostgreSQL Gecisi ve Helm Dogrulamasi — Tasarim

- **Tarih:** 2026-10-01 (tasarim oturumu 2026-09-30'da basladi)
- **Durum:** Tasarim onaylandi (bolum 1-4 kullanici onayindan gecti). Uygulanmadi.
- **Planlar:** `../plans/2026-10-01-faz-b1-postgres.md` (B1), `../plans/2026-10-01-faz-b2-helm.md` (B2)
- **Kapsam:** Canli yerel compose yiginini SQLite'tan PostgreSQL 16'ya kayipsiz tasimak (B1);
  hic deploy edilmemis Helm chart'ini guncel kodla calisir hale getirip yalniz yerel
  Docker Desktop Kubernetes'inde (`docker-desktop` baglami) gercek kurulumla dogrulamak (B2).
- **Iliskili:** [ADR-0003](../../ADR-0003-Entegrasyon-API-v1.md) (v1 delta sozlesmesi),
  [ADR-0004](../../ADR-0004-Ceviri-Saglayici-Zinciri.md) (LibreTranslate acik isi),
  [ADR-0005](../../ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md) (`RETENTION_DAYS`, `GEMINI_CVE_RESERVE`),
  [ADR-0006](../../ADR-0006-FetchRun-Gorunurlugu-ve-Status-Ucu.md) (FetchRun tasinir),
  `2026-09-12-entegrasyon-api-v1-design.md` bolum 16, `2026-09-30-hizli-isler-design.md` (Faz B notlari).
- **Migration:** **Var** (`0013`, uc `link` alani 200 -> 500). Yalniz PostgreSQL'e uygulanir; SQLite 0012'de yedek kalir.

## 1. Neden

1. **SQLite kilitleniyor.** Son 7 gunde 194 FetchRun'in 10'u `database is locked` ile dustu,
   5 satir `running`'de asili kaldi. Olculen yapilandirma: `journal_mode=delete`,
   `busy_timeout=5000`; compose worker'inda `--concurrency` yok (12 prefork sureci),
   gunicorn 4 worker ve scheduler ayni dosyaya yaziyor.
2. **Chart hic deploy edilmedi** ve guncel kodun gerisinde: LibreTranslate yok, alti env eksik,
   probe'lar yanlis uca gidiyor, `ALLOWED_HOSTS: "*"`, parolalar `required` degil (bkz. 2.5).
3. **Tasinacak veri kayipsiz tasinmali** ve v1 delta sozlesmesi (`updated_at` + `id` imleci,
   `updated_at ASC, id ASC` sirasi) bozulmamali: tuketicinin elindeki imlec gecisten sonra da
   ayni kayda isaret etmeli.

## 2. Olcumler ve problar (2026-09-30)

Problar tek kullanimlik `postgres:16-alpine` konteynerinde kostu; canli SQLite yalniz okundu,
prob konteyneri ve hassas dump dosyasi sonra silindi.

### 2.1 Veri

| Model | Satir |
|---|---:|
| `news.CVEEntry` | 3308 |
| `news.AINewsEntry` | 592 |
| `news.FetchRun` | 268 (250 success, 13 failure, 5 running) |
| `news.NewsArticle` | 208 |
| `news.SREEntry` | 72 |
| `news.KubernetesEntry` | 70 |
| `news.DevToolsEntry` | 54 |
| `auth.User` / `authtoken.Token` | 2 / 1 |
| `django_celery_beat.*`, `admin.LogEntry` | 0 |

`db.sqlite3` 16 MB. Metin alanlarinda NUL karakteri yok; sinirina %80'den fazla yaklasan tek
`CharField` sabit 40 karakterli token anahtari.

### 2.2 Testler PostgreSQL'de

347 testin tamami PostgreSQL 16.15'te **gecti** (8.2 sn). Test tarafinda duzeltme isi yok.

### 2.3 Django'nun hazir serilestiricileri kayipli

| Yol | Kayip | Etki |
|---|---|---|
| `dumpdata` (JSON) | `DjangoJSONEncoder` datetime'i **milisaniyeye** kirpar | CVE'lerin 3305/3308'inde milisaniye alti kisim var; `updated_at` geri kayar, imlec hassasiyetindeki sira ve `published_date`/`started_at` degerleri bozulur |
| `dumpdata --format xml` | Okuyucu metin alanlarini `strip()` eder, XML ayristiricisi `\r\n`'i `\n` yapar | 381 satirda bas/son bosluk ve CR kaybi |

Imlec tam mikrosaniye tasir (`news/api_v1/cursor.py::encode_cursor` -> `isoformat()`).

### 2.4 Kayipsiz yol: tam hassasiyetli JSON + standart `loaddata`

`serializers.serialize('json', ..., cls=<datetime'i isoformat() ile yazan kodlayici>,
use_natural_foreign_keys=True, use_natural_primary_keys=True)` ile yazilan dosya standart
`loaddata` ile yuklendi (4575 nesne, 8.8 sn). Serilestiriciden bagimsiz ozet:

- Dokuz modelin hepsinde **tum alanlarin SHA-256'si** ve **`(updated_at, id)` sirali delta
  SHA-256'si** kaynak ile hedefte birebir ayni.
- `loaddata` `raw=True` kullandigi icin `auto_now` `updated_at`'i ezmez.
- `loaddata` sequence'leri kendisi sifirlar: `news_cveentry_id_seq` last_value 12767 = max id,
  `news_fetchrun_id_seq` 268 = max id.

### 2.5 Imaj ve chart bulgulari

- **Imaj kod iceriyor:** `Dockerfile` `COPY . .`; `/app/news`, `/app/cybernews` var, uid/gid
  999 (chart'in `runAsUser: 999`'u ile uyumlu). Imaja gereksiz dosyalar da siziyor:
  `celerybeat-schedule`, `docs/`, `helm/`, `k8s/`. `staticfiles/` bos (collectstatic calisma
  aninda). Compose bu imaji bind mount (`./:/app`) ve `user: root` ile kullaniyor.
- **`settings.py`** PostgreSQL'e `DATABASE_URL` doluysa geciyor ama degerini hic okumuyor
  (baglanti `DB_*`'dan kuruluyor); chart bu yuzden `DATABASE_URL: "postgresql"` veriyor.
- **Parola hatasi:** chart `POSTGRES_USER=DB_USER`, `POSTGRES_PASSWORD=postgresPassword`
  veriyor; uygulama ayni kullaniciyla `DB_PASSWORD=dbPassword` ile baglaniyor. Iki deger
  farkli girilirse uygulama hic baglanamaz.
- PVC icin `fsGroup` yok: Postgres (uid 70) root sahipli volume'a yazamaz.
- Migration `post-install,post-upgrade` hook'u; backend pod'lari da entrypoint'te
  `migrate || true` calistiriyor (2 replika + Job = uc eszamanli migrate).
- Probe'lar `/api/news/` (cache-first eski uc); `/api/v1/health/` kullanilmiyor.
- Eksik: LibreTranslate Deployment/Service/PVC, `GEMINI_API_KEY`, `RETENTION_DAYS`,
  `GEMINI_CVE_RESERVE`, `REFRESH_*`, `TRANSLATE_MIN_RATIO`, `RETRANSLATE_*`, `LIBRETRANSLATE_*`.
- `namespace.yaml` + `global.namespace` Helm'in `-n`/`--create-namespace` kalibiyla celisiyor.
- `k8s/` ham manifest'leri chart'in elle tutulan, kaymis bir kopyasi. `helm;C` ve
  `helm/tech-radar;C` bos cop dizinler.
- LibreTranslate konteyneri uid 1032, gid 65534 ile kosuyor (canli konteynerden olculdu).
- `GET /api/v1/health/` DB'ye ve Redis'e dokunmaz (`news/api_v1/views.py::HealthView`).

### 2.6 Ortam

- `kubectl` aktif baglami **`aks-gokbulut`** (baska projenin uretim kumesi). `docker-desktop`
  baglami tanimli ama kume kapali. `helm` kurulu degil (`alpine/helm` konteyneri calisiyor ama
  `127.0.0.1`'deki API'ye ulasamaz).

## 3. Guvenlik siniri — yalniz yerel (kullanici karari)

1. **Hicbir ortama release yok:** registry'ye imaj push'u, uzak kume, git tag, GitHub release yok.
   `git push` yalniz kullanici istediginde.
2. **`aks-gokbulut`'a hicbir kosulda dokunulmaz.** Her `kubectl` cagrisi `--context docker-desktop`,
   her `helm` cagrisi `--kube-context docker-desktop` tasir; `kubectl config use-context` hic
   cagrilmaz. Kume isi yapan her adim once baglamin yerel oldugunu dogrular.
3. **Gercek bir hedef kume** icin kurulum talimatlari (README, `NOTES.txt`, bu spec) yalniz
   `<placeholder>` sablonu olarak yazilir ve calistirilmaz:

   ```bash
   helm upgrade --install tech-radar ./helm/tech-radar \
     --kube-context <hedef-baglam> -n <namespace> --create-namespace \
     --set secrets.secretKey="<openssl rand -hex 32>" \
     --set secrets.dbPassword="<guclu-sifre>" \
     --set ingress.host=<alan-adi> \
     --set backend.image.repository=<registry>/teknoloji-haberleri-api \
     --set backend.image.tag=<surum> \
     --set frontend.image.repository=<registry>/teknoloji-haberleri-frontend \
     --set frontend.image.tag=<surum>
   ```
4. Canli yerel yigina dokunan riskli adimdan once kopya veriyle ayri bir compose projesinde
   **prova** yapilir.

## 4. Alinan kararlar

| # | Karar | Secenekler / gerekce |
|---|---|---|
| K1 | Helm dogrulamasi **Docker Desktop Kubernetes** uzerinde | kind (indirme + `kind load`), yalniz statik dogrulama (calisma zamani hatalarini yakalamaz) elendi |
| K2 | **`k8s/` silinir, Helm tek kaynak** | `helm template` ciktisini commit etmek, iki kopyayi elle tutmak elendi |
| K3 | Canli gecis **kisa planli yazma kesintisiyle** | "okuma acik kalsin" (arada gelen "Cek" eski DB'ye yazilabilir, ek kilit gerekir) elendi |
| K4 | Veri tasima: **tam hassasiyetli JSON dump + standart `loaddata` + ayri ozet komutu** | bkz. bolum 13 |
| K5 | Is **B1 (PostgreSQL) -> B2 (Helm)** olarak bolunur; tek spec, iki plan | B1 canli olayi cozer ve tek basina deger uretir; B2 PostgreSQL'de kanitlanmis kodun uzerine kurulur |
| K6 | 5 asili `running` FetchRun satiri gecis sirasinda `failure` olarak kapatilir | Bilinen kilit kurbanlari; acik kalirlarsa "asili tur" sinyalini kalici kirletirler |

## 5. B1 — Bilesenler

### 5.1 Veritabani secimi

Yeni saf fonksiyon `cybernews/ayar_dogrulama.py::veritabani_ayari(ortam, debug, base_dir) -> dict`
(`dogrulanmis_secret_key` ile ayni kalip; `ortam` bir `Mapping[str, str]`, donus degeri
`DATABASES` sozlugudur). `settings.py` `DATABASES = veritabani_ayari(os.environ, DEBUG, BASE_DIR)`.

| Durum | Sonuc |
|---|---|
| `DB_HOST` dolu | PostgreSQL: `NAME=DB_NAME` (vars. `cybernews`), `USER=DB_USER` (vars. `cybernews`), `PASSWORD=DB_PASSWORD` (vars. `''`), `HOST=DB_HOST`, `PORT=DB_PORT` (vars. `5432`), `CONN_MAX_AGE=600`, `CONN_HEALTH_CHECKS=True`, `OPTIONS={'connect_timeout': 10}` |
| `DB_HOST` bos/bosluk, `debug=True` | SQLite: `base_dir / 'db.sqlite3'` (hostta `manage.py` calismaya devam eder) |
| `DB_HOST` bos/bosluk, `debug=False` | `ImproperlyConfigured("DB_HOST tanimli degil: DEBUG=False iken SQLite'a dusulmez ...")` |

`DATABASE_URL` hicbir yerde okunmaz ve compose/Helm/README'den kalkar. Test:
`news/tests/test_ayar_dogrulama.py`'ye yeni siniflar (test kesfi yalniz `news` altinda).

Gerekce: env'i eksik bir pod veya konteyner sessizce gecici bir SQLite yaratip "calisiyormus"
gibi gorunmemeli; hata acilista gorunur olmali.

### 5.2 Compose

- Yeni servis `teknoloji-postgres`: `postgres:16-alpine@sha256:<digest>` (plan digest'i yazar),
  `POSTGRES_DB=cybernews`, `POSTGRES_USER=cybernews`,
  `POSTGRES_PASSWORD=${POSTGRES_PASSWORD:?...}`, isimli volume `teknoloji-postgres-data`,
  healthcheck `pg_isready -U cybernews -d cybernews`, `restart: unless-stopped`, **hosta port
  acilmaz**.
- `teknoloji-api`, `teknoloji-worker`, `teknoloji-scheduler`: `DB_HOST=teknoloji-postgres`,
  `DB_NAME=cybernews`, `DB_USER=cybernews`, `DB_PASSWORD=${POSTGRES_PASSWORD:?...}`,
  `DB_PORT=5432`; `depends_on: teknoloji-postgres: condition: service_healthy`.
- `.env.example`'a `POSTGRES_PASSWORD=` satiri ve uretim komutu (`openssl rand -hex 24`).
- CI `manifests` isindeki `docker compose config` adimi `POSTGRES_PASSWORD` sahte degerini de alir.
- Compose'daki `POSTGRES_USER` konteyner icinde superuser'dir; test calistiricisinin
  `test_cybernews` veritabanini acabilmesi (CREATEDB) buna dayanir.

### 5.3 Yonetim komutlari (`news/management/commands/`)

**`veri_tasi_dump <cikti_dosyasi>`**
- Modeller: `django.apps.apps.get_models()` icinden proxy ve managed olmayanlar ile
  `contenttypes.ContentType`, `auth.Permission`, `sessions.Session`, `admin.LogEntry` disarida;
  kalanlar `django.core.serializers.sort_dependencies` sirasiyla, her model `order_by('pk')`.
- Kodlayici: `DjangoJSONEncoder` alt sinifi, `datetime` icin `o.isoformat()` (mikrosaniye korunur).
- `use_natural_foreign_keys=True`, `use_natural_primary_keys=True`, `indent=1`.
- Sonda model basina yazilan nesne sayisini stderr'e basar.
- **Dosya hassastir** (parola hash'leri, API token'i): commit edilmez (`.fazb/` gitignore'da),
  is bitince silinir.

**`veri_ozeti [--json]`**
- Ayni model kumesi. Model basina: satir sayisi; tum `concrete_fields` degerlerinin `pk`
  sirasiyla SHA-256'si; `updated_at` alani olan modellerde `(updated_at, id)` sirali
  `"{updated_at.isoformat()}|{id};"` akisinin SHA-256'si.
- Kanoniklestirme: `datetime` -> `isoformat()`; `dict`/`list` -> `json.dumps(sort_keys=True,
  ensure_ascii=False)` (PostgreSQL `jsonb` nesne anahtar sirasini korumaz).
- Cikti deterministiktir; iki veritabaninin ciktilari `diff` ile karsilastirilir.

Iki komut da veritabanindan bagimsizdir: ayni komutlar geri donuste ters yonde calisir.

### 5.4 Migration `0013`

`news/migrations/0013_link_max_length_500.py`: `NewsArticle.link`, `CVEEntry.link`,
`KubernetesEntry.link` `URLField(max_length=500)` olur (diger uc bolumle ayni; mevcut
`unique`/`verbose_name` ozellikleri korunur). Gerekce: SQLite `max_length` uygulamaz,
PostgreSQL uygular; 200 karakteri asan ilk link o kaydi `DataError` ile dusururdu.

### 5.5 CI

`backend` isine `postgres:16-alpine` servis konteyneri (healthcheck'li) ve
`DB_HOST=127.0.0.1`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_PORT` env'leri eklenir. Testler
yalniz PostgreSQL'de kosar; SQLite kosusu kalkar. `MIN_TESTS` degismez.

### 5.6 Calisma yeri

Compose bind mount ile calistigi icin canli calisma kopyasi B1 dalina gecerse bir sonraki
worker yeniden baslatmasi `DB_HOST` zorunlulugu yuzunden yigini dusurur. **B1 ayri bir git
worktree'de uygulanir** (dal `feat/faz-b1-postgres`). Testler worktree'yi baglayan tek seferlik
konteynerde, tek kullanimlik bir PostgreSQL'e karsi kosar. Canli kopya yalniz gecis aninda
`main`'e cekilir.

## 6. B1 — Canli gecis proseduru

**On kosul:** B1 `main`'e `--no-ff` merge edilmis ve worktree'de tam test yesil; `.env`'e
`POSTGRES_PASSWORD` yazilmis (`openssl rand -hex 24`; deger hicbir ciktiya dusmez).

| Adim | Is | Kapi |
|---|---|---|
| 0 | **Prova.** `db.sqlite3` kopyasi ayri bir compose projesinde (`-p fazb-prova`: portsuz, kendi PostgreSQL volume'u ve Redis'i) adim 4-6 aynen kosulur; proje `down -v` ile silinir | Ozet `diff` bos, sequence'ler dogru |
| 1 | **Pencere.** 00/06/12/18 disindaki bir cift saatte :10-:55 (fetch slotlari 00/06/12/18 :00-:50, retranslate tek saatlerde :05) | `celery inspect active` bos; son 1 saatte acilmis `running` FetchRun yok |
| 2 | **Durdur ve yedekle.** `stop teknoloji-scheduler`, `stop teknoloji-worker` (warm shutdown), `stop teknoloji-api`; `db.sqlite3` -> `db.sqlite3.fazb-yedek-<YYYYMMDD>` (`db.sqlite3.*` ve `.fazb/` B1 dalinda `.gitignore`'a eklenmistir) | Yedekte `PRAGMA integrity_check` = `ok` |
| 3 | **Canli kopyayi guncelle.** `git checkout main` (servisler durduktan sonra) | `git log -1` merge commit'i |
| 4 | **Dump.** `docker compose run --rm --no-deps --entrypoint python -e DEBUG=True -e DB_HOST= teknoloji-api manage.py veri_tasi_dump /app/.fazb/dump.json`; ayni bicimde `veri_ozeti` -> `.fazb/ozet_sqlite.txt` | Nesne sayilari 2.1 ile tutarli |
| 5 | **Yukle.** `up -d teknoloji-postgres` (healthy beklenir); tek seferlik konteynerde `migrate --noinput`, `loaddata /app/.fazb/dump.json`, `veri_ozeti` -> `.fazb/ozet_pg.txt` | `diff` bos; alti icerik tablosu ve FetchRun'da sequence `last_value` = max id |
| 6 | **Asili satirlar.** 5 `running` FetchRun -> `status='failure'`, `error='asili kaldi: SQLite kilit donemi, Faz B tasimasinda kapatildi'`; `finished_at` bos kalir | `running` sayisi 0 |
| 7 | **Kaldir ve kapi.** `up -d --force-recreate teknoloji-api teknoloji-worker teknoloji-scheduler` | Tam kapi (asagida) + arayuzden bir "Cek" -> FetchRun `success`, yeni `id` > eski max id |
| 8 | **Temizlik.** `.fazb/dump.json` silinir; SQLite yedegi 14 gun tutulur | — |
| 9 | **Gozlem.** 48 saat sonra olculur ve ADR-0007'ye yazilir | `database is locked` ile dusen FetchRun 0, asili `running` 0 |

**`--entrypoint python` zorunludur:** `entrypoint.sh` Celery disindaki her komutta `migrate`
calistirir; bayrak olmadan adim 4 SQLite'a 0013'u uygular ve yedegi bozar.

**Tam kapi** (proje kurali, B1 sonrasi hali): compose yeniden olusturma, 7 servis Up
(postgres dahil), `docker exec teknoloji-api python manage.py test news` (347 + yeni testler,
compose PostgreSQL'inde `test_cybernews` acilir), sema 0 uyari, `/api/v1/health/` 200,
`/api/v1/schema/` tokensiz 401, `:3000` 200, `scripts/ornek_istemci.py` uctan uca.

**Geri donus:**
- *Adim 7'den once:* SQLite'a hic dokunulmamistir. Onceki commit'e donulur, `up -d`. Kayip sifir.
- *Adim 7'den sonra:* ayni iki komut ters yonde. Onceki commit'in koduyla bos bir SQLite
  `migrate` edilir, PostgreSQL'den alinan `veri_tasi_dump` `loaddata` ile yuklenir, ozetler
  karsilastirilir. Gecisten sonra yazilan kayitlar da korunur; 0013'un 500 karakterlik
  linkleri SQLite'ta sorun cikarmaz.

## 7. B2 — Chart degisiklikleri

1. **Parolalar.** `secrets.dbPassword` tek parola olur ve `required` (mesaj: uretim komutuyla).
   `secrets.postgresPassword` kalkar; Postgres konteynerinin `POSTGRES_PASSWORD`'u da
   `DB_PASSWORD` anahtarindan okunur. Yeni istege bagli `secrets.geminiApiKey` (`""` -> Gemini
   kapali) secret'a `GEMINI_API_KEY` olarak girer.
2. **Probe'lar ve `ALLOWED_HOSTS`.**
   - Backend readiness ve liveness `GET /api/v1/health/`, `httpHeaders: [{name: Host, value: localhost}]`
     (pod IP'leri degisken oldugu icin listeye yazilamaz).
   - `ALLOWED_HOSTS` sablonda acikca kurulur: `localhost`, `backend.name` (kume ici tuketici),
     `ingress.enabled` ise `ingress.host`, ve `config.django.extraAllowedHosts`. `*` ve
     `config.django.allowedHosts` kalkar.
   - `CSRF_TRUSTED_ORIGINS`: `ingress.enabled` ise `http(s)://<ingress.host>` (TLS'e gore) ve
     `config.django.extraCsrfTrustedOrigins`.
3. **ConfigMap.** `DATABASE_URL` kalkar. Kodun okuyup chart'ta olmayan env'ler `config.app`
   altinda, **koddaki varsayilanlarla** eklenir:

   | Env | Varsayilan |
   |---|---|
   | `REFRESH_COOLDOWN` / `REFRESH_LOCK_TTL` | `900` / `3600` |
   | `TRANSLATE_MIN_RATIO` | `0.4` |
   | `RETRANSLATE_BATCH` / `RETRANSLATE_UPGRADE_BATCH` | `100` / `40` |
   | `RETENTION_DAYS` | `90` |
   | `GEMINI_CVE_RESERVE` / `GEMINI_DAILY_BUDGET` / `GEMINI_MODEL` | `0.5` / `400` / `gemini-3.5-flash-lite` |
   | `LIBRETRANSLATE_TIMEOUT` / `LIBRETRANSLATE_COOLDOWN` / `LIBRETRANSLATE_CHUNK_CHARS` | `60` / `60` / `160` |
   | `LIBRETRANSLATE_URL` | `libretranslate.enabled` ise `http://<libretranslate.name>:<port>`, degilse `""` |
   | `RUN_STARTUP_TASKS` | `false` (madde 6) |

4. **LibreTranslate** (yeni `templates/libretranslate.yaml`, `libretranslate.enabled: true`):
   Deployment (`libretranslate/libretranslate:v1.9.6`, `LT_LOAD_ONLY=en,tr`,
   `LT_UPDATE_MODELS=false`, uid 1032 / gid 65534, `Recreate` stratejisi), Service (5000),
   PVC 1 Gi -> `/home/libretranslate/.local` (modeller bir kez iner). `startupProbe`
   `GET /languages` ilk acilistaki 258 MB model indirmesi icin 10 dk tanir; readiness/liveness
   ayni uc. Kaynaklar compose ile ayni: sinir 4 CPU / 2 Gi.
5. **`fsGroup`.** `tech-radar.podSecurityContext` yardimcisi `fsGroup: <runAsGroup>` ve
   `fsGroupChangePolicy: OnRootMismatch` ekler. `tech-radar.containerSecurityContext`
   yardimcisi `global.containerSecurityContext`'i bilesenin istege bagli
   `containerSecurityContext`'i ile birlestirir (`mergeOverwrite`); boylece gerekirse tek
   bilesende gevseme yapilabilir.
6. **Migration akisi.**
   - Hook kalkar. Her revizyonda yeni adli normal bir Job: `<migration.name>-r{{ .Release.Revision }}`
     (Job spec'i degistirilemez oldugu icin ad revizyona baglanir). Job PostgreSQL'i bekler ve
     `python manage.py migrate --noinput` calistirir.
   - api, worker ve scheduler'a `migrasyon-bekle` initContainer'i (ayni backend imaji):
     `python manage.py migrate --check` basarili olana kadar 5 sn arayla doner.
     Boylece tek bir migrate calisir ve `helm --wait --wait-for-jobs` kilitlenmez.
   - `entrypoint.sh` yeni `RUN_STARTUP_TASKS` bayragini okur (varsayilan `true`: compose
     davranisi degismez). `false` iken migrate ve collectstatic atlanir; PostgreSQL/Redis
     beklemesi surer.
7. **Imaj.**
   - `collectstatic` build sirasinda imaja gomulur
     (`DEBUG=True SECRET_KEY=<yalniz-build-icin> python manage.py collectstatic --noinput`,
     sahiplik `appuser`). Backend ve Job'daki `staticfiles` `emptyDir`'i kalkar.
   - `.dockerignore`'a `docs/`, `helm/`, `k8s/`, `celerybeat-schedule`, `db.sqlite3.*`, `.fazb/`.
8. **Namespace.** `templates/namespace.yaml` ve `global.namespace` kalkar; her kaynak
   `{{ .Release.Namespace }}` kullanir. `NOTES.txt` ayni sekilde guncellenir.
9. **Temizlik.** `k8s/`, `helm;C`, `helm/tech-radar;C` silinir.
10. **Bilincli olarak degismeyenler:** Redis `emptyDir` (bkz. bolum 12); Postgres `Deployment`
    + `Recreate` + PVC (StatefulSet'e gecilmez); ingress sablonu ve yollari.

## 8. B2 — `docker-desktop` dogrulamasi

### 8.1 On kosullar (kullanici)

1. Docker Desktop -> Settings -> Kubernetes -> **Enable**; Docker Desktop'a en az 8 GB bellek
   (compose yigini da acik kalir).
2. **Helm 3 CLI** (`winget install Helm.Helm`), kullanicinin kurmasi ya da acik onayi ile.
   Gerekce: `helm` konteyneri `docker-desktop` API'sine (`127.0.0.1:<port>`) ulasamaz; gercek
   `install`/`upgrade` davranisi (revizyon, `--wait-for-jobs`) yerel CLI ister.

### 8.2 Betik: `scripts/helm_yerel_dogrulama.sh`

Dogrulamanin tamami tekrar kosulabilir tek betikte:

- Baglam sabit `docker-desktop`; betik onu degistiremez. Her cagri `kubectl --context
  docker-desktop` / `helm --kube-context docker-desktop`.
- Baslangic kontrolleri (biri tutmazsa hicbir sey kurmadan cikar): baglam tanimli; baglamin
  sunucu adresi `127.0.0.1`, `localhost` veya `kubernetes.docker.internal`; dugum adi
  `docker-desktop` veya `desktop-` onekli.
- Namespace sabit `tech-radar-dogrulama`.
- Gizli degerler calisma aninda uretilir (`openssl rand`), hicbir ciktiya basilmaz;
  `secrets.geminiApiKey` bos (test kumesi gercek kotayi harcamaz).
- Alt komutlar: `kur` (S1-S6), `sok` (S7). Her senaryo gecti/kaldi satiri basar; ilk kalan
  senaryoda cikis kodu 1 ile durur.

### 8.3 Yerel imajlar

- `teknoloji-haberleri-api:fazb-yerel` ve `teknoloji-haberleri-frontend:fazb-yerel` yerelde
  derlenir; registry yok.
- `helm/tech-radar/ci/yerel-values.yaml`: `pullPolicy: Never`, tek replika, `ingress.enabled:
  false`, LibreTranslate sinirlari 2 CPU / 1.5 Gi.
- Docker Desktop'in kind tabanli modu yerel imajlari kumeye kendiliginden gostermeyebilir:
  betik ilk pod'da `ErrImageNeverPull` gorurse imajlari `docker save | docker exec -i
  <dugum-konteyneri> ctr -n k8s.io images import -` ile dugume yukler ve tekrar dener.

### 8.4 Kabul senaryolari

| # | Senaryo | Beklenen |
|---|---|---|
| S1 | `helm upgrade --install ... -f ci/yerel-values.yaml --wait --wait-for-jobs --timeout 15m` | cikis 0; tum pod'lar Ready; `teknoloji-migrate-r1` Complete; api'de `migrate --check` cikis 0 |
| S2 | port-forward (18000 -> api, 13000 -> frontend; compose'un 3000/8000'i ile cakismaz) | `/api/v1/health/` 200, `/api/v1/schema/` tokensiz 401, `/` 200, `/admin/login/` 200, `/static/admin/css/base.css` 200 (imajdaki statik), sahte `Host` 400 |
| S3 | Uctan uca is: `POST /api/sre/fetch/` (frontend uzerinden, anonim) | 200 baslatildi; <= 10 dk icinde FetchRun `success`; worker'dan LibreTranslate `/languages` 200 |
| S4 | `helm upgrade` (bir configmap degeri degisir, ornegin `config.app.retentionDays=91`) | revizyon 2, `teknoloji-migrate-r2` Complete, pod'lar yenilenir, SRE satir sayisi degismez |
| S5 | Postgres pod'u silinir | yeni pod Ready, satir sayisi ayni (`fsGroup` + PVC kaniti) |
| S6 | `helm template` `secrets.secretKey` ya da `secrets.dbPassword` olmadan | ikisi de anlamli `required` mesajiyla hata |
| S7 | Sokum: `helm uninstall` + namespace silme | namespace ve PVC'ler gider; compose yigini etkilenmez |

- Gercek veri Kubernetes'e tasinmaz: chart'in guncel kodla calistiginin kaniti bos veritabani
  uzerinde gercek bir cekimdir.
- LibreTranslate ilk acilista 258 MB model indirir; internet gerekir.
- `readOnlyRootFilesystem` LibreTranslate'i bozarsa yalniz o bilesende 7.5'teki birlestirmeyle
  gevsetilir ve ADR-0007'ye bilincli sapma olarak yazilir.

## 9. B2 — CI (`manifests` isi)

- `helm lint` ve `helm template` gerekli degerlerle (`secretKey` + `dbPassword`, LibreTranslate acik).
- `kubeconform -strict -summary` (Kubernetes 1.31 semasi), imaj digest'e sabitli (zizmor ve
  Scorecard kuralina uygun).
- **Negatif test:** `dbPassword` verilmeden render hata vermeli (verirse is kirmizi).
- Cikti kontrolleri: render'da `ALLOWED_HOSTS: "*"`, `postgresPassword`, `DATABASE_URL`
  gecmemeli; `teknoloji-translate` Deployment'i bulunmali.
- `docker compose config` `SECRET_KEY` ve `POSTGRES_PASSWORD` sahte degerleriyle.

## 10. Belgeler

- **README:**
  - Compose bolumu: `POSTGRES_PASSWORD`, PostgreSQL servisi, hostta `DEBUG=True` ile SQLite notu.
  - Kubernetes bolumu: `k8s/` anlatimi kalkar; ham YAML isteyen `helm template` kullanir;
    gercek kume kurulumu yalniz bolum 3.3'teki `<placeholder>` sablonu; yerel dogrulama betigi.
  - Proje agacindan `k8s/` ve `DATABASE_URL` kalkar.
- **Yeni ADR-0007** "PostgreSQL Gecisi ve Helm Dogrulamasi": kararlar (bolum 4), prob
  bulgulari (bolum 2), elenen yollar (bolum 13), gecis ve 48 saatlik olcum sonucu, S1-S7 sonucu.
- **ADR-0003...0006:** "Faz B" acik is satirlari tamamlandi olarak guncellenir.
- **`docs/GUVENLIK-PLANI.md`:** `dbPassword` `required` maddesi kapanir.

## 11. Sira ve kapilar

| Sira | Is | Dal | Kapi |
|---|---|---|---|
| 1 | B1 kod | `feat/faz-b1-postgres` (worktree) | Tek kullanimlik PostgreSQL'de tum testler + yeni testler; `makemigrations --check`; prova (adim 0) |
| 2 | B1 gecis | `main` (canli kopya) | Bolum 6 tablosu; tam kapi |
| 3 | B1 gozlem | — | 48 saat sonra adim 9 |
| 4 | B2 | `feat/faz-b2-helm` (worktree) | `helm lint/template`, kubeconform, betik S1-S7 yesil; compose tam kapi (entrypoint/Dockerfile degisti) |
| 5 | Belgeler | ayni dallar | — |

Her is ayri dal, `--no-ff` merge (depo kalibi). Kapiyi gecemeyen is geri alinir, push
edilmez, rapor edilir. B2, B1 gecisinden sonra baslar; 48 saatlik gozlemi beklemek zorunda
degildir.

## 12. Kabul edilen sinirlar

- **Helm'de Redis `emptyDir`:** pod yeniden baslarsa bolum kilitleri, soguma, cache ve Celery
  kuyrugu kaybolur; Beat isleri bir sonraki slotta yeniden planlar. Compose'da Redis volume'da
  kalir.
- **Readiness DB'yi kontrol etmez** (`/api/v1/health/` bilincli olarak bagimsiz): PostgreSQL
  duserse pod'lar Ready kalir, istekler 500 doner.
- **`jsonb` nesne anahtar sirasini korumaz:** `FetchRun.by_provider` admin'de farkli sirada
  gorunebilir; deger ayni. Listeler (`cwe_ids`, `references`) sirayi korur.
- **`backend.name` frontend imajina bagli:** `frontend/nginx.conf` `teknoloji-api:8000`'e
  proxy'ler; `backend.name` degistirilirse frontend imaji yeniden derlenmelidir.
- **`helm rollback` sema geri almaz:** yeni revizyon Job'u yeniden `migrate` calistirir (ileri
  yonde no-op); geri alma yalniz kod icindir.
- **SQLite yolu yalniz `DEBUG=True` hostta kalir** ve CI'da artik test edilmez.
- **Docker Desktop != uretim kumesi:** storage class, ingress controller, NetworkPolicy ve
  cok dugumlu zamanlama dogrulanmaz.
- **Geri donus penceresi adim 7'den sonra** ters yonde dump/yukleme gerektirir (bolum 6).

## 13. Elenen alternatifler

| Alternatif | Neden elendi |
|---|---|
| `dumpdata` JSON | Milisaniyeye kirpar (2.3); imlec sozlesmesini bozar |
| `dumpdata` XML | Metin bosluklarini ve CR'i kaybeder (2.3) |
| pgloader | Harici arac; SQLite metin tarihlerini ve Django JSON alanlarini kendi tip eslemesiyle yorumlar, dogrulamanin disinda bir cevirim katmani |
| Iki DB takma adi arasinda ORM kopyasi | Settings'e yalniz tasima icin dal girer, sequence sifirlama elle yazilir; `loaddata` ayni `raw=True` yolunu zaten test edilmis haliyle verir |
| Sifir kesintili cift yazma | ~4.600 satir icin orantisiz karmasiklik |
| "Okuma acik kalsin" gecisi | Arada gelen "Cek" eski DB'ye yazilabilir; ek kilit adimi (K3) |
| `dj-database-url` / `DATABASE_URL` ayristirma | Yeni bagimlilik; `DB_*` kalibi entrypoint, compose ve chart'ta zaten var |
| `k8s/`'i koruma (uretilmis veya elle) | K2 |
| kind / yalniz statik dogrulama | K1 |
| `helm` konteyneri | `127.0.0.1`'deki kume API'sine ulasamaz |
| `ALLOWED_HOSTS: "*"` veya pod CIDR | Hizli isler P4'u geri alir / pod IP'leri degisken; probe'a `Host` basligi vermek yeterli |
| `pre-install` migration hook'u | PostgreSQL ayni release'in parcasi; hook onu bekleyemez |
| Her pod'da initContainer ile `migrate` | Eszamanli migrate; PostgreSQL'de Django migrate kilitsizdir |
| `post-install` hook + `--wait` | Pod'lar migration'i bekledigi icin kilitlenir |
| StatefulSet / Bitnami alt chart'i | Tek replikali Postgres icin `Deployment` + `Recreate` + PVC yeterli; alt chart bagimlilik ve imaj degisikligi getirir |

## 14. Kapsam disi

- Gercek veriyi Kubernetes'e tasimak; registry, imaj yayinlama, gercek kume kurulumu.
- `django_celery_beat` `DatabaseScheduler` karari (entegrasyon spec'i 16, ertelenen madde 1).
- Compose worker `--concurrency` ayari (PostgreSQL ile kilit sorunu ortadan kalkar; ayri olcum).
- Helm'de Redis kaliciligi, HPA, PodDisruptionBudget, NetworkPolicy, PostgreSQL yedekleme CronJob'u.
- Readiness'in DB'yi kontrol etmesi (ayri bir `/ready` ucu gerektirir; v1 sozlesmesi degisir).
- Olu kod temizligi (`gui*.py`, `scraper*.py`, `static/js/app.js`).
