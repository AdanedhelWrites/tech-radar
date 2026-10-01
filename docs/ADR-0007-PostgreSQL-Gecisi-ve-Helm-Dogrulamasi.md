# ADR 0007: PostgreSQL Gecisi ve Helm Dogrulamasi (Faz B)

## Status
Accepted — 2026-10-01. **B1 (PostgreSQL) uygulandi** (canli gecis 2026-10-02 02:10-02:15, merge commit `a492d38`). B2 (Helm dogrulamasi) acik.

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

## Consequences
- **Positive:** Yazma kilidi kalkar; worker ve api eszamanli yazabilir. v1 imleci gecisten etkilenmedi (delta ozeti ayni). Env'i eksik bir kurulum acilista hata verir. Diger kisisel uygulamalar ayni sunucuda kendi veritabanini alir; Kubernetes kurulumu silinip yeniden kurulsa da yerel veri kalir.
- **Negative / kabul edilen sinirlar:** SQLite yolu yalniz hostta `DEBUG=True` ile kalir ve CI'da test edilmez. `jsonb` nesne anahtar sirasini korumaz (`by_provider` admin'de farkli sirada gorunebilir). CyberNews compose artik `yerel-platform`'un ayakta olmasina baglidir. Ayni veritabanina iki kurulum (compose + Kubernetes) ayni anda baglanmamalidir; Kubernetes icin ayri veritabani (`cybernews_k8s`) acilir. Geri donus ters yonde dump/yukleme gerektirir (prova edildi).
