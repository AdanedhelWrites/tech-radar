# ADR 0007: PostgreSQL Gecisi ve Helm Dogrulamasi (Faz B)

## Status
Accepted — 2026-10-01. **B1 (PostgreSQL) uygulandi** (canli gecis 2026-10-02 02:10-02:15, merge commit `a492d38`). **B2 (Helm dogrulamasi) uygulandi** (2026-10-03, docker-desktop'ta S1-S7 gecti); chart 2.0.0, appVersion 2026.10.1.

Tasarim: [`superpowers/specs/2026-10-01-faz-b-postgres-helm-design.md`](superpowers/specs/2026-10-01-faz-b-postgres-helm-design.md). Planlar: `superpowers/plans/2026-10-01-faz-b1-postgres.md`, `superpowers/plans/2026-10-01-faz-b2-helm.md`. Spec ile plan celistiginde planlarin "Spec'e Gore Netlestirmeler" ve "Plan Degisikligi" bolumleri gecerlidir.

## Context
SQLite yazma kilidi canli isleri dusuruyordu: 2026-09-23..30 arasinda 194 FetchRun'in 10'u `database is locked` ile dustu, 5 satir `running`'de asili kaldi (gecis aninda 6). Yapilandirma: `journal_mode=delete`, `busy_timeout=5000`, 12 prefork worker + gunicorn + beat ayni dosyaya yaziyordu. Helm chart'i hic deploy edilmemisti ve guncel kodun gerisindeydi.

Tasarim sirasindaki problar (2026-09-30) yontemi belirledi:
- 347 test PostgreSQL 16.15'te degisiklik yapilmadan gecti.
- Django'nun `dumpdata` JSON bicimi datetime'i milisaniyeye kirpar (CVE'lerin 3305/3308'i etkilenir; v1 imleci mikrosaniye tasir); XML bicimi metin alanlarini `strip()` eder ve CR'i kaybeder (381 satir).
- Tam hassasiyetli JSON (`isoformat()`) + standart `loaddata` dokuz modelde tum alan ve `(updated_at, id)` delta ozetlerini birebir korudu; sequence'ler sifirlandi.

## Decision
1. **Veritabani `DB_HOST`'tan secilir** (`cybernews/ayar_dogrulama.py::veritabani_ayari`). Bossa yalniz `DEBUG=True` iken SQLite; `DEBUG=False` iken acilis reddedilir. `DATABASE_URL` okunmaz.
2. **Paylasilan yerel PostgreSQL** (kullanici karari 2026-10-02): ayri repo `yerel-platform` kullanicinin kisisel uygulamalari icin tek bir PostgreSQL 16.15 calistirir (`yerel-postgres`, digest'e sabit, isimli volume, yalniz `127.0.0.1:5432`, Docker agi `yerel-platform`). Uygulama basina veritabani + ayni adli kullanici (CREATEDB; CONNECT PUBLIC'ten alinmis, capraz erisim reddi dogrulandi). CyberNews compose kendi PostgreSQL'ini tasimaz: `DB_HOST=yerel-postgres`, dis ag, parola `.env`'deki `DB_PASSWORD`. Ilk tasarimdaki compose ici `teknoloji-postgres` servisi bu kararla kalkti.
3. **Tasima `veri_tasi_dump` + `loaddata`, dogrulama `veri_ozeti`.** Ozet serilestiriciden bagimsizdir (model basina satir sayisi, tum alanlarin, auto-created M2M iliskilerinin ve delta sirasinin sha256'si). Dogal birincil anahtar kullanilmaz: `pk`'ler aynen korunur. Dump dosyasi `0600` ile yazilir (parola hash'i ve token icerir).
4. **Migration 0013:** `news`/`cve`/`kubernetes` `link` 200 -> 500 (PostgreSQL `max_length` uygular).
5. **CI testleri yalniz PostgreSQL'de.** Yerel testler `scripts/pg_test.sh` ile tek kullanimlik PostgreSQL + Redis'te kosar.
6. **Asili 6 FetchRun satiri `failure` olarak kapatildi** (`error`: "asili kaldi: SQLite kilit donemi, Faz B tasimasinda kapatildi"; `finished_at` bos).

### Elenen alternatifler
| Alternatif | Neden elendi |
|---|---|
| `dumpdata` JSON / XML | Mikrosaniye / metin bosluklari kaybi (Context) |
| pgloader | Dogrulamanin disinda bir tip cevirim katmani |
| Iki DB takma adi arasinda ORM kopyasi | Settings'e yalniz tasima icin dal; sequence sifirlama elle |
| Sifir kesintili cift yazma | ~5.200 satir icin orantisiz |
| `DATABASE_URL` ayristirma (`dj-database-url`) | Yeni bagimlilik; `DB_*` kalibi zaten her yerde |
| Compose icinde uygulamaya ozel PostgreSQL | Kullanici tek, paylasilan bir yerel sunucu istedi (diger kisisel uygulamalar da kullanacak) |
| PostgreSQL'i Windows'a dogrudan kurmak | Compose ve Kubernetes konteyner kullaniyor; surum sabitlemesi ve volume ile tasinabilirlik kaybolur |

## Gecis (B1)
| Olcut | Deger |
|---|---|
| Prova 1 (tek kullanimlik PG, 2026-10-02 00:13) | 5138 nesne; dump 11.0 sn, loaddata 14.0 sn; ozet ayni; sequence 7/7; geri donus (PG -> bos SQLite) ozeti ayni |
| Prova 2 (yerel-platform, gecici `cybernews_prova`) | 5223 nesne; loaddata 7.9 sn; ozet ayni; sequence 7/7; ayni kullanici yetkileriyle 375 test OK |
| Canli gecis penceresi | 2026-10-02 02:10-02:15 (yazma kesintisi ~5 dk) |
| Tasinan nesne | 5233 (CVE 3829, AI 641, haber 231, FetchRun 321, SRE 79, Kubernetes 74, DevTools 55, User 2, Token 1; beat tablolari bos) |
| Dump / loaddata | 5.6 sn / 8.4 sn |
| Ozet farki | yok |
| Sequence kontrolu | 7/7 OK |
| Kapatilan asili satir | 6 |
| Tam kapi | 6 servis Up + `yerel-postgres` healthy; 375 test OK; sema 11 yol, 0 uyari/0 hata; health 200, schema 401, admin 200, frontend 200; ornek istemci 4909 kayit upsert |
| Ilk PostgreSQL cekimi | FetchRun 322 `success` (sre, fetched 15, saved 1) |
| SQLite yedegi | `db.sqlite3.fazb-yedek-20261002` (14 gun tutulur; hash canli dosyayla ayni) |

Gecis sirasinda yakalanan bir plan hatasi: Git Bash `docker compose run ... /app/...` yolunu `C:/Program Files/Git/app/...` olarak cevirdi ve ilk dump konteyner icine yazilip kayboldu. SQLite'a dokunulmadi (hash dogrulandi); komut `MSYS_NO_PATHCONV=1` ile tekrarlandi. Plan metni duzeltildi.

48 saatlik olcum: (B1 Task 10'da eklenir)

## Helm Dogrulamasi (B2)

### Karar
7. **Helm tek dagitim kaynagi;** `k8s/` silindi. Ham manifest isteyen `helm template` kullanir.
8. **Chart surumlenir (K7):** SemVer `version` (bu faz 1.0.0 -> 2.0.0), `appVersion` = uygulama imaj etiketi (CalVer `2026.10.1`), `helm/tech-radar/CHANGELOG.md` (MAJOR'da yukseltme notu). Values'ta kayan etiket yok: ucuncu taraf imajlar surum + digest ile sabit. CI: `scripts/chart_surum_kontrol.sh` (chart degistiyse surum artmali ve CHANGELOG basligi olmali), `scripts/imaj_etiket_kontrol.sh`, kubeconform, zorunlu deger negatif testi.
9. **Tek parola:** `secrets.dbPassword` zorunlu; `postgresPassword` kalkti (iki deger farkli girilince uygulama baglanamiyordu).
10. **Migration** her revizyonda `teknoloji-migrate-r<N>` Job'unda; uygulama pod'lari `migrate --check` initContainer'inda bekler. Hook ve entrypoint'teki eszamanli migrate kalkti (`RUN_STARTUP_TASKS=false`); statik dosyalar imajda.
11. **Probe'lar** `/api/v1/health/` + `Host: localhost`; `ALLOWED_HOSTS` sablonda acik liste (`*` kalkti).
12. **LibreTranslate** chart'a girdi (PVC'de modeller); eksik env'ler `config.app.*`; `fsGroup` eklendi; pod'lar configmap/secret checksum'iyla yenilenir. Kok dosya sistemi her bilesende salt okunur kaldi: LibreTranslate'in yazdigi `.config`, `.cache`, `/app/db` (Prometheus metrik dizini) ve `/tmp` icin `emptyDir`.
13. **Dogrulama yalniz yerel `docker-desktop`'ta** (`scripts/helm_yerel_dogrulama.sh`; baglam sabit, yerel olmayan kume reddedilir). Gercek kume talimatlari yalniz `<placeholder>` sablonu.

### Ortam
Docker Desktop Kubernetes **kubeadm** saglayicisi (tek dugum `docker-desktop`, v1.36.1, runtime docker: yerel imajlar kumede dogrudan gorunur). kind saglayicisi denendi ama Docker containerd image store'u kapali oldugu icin kume acilmadi; store'u acmak canli yiginin imajlarini gizleyecegi icin tercih edilmedi. Helm 4.3.0.

### Sonuc (2026-10-03)
| Senaryo | Sonuc |
|---|---|
| S1 kurulum (`--wait --wait-for-jobs`) | GECTI — tum pod'lar Ready, `teknoloji-migrate-r1` Complete, `migrate --check` 0 |
| S2 HTTP | GECTI — health 200, schema tokensiz 401, frontend/admin/static 200, sahte `Host` 400 |
| S3 uctan uca | GECTI — worker -> LibreTranslate `/languages` 200, SRE cekimi FetchRun `success` |
| S4 upgrade | GECTI — revizyon 2, `teknoloji-migrate-r2` Complete, configmap degisikligi (RETENTION_DAYS 91) pod'lari yeniledi, veri korundu |
| S5 PostgreSQL pod silme | GECTI — yeni pod Ready, FetchRun sayisi korundu (PVC + fsGroup) |
| S6 zorunlu degerler | GECTI — `secretKey`/`dbPassword` olmadan render anlamli mesajla reddedildi |
| S7 sokum | GECTI — release, namespace ve PVC'ler silindi; compose yigini etkilenmedi |

Basarili kosu: 4 dk 23 sn (imaj derleme haric). Yerel imajlar dugume yuklenmeden kumede gorundu.

**Dogrulamanin buldugu iki gercek hata** (ikisi de bu faza kadar hic deploy edilmedigi icin gorunmemisti):
1. LibreTranslate salt okunur kokte `/home/libretranslate/.config` ve `/app/db/prometheus`'a yazamiyor, `CrashLoopBackOff`. Cozum guvenlik ayarini gevsetmek degil, bu iki dizine `emptyDir` (spec 8.4'teki "gevset" yedegine gerek kalmadi).
2. `frontend/nginx.conf`'ta `location ~* \.(js|css|...)$` regex blogu, `^~` olmayan `/api/`, `/admin/`, `/static/` onek bloklarindan oncelikliydi: `/static/*.css` api'ye proxy'lenmeyip 404 donuyordu (compose'da frontend Vite dev sunucusu oldugu icin hic gorulmedi). Cozum: uc blok `location ^~`.

### Kabul edilen sinirlar (B2)
- Redis `emptyDir`: pod yeniden baslarsa kilit/soguma/cache/kuyruk kaybolur.
- Readiness DB'yi kontrol etmez (`/api/v1/health/` bilincli olarak bagimsiz).
- `helm rollback` sema geri almaz.
- `backend.name` frontend imajina (`nginx.conf`) bagli.
- Docker Desktop uretim kumesi degildir: storage class, ingress controller, NetworkPolicy ve cok dugumlu zamanlama dogrulanmadi.

## Consequences
- **Positive:** Yazma kilidi kalkar; worker ve api eszamanli yazabilir. v1 imleci gecisten etkilenmedi (delta ozeti ayni). Env'i eksik bir kurulum acilista hata verir. Diger kisisel uygulamalar ayni sunucuda kendi veritabanini alir; Kubernetes kurulumu silinip yeniden kurulsa da yerel veri kalir.
- **Negative / kabul edilen sinirlar:** SQLite yolu yalniz hostta `DEBUG=True` ile kalir ve CI'da test edilmez. `jsonb` nesne anahtar sirasini korumaz (`by_provider` admin'de farkli sirada gorunebilir). CyberNews compose artik `yerel-platform`'un ayakta olmasina baglidir. Ayni veritabanina iki kurulum (compose + Kubernetes) ayni anda baglanmamalidir; Kubernetes icin ayri veritabani (`cybernews_k8s`) acilir. Geri donus ters yonde dump/yukleme gerektirir (prova edildi).
