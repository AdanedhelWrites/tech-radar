# Teknoloji Radar

Siber guvenlik haberleri, CVE zafiyetleri, Kubernetes ekosistemi, SRE (Site Reliability Engineering) haberleri, DevTools altyapi araclari guncellemeleri ve yapay zeka (AI) gelismelerini **35 farkli kaynaktan** toplayan, Turkceye ceviren ve modern bir arayuzde sunan full-stack haber agregasyon uygulamasi.

> Bu proje **Vibe Coding** yaklasimiyla, Claude Code (claude-opus-4-6) ile birlikte gelistirilmistir.

---

## Mimari

```
                         ┌──────────────────┐
                         │   React Frontend │
                         │   (Vite + BS5)   │
                         │   :3000          │
                         └────────┬─────────┘
                                  │ /api proxy
                         ┌────────▼─────────┐
                         │  Django REST API  │
                         │  (Gunicorn)       │
                         │  :8000            │
                         └──┬──────────┬────┘
                            │          │
                   ┌────────▼──┐  ┌────▼────────────┐
                   │   Redis   │  │  Celery Worker   │
                   │   :6379   │  │  + Beat Scheduler│
                   └───────────┘  └─────────────────┘
                                          │
                              ┌───────────▼───────────┐
                               │   Harici Kaynaklar     │
                               │   (35 kaynak)          │
                              │   + LibreTranslate      │
                              └─────────────────────────┘
```

## Ozellikler

- **35 farkli kaynak** — 5 siber guvenlik, 5 CVE, 3 Kubernetes, 5 SRE, 9 DevTools, 8 Yapay Zeka
- **Asenkron cekim** — "Getir" istegi Celery worker'a devredilir; arayuz 5 saniyede bir yeni kayitlari otomatik yansitir
- **Periyodik cekim** — Celery Beat tum bolumleri 6 saatte bir otomatik gunceller (sadece yeni kayitlar cevrilir)
- **Yonetici korumali sifirlama** — Veritabanini silen `clear` endpoint'leri yalnizca Django admin oturumuyla calisir
- **Tam makale cevirisi** — Kisaltma yok, tum icerik Turkceye cevrilir
- **Teknik terim korumasi** — 130+ terim (Kubernetes, Docker, Elasticsearch, CVE, CVSS, vb.) ceviri sirasinda bozulmaz
- **Turkce imla post-processing** — Cumle basi buyuk harf, noktalama duzeltme, URL/surum koruma
- **Parca tabanli ceviri** — Uzun makaleler cumle sinirlarindan 4500 karakterlik parcalara bolunerek cevrilir
- **Karanlik mod** — Koyu tonlarda arayuz (steel blue `#5b86a7` vurgu rengi)
- **DevTools takibi** — MinIO, Seq, Ceph, MongoDB, PostgreSQL, RabbitMQ, Elasticsearch+Kibana, Redis, Moodle release guncellemeleri
- **Tarih filtresi** — 1-15 gun (haberler) / 1-60 gun (DevTools, Yapay Zeka) slider ile filtreleme
- **CVSS siddet filtresi** — Kritik / Yuksek / Orta / Dusuk (CVE sayfasi)
- **HTML rapor disa aktarma** — Her bolumden koyu temali, yazdirilabilir HTML rapor indirilebilir
- **Docker Compose** — Tek komutla 5 container ayaga kalkar
- **Kubernetes** — Production-ready manifest'ler + Helm chart

---

## Veri Kaynaklari

### Siber Guvenlik Haberleri (5 kaynak)

| Kaynak | Yontem | Aciklama |
|--------|--------|----------|
| The Hacker News | HTML Scraping | Tam makale icerigi cekilir |
| Bleeping Computer | HTML Scraping | Sponsorlu icerik filtrelenir |
| SecurityWeek | HTML Scraping | Guvenlik odakli haberler |
| Dark Reading | RSS Feed | HTML 403 dondugu icin RSS kullanilir |
| Krebs on Security | HTML Scraping | Brian Krebs'in guvenlik blogu |

### CVE Zafiyetleri (5 kaynak)

| Kaynak | Yontem | Aciklama |
|--------|--------|----------|
| NVD (Yayinlanan) | REST API | Yeni yayinlanan CVE'ler |
| NVD (Guncel) | REST API | Son guncellenen CVE'ler |
| GitHub Advisory | REST API | CVSS, CWE, etkilenen paketler dahil |
| Tenable | HTML Scraping | Severity bilgisi dahil |
| CIRCL | REST API | Luksemburg CERT |

### Kubernetes (3 kaynak)

| Kaynak | Yontem | Aciklama |
|--------|--------|----------|
| Kubernetes Blog | HTML Scraping | Resmi Kubernetes blog yazilari |
| Kubernetes GitHub | REST API | Release notlari, CHANGELOG formatinda |
| CNCF Blog | WordPress API | Cloud Native Computing Foundation haberleri |

### SRE (5 kaynak)

| Kaynak | Yontem | Aciklama |
|--------|--------|----------|
| SRE Weekly | RSS Feed | Haftalik bulten, bireysel makalelere ayristirilir |
| InfoQ SRE | HTML Scraping | SRE etiketli makaleler |
| PagerDuty Eng | RSS Feed | Incident management ve SRE makaleleri |
| Google Cloud SRE | RSS Feed | SRE anahtar kelime filtresiyle |
| DZone DevOps | RSS Feed | SRE/DevOps konulu makaleler |

### DevTools — Altyapi Araclari (9 kaynak)

| Kaynak | Yontem | Aciklama |
|--------|--------|----------|
| MinIO | GitHub Releases API | S3 uyumlu object storage, detayli changelog |
| Seq | Datalust Blog RSS | Yapilandirilmis log arama motoru, release filtreli |
| Ceph | GitHub Releases Atom | Dagitik storage, version tag tabanli |
| MongoDB | Blog RSS | Release ve guncelleme filtreli blog yazilari |
| PostgreSQL | Resmi News RSS | Resmi haberler, release notlari, ekosistem |
| RabbitMQ | GitHub Releases API | Mesaj kuyrugu, tam changelog |
| Elasticsearch + Kibana | GitHub Releases API + elastic.co release notes | Resmi release notes sayfasindan detayli changelog |
| Redis | Blog RSS + tam makale | Blog sayfasindan tam icerik cekilir (blockContent) |
| Moodle | GitHub Tags API + moodledev.io | Resmi release notes sayfasindan gercek icerik |

### Yapay Zeka (8 kaynak)

| Kaynak | Yontem | Aciklama |
|--------|--------|----------|
| Hugging Face | RSS Feed | Model, dataset ve kutuphane duyurulari |
| MIT Tech Review AI | RSS Feed | Tam makale icerigi RSS icinde gelir |
| MarkTechPost | RSS Feed | Arastirma ve model haberleri |
| AWS ML Blog | RSS Feed | AWS makine ogrenmesi blogu |
| TechCrunch AI | RSS Feed | AI sektor haberleri |
| Google DeepMind | RSS Feed | DeepMind arastirma blogu |
| KDnuggets | RSS Feed | Veri bilimi ve ML yazilari |
| OpenAI Blog | RSS Feed | OpenAI duyurulari |

> Tum AI kaynaklari `news/base_scraper.py` icindeki ortak `BaseRSSScraper` ile okunur; RSS aciklamasi 200 karakterden kisaysa makale sayfasindan paragraf cekilir. Benchmark/leaderboard skorlari kapsam disidir (bkz. [ADR-0002](docs/ADR-0002-AI-Benchmark.md)).

---

## Teknoloji Yigini

| Katman | Teknolojiler |
|--------|-------------|
| **Backend** | Python 3.11, Django 4.2, Django REST Framework 3.14, Celery 5.3, Gunicorn |
| **Frontend** | React 18, Vite 5, React Bootstrap 2.9, React Router DOM 6, Axios |
| **Veri** | PostgreSQL 16 (compose ve K8s; SQLite yalniz `DEBUG=True` ile hostta), Redis 7 (cache + broker) |
| **Scraping** | BeautifulSoup4, lxml, Requests |
| **Ceviri** | Cekim aninda yerel LibreTranslate (aninda Turkce, rozetli); retranslate 2 saatte bir bekleyen ve LibreTranslate kayitlarini Gemini API (gemini-3.5-flash-lite, ucretsiz katman, kayit basina tek istek) ile yukseltir + merkezi post-processing |
| **Altyapi** | Docker Compose, Kubernetes, Nginx 1.25, Whitenoise |

---

## Kurulum (Docker Compose)

### Gereksinimler

- Docker ve Docker Compose
- Internet baglantisi (kaynak sitelere ve Gemini API'ye erisim icin; LibreTranslate yerel container'da calisir)
- Paylasilan yerel PostgreSQL (`yerel-platform` reposu) ayakta ve `cybernews` veritabani olusturulmus

### Hizli Baslangic

`.env.example`'i `.env` olarak kopyalayin. `SECRET_KEY` (`openssl rand -hex 32`) ve `DB_PASSWORD` (yerel-platform'daki `cybernews` kullanicisinin parolasi) zorunludur; `GEMINI_API_KEY` istege baglidir (bos birakilirsa Gemini hic denenmez, sistem LibreTranslate ile calisir). Veritabani ayri `yerel-platform` reposundaki paylasilan PostgreSQL'dir; compose'dan once orada `docker compose up -d` calismis olmalidir:

```bash
git clone https://github.com/AdanedhelWrites/tech-radar.git
cd tech-radar/cybersecurity_news

cp .env.example .env
docker compose up -d --build
```

| Servis | URL |
|--------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/api/ |

### Container'lar

| Container | Image | Port | Gorev |
|-----------|-------|------|-------|
| `teknoloji-api` | `teknoloji-haberleri-api:latest` | 8000 | Django REST API, scraping, ceviri |
| `teknoloji-frontend` | `node:18-alpine` | 3000 | React arayuz (Vite dev server, hot-reload) |
| `teknoloji-redis` | `redis:7-alpine` | 6379 | Cache + Celery message broker |
| `yerel-postgres` (ayri repo: `yerel-platform`) | `postgres:16.15-alpine` | 127.0.0.1:5432 | Paylasilan yerel PostgreSQL; CyberNews `cybernews` veritabanini ve kullanicisini kullanir |
| `teknoloji-worker` | `teknoloji-haberleri-api:latest` | — | Arka plan scraping + ceviri |
| `teknoloji-scheduler` | `teknoloji-haberleri-api:latest` | — | Periyodik gorev zamanlayici (Celery Beat) |

Container'lar `teknoloji-network` bridge network uzerinden haberlesir.

### Yonetim Komutlari

```bash
# Baslat
docker compose up -d --build

# Durdur
docker compose down

# Loglari izle
docker compose logs -f teknoloji-api
docker compose logs -f teknoloji-worker

# Redis cache temizle
docker compose exec teknoloji-redis redis-cli FLUSHDB

# PostgreSQL shell
docker exec -it yerel-postgres psql -U cybernews -d cybernews

# Django shell
docker compose exec teknoloji-api python manage.py shell

# Sifirdan baslat (volume'lar dahil)
docker compose down -v && docker compose up -d --build
```

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

### Yonetici Hesabi

"Sifirla" butonlari (`POST /api/{bolum}/clear/`) veritabanini sildigi icin yalnizca Django admin yetkisiyle calisir; oturum yoksa 403 doner. Ilk kurulumda bir yonetici olusturun:

```bash
docker compose exec teknoloji-api python manage.py createsuperuser
```

Ardindan `http://localhost:8000/admin/` adresinden giris yapin. Oturum cerezi ayni tarayicidaki frontend isteklerinde de kullanilir; axios CSRF token'i `csrftoken` cerezinden otomatik ekler.

---

## Kullanim

Her sayfa ayni duzeni takip eder:

1. Sol panelden **gun araligini** (1-15 / DevTools ve Yapay Zeka icin 1-60) ve **kaynaklari** secin
2. **"Getir"** butonuna tiklayin
3. Cekim arka planda (Celery worker) baslar; cevrilen haberler orta panele birkac saniye icinde otomatik duser
4. Bir habere tiklayarak sag panelde detayini goruntuleyin

**Ek butonlar:**
- **Yenile** — Mevcut verileri yeniden yukler
- **Sifirla** — Tum verileri temizler (yonetici girisi gerekir, bkz. [Yonetici Hesabi](#yonetici-hesabi))
- **Indir** — Koyu temali HTML rapor olarak disa aktarir

---

## API Endpoints

Her bolum (news, cve, k8s, sre, devtools, ai) ayni endpoint yapisini kullanir:

| Method | Endpoint Deseni | Aciklama |
|--------|-----------------|----------|
| GET | `/api/{bolum}/` | Kayitli verileri listele |
| POST | `/api/{bolum}/fetch/` | Arka planda cekim baslat — Celery task (body: `{"days": 7, "sources": [...]}`) |
| POST | `/api/{bolum}/clear/` | Tum verileri sil (**yonetici oturumu gerekir**, aksi halde 403) |
| GET | `/api/{bolum}/stats/` | Istatistikleri getir |
| GET | `/api/{bolum}/export/` | HTML rapor olarak disa aktar |

**Bolum isimleri:** `news` (Siber Guvenlik, fetch endpoint: `/api/fetch/`), `cve`, `k8s`, `sre`, `devtools`, `ai`

> **Not:** Siber guvenlik bolumunun fetch, clear, stats ve export endpoint'leri `/api/news/` altinda degil, dogrudan `/api/` altindadir: `/api/fetch/`, `/api/clear/`, `/api/stats/`, `/api/export/`

---

## Entegrasyon API (`/api/v1/`)

Yukaridaki `/api/*` uc noktalari React arayuzune hizmet eder. **Dis tuketici uygulamalar `/api/v1/` kullanmalidir:** token ister, cache'e hic bakmaz, imlecli delta ile hicbir kaydi atlamadan ve tekrar islemeden senkron yapilmasini saglar. Karar gerekcesi icin [ADR-0003](docs/ADR-0003-Entegrasyon-API-v1.md).

Calisan ornek: [`scripts/ornek_istemci.py`](scripts/ornek_istemci.py) — alti bolumu bastan sona ceker, imleci diske yazar, yalnizca standart kutuphane kullanir.

### Token alma

Token'lar Django admin'den uretilir ve iptal edilir:

```bash
# Kullanici olustur (yoksa) ve token uret
docker compose exec teknoloji-api python manage.py shell -c "
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
u, _ = User.objects.get_or_create(username='entegrasyon')
print(Token.objects.get_or_create(user=u)[0].key)
"
```

Her istekte `Authorization: Token <key>` basligi gonderilir. Admin arayuzunde **Auth Token → Tokens** ekranindan da uretilebilir ve iptal edilebilir.

### Uc noktalar

| Method | Uc nokta | Aciklama |
|--------|----------|----------|
| GET | `/api/v1/schema/` | OpenAPI 3 semasi (token gerekir) |
| GET | `/api/v1/docs/` | Swagger UI — tarayicida admin oturumuyla acilir |
| GET | `/api/v1/health/` | Servis ayakta mi — **tokensiz** (Kubernetes probe'lari icin) |
| GET | `/api/v1/status/` | Bolum basina veri tazeligi: `last_success_at`, `last_status`, `last_fetched_count`, `last_saved_count`, `pending_translation`, `total` |
| GET | `/api/v1/{bolum}/` | Imlecli delta okuma |
| POST | `/api/v1/{bolum}/refresh/` | Tek bolum icin manuel cekim tetikler |
| POST | `/api/v1/refresh/` | Alti bolumu birden tetikler |
| GET | `/api/v1/jobs/{job_id}/` | Manuel tetiklenen isin durumu |

**Bolum isimleri:** `news`, `cve`, `kubernetes`, `sre`, `devtools`, `ai` — dikkat: v1'de `k8s` degil **`kubernetes`**.

### Delta dongusu

```bash
curl -H "Authorization: Token $CYBERNEWS_TOKEN" \
  "http://localhost:8000/api/v1/cve/?limit=200&min_severity=high"
```

Yanit zarfi:

```json
{
  "results": [ ... ],
  "next_cursor": "eyJ1IjoiMjAyNi0wOS0yMFQyMjowODo1Mi43MDE4MzErMDA6MDAiLCJpIjoxMDM2NX0",
  "has_more": true,
  "count": 200
}
```

Dongu: `next_cursor`'i sakla, bir sonraki istekte `?since_cursor=<deger>` olarak gonder, `has_more` `false` olana kadar tekrarla. **Imlec opaktir** — `(updated_at, id)` ikilisinin kodlanmis halidir, ic bicimi haber verilmeden degisebilir; acma, yalnizca sakla ve geri gonder. `next_cursor` bos sonucta bile doner ki saklayacak bir degerin hep olsun. Siralama her zaman `updated_at ASC, id ASC`'dir; bu **akis sirasidir, ekrana basma sirasi degildir**.

Ilk senkronda tum kayitlar yeni gorunur. Daraltmak icin `?since=YYYY-MM-DD` kullanilabilir (yalnizca imlec yokken gecerlidir).

| Parametre | Bolumler | Aciklama |
|-----------|----------|----------|
| `since_cursor` | hepsi | Opak imlec; verildiginde `since` yok sayilir |
| `since` | hepsi | `YYYY-MM-DD` — ilk senkronu daraltmak icin |
| `limit` | hepsi | Varsayilan 100, tavan 500 |
| `source` | hepsi | Virgulle ayrilmis kaynak adlari |
| `needs_translation` | hepsi | `true` / `false` — cevirisi bekleyenler |
| `min_severity` | `cve` | `low` \| `medium` \| `high` \| `critical` — esik ve uzeri |
| `severity` | `cve` | Virgulle ayrilmis tam eslesme (`critical,high`) |
| `category` | `kubernetes` | Virgulle ayrilmis kategori |
| `entry_type` | `devtools` | Virgulle ayrilmis tur |

Gecersiz parametre sessizce yok sayilmaz; `400 invalid_parameter` doner.

### Upsert anahtari — `id` kullanmayin

**Tuketici tarafi upsert (idempotent) olmalidir; salt insert cift kayit uretir.** `updated_at` icerik degismese de ilerleyebilir, yani ayni kayit akista birden fazla kez gorunur.

Birlestirme anahtari olarak **`id` kullanilmamalidir.** `id` kalici degildir: saklama penceresi (`RETENTION_DAYS`) disina dusen bir kayit silinir ve kaynak onu tekrar dondurdugunde **yeni bir `id` ile** geri gelir. Kararli anahtarlar:

| Bolum | Upsert anahtari |
|-------|-----------------|
| `cve` | **`cve_id`** |
| `news`, `kubernetes`, `sre`, `devtools`, `ai` | **`link`** |

Bunlar yazma yolunun da anahtarlaridir: `news/tasks.py` ayni alanlarla `update_or_create` yapar. Gerekce ve olcumler icin [ADR-0005](docs/ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md).

> **Uyari:** Bes bolumden dordunde (`kubernetes`, `sre`, `devtools`, `ai`) `link` veritabaninda `unique=True`, `cve` icin `cve_id` de oyle. **`news` bolumunde `link` uzerinde benzersizlik kisiti yoktur** — anahtar yazma yolunun sozlesmesidir, sema garantisi degildir. Tuketici kendi tarafinda benzersiz indeks tanimlamalidir.

Silmeler akista bildirilmez (tombstone yok); tuketici kendi saklama suresini uygular.

### Dil alanlari

Baslik ve aciklama ic ice doner ve severity normalize edilir:

```json
{
  "title":    { "original": "Critical RCE in ...", "tr": "... kritik RCE" },
  "severity": { "code": "critical", "label": "Kritik" },
  "needs_translation": false,
  "translation_provider": "gemini"
}
```

Tuketici `title.tr || title.original` yazarak cevirisi henuz hazir olmayan kayitta Ingilizceye duser — kayit kaybolmaz, Turkcesi hazir olunca `updated_at` ilerledigi icin ayni anahtar uzerine guncelleme gelir. Filtreler severity'nin **`code`** degeri uzerinden calisir.

### Manuel tetikleme

```bash
curl -X POST -H "Authorization: Token $CYBERNEWS_TOKEN" \
  http://localhost:8000/api/v1/cve/refresh/
```

`202` ile `{"job_id", "section", "status", "status_url"}` doner; durum `/api/v1/jobs/{job_id}/` ile izlenir. Uc katman korur: bolum kilidi (`REFRESH_LOCK_TTL`) cift kazimayi onler, **paylasilan** bolum sogumasi (`REFRESH_COOLDOWN`) kaynak siteleri ve ceviri kotasini korur, token basina hiz siniri tek istemciyi sinirlar. Sogumadaki bolum `429 cooldown` ve `Retry-After` basligi dondurur. Toplu `/api/v1/refresh/` her zaman `202` doner; govdede `started` / `already_running` / `skipped` listeleri bulunur.

### Hiz sinirlari

| Kapsam | Oran |
|--------|------|
| Okuma (`v1_read`) | token basina `120/dk` |
| Tetikleme (`v1_refresh`) | token basina `12/saat` |
| Bolum sogumasi | `REFRESH_COOLDOWN` (900 sn) — **tum token'lar arasinda paylasilir** |

### Hata sozlesmesi

Tum v1 hatalari ayni bicimde doner:

```json
{ "error": { "code": "invalid_cursor", "message": "Imlec cozulemedi: ..." } }
```

| Kod | HTTP | Ne zaman |
|-----|------|----------|
| `unauthorized` | 401 | Token yok, gecersiz veya iptal edilmis |
| `invalid_cursor` | 400 | `since_cursor` cozulemedi |
| `invalid_parameter` | 400 | Parametre bicimi veya degeri gecersiz |
| `not_found` | 404 | `refresh/` icin bilinmeyen bolum; bilinmeyen veya suresi dolmus `job_id` |
| `throttled` | 429 | Hiz siniri asildi |
| `cooldown` | 429 | Bolum sogumada (`Retry-After` basligi ile) |
| `internal` | 500 | Beklenmeyen sunucu hatasi |

> **Not:** Bu sozlesme yalnizca **tanimli** uc noktalar icin gecerlidir. Hic rotasi olmayan bir yol — ornegin `GET /api/v1/k8s/`, cunku v1'de bolum adi `kubernetes`'tir — DRF'e hic ulasmadan Django'nun duz **HTML 404**'unu dondurur, JSON gelmez. Tuketici yanit govdesini ayristirmadan once `Content-Type`'i kontrol etmelidir. Buna karsilik `POST /api/v1/k8s/refresh/` rotalidir ve duzgun `{"error": {"code": "not_found", ...}}` dondurur.

### Makine tarafindan okunur sozlesme

`/api/v1/schema/` OpenAPI 3 dokumani dondurur ve yalnizca `/api/v1/` uclarini
kapsar; eski `/api/*` uclari bilincli olarak disaridadir.

```bash
curl -H "Authorization: Token $CYBERNEWS_TOKEN" \
  http://localhost:8000/api/v1/schema/ -o cybernews-v1.yaml
```

Semadan istemci uretilebilir (`openapi-generator` vb.). `/api/v1/docs/` ayni
semayi Swagger UI ile gosterir; tarayici `Authorization` basligi gondermedigi
icin bu sayfa **admin'de oturum acmis** bir kullaniciyla acilir.

> **Not:** Sema yayimlandigi andan itibaren dis sozlesmedir. Bir alanin tipi
> degisirse bu artik "dokumantasyon hatasi" degil, tuketicinin istemcisini
> kiran bir degisikliktir.

---

## Proje Yapisi

```
cybersecurity_news/
├── cybernews/                  # Django proje ayarlari
│   ├── settings.py             # Env-var tabanli config (DB, Redis, CORS)
│   ├── urls.py                 # Root URL yapilandirmasi
│   ├── celery.py               # Celery yapilandirmasi
│   └── wsgi.py
│
├── news/                       # Ana Django uygulamasi
│   ├── models.py               # NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry
│   ├── views.py                # API endpoint'leri (6 bolum x 5 endpoint = 30)
│   ├── tasks.py                # Celery task'lari (cekim + ceviri + cache)
│   ├── serializers.py          # DRF serializer'lari
│   ├── urls.py                 # API URL pattern'leri
│   ├── translation_utils.py    # Merkezi ceviri modulu (terim koruma + post-processing)
│   ├── base_scraper.py         # Ortak RSS okuyucu (BaseRSSScraper)
│   ├── ai_scraper.py           # 8 Yapay Zeka kaynagi scraper'i
│   ├── cve_scraper.py          # 5 CVE kaynagi scraper'i
│   ├── k8s_scraper.py          # 3 Kubernetes kaynagi scraper'i
│   ├── sre_scraper.py          # 5 SRE kaynagi scraper'i
│   ├── devtools_scraper.py     # 9 DevTools kaynagi scraper'i
│   ├── fetch_runs.py           # FetchRun satirlarini yazan Celery sinyalleri
│   ├── api_v1/                 # Dis tuketici entegrasyon katmani (ADR-0003)
│   │   ├── views.py            # Delta, refresh, jobs, status, health uc noktalari
│   │   ├── serializers.py      # v1 serializer'lari (alanlar tek tek yazilir)
│   │   ├── cursor.py           # (updated_at, id) keyset imleci
│   │   ├── filters.py          # Query parametresi ayristirma
│   │   └── refresh.py          # Bolum kilidi, soguma, job kaydi
│   └── admin.py                # Django admin kayitlari
│
├── scripts/
│   └── ornek_istemci.py        # /api/v1/ delta senkron ornegi (stdlib-only)
│
├── scraper_multi.py            # 5 siber guvenlik kaynagi scraper'i
│
├── frontend/                   # React SPA
│   ├── src/
│   │   ├── App.jsx             # Router, Navbar, Karanlik Mod
│   │   ├── App.css             # Tema stilleri
│   │   ├── components/
│   │   │   ├── NewsComponent.jsx       # Siber guvenlik sayfasi
│   │   │   ├── CVEComponent.jsx        # CVE sayfasi
│   │   │   ├── KubernetesComponent.jsx # Kubernetes sayfasi
│   │   │   ├── SREComponent.jsx        # SRE sayfasi
│   │   │   ├── DevToolsComponent.jsx   # DevTools sayfasi
│   │   │   └── AINewsComponent.jsx     # Yapay Zeka sayfasi
│   │   └── services/
│   │       └── api.js          # Axios API servisleri
│   ├── Dockerfile              # Production build: Node + Nginx
│   ├── nginx.conf              # SPA routing + /api proxy
│   ├── vite.config.js          # Dev proxy ayarlari
│   ├── index.html
│   └── package.json
│
├── docs/                       # Mimari karar kayitlari (ADR)
│
├── helm/tech-radar/            # Helm chart (tek dagitim kaynagi; surum: Chart.yaml)
│   ├── Chart.yaml              # version (SemVer) + appVersion (imaj etiketi)
│   ├── CHANGELOG.md            # Chart surumleri ve yukseltme notlari
│   ├── values.yaml             # Varsayilan degerler (gizli deger icermez)
│   ├── ci/yerel-values.yaml    # Yerel docker-desktop dogrulamasi
│   ├── .helmignore
│   └── templates/
│       ├── _helpers.tpl        # Imaj, guvenlik baglami, ortam, ALLOWED_HOSTS yardimcilari
│       ├── configmap.yaml
│       ├── secret.yaml         # secretKey ve dbPassword zorunlu
│       ├── postgresql.yaml     # postgresql.enabled
│       ├── redis.yaml          # redis.enabled
│       ├── libretranslate.yaml # libretranslate.enabled
│       ├── backend.yaml
│       ├── frontend.yaml
│       ├── celery.yaml         # Worker + Beat
│       ├── migration-job.yaml  # Her revizyonda teknoloji-migrate-r<N>
│       ├── ingress.yaml        # ingress.enabled
│       └── NOTES.txt
│
├── docker-compose.yml          # 6 servis (PostgreSQL ayri: yerel-platform)
├── Dockerfile                  # Backend multi-stage build
├── entrypoint.sh               # Startup: wait-for-db + migrate
├── requirements.txt            # Python bagimliliklari
├── .gitignore
├── .dockerignore
└── manage.py
```

---

## Ceviri Sistemi

Tum scraper'lar `news/translation_utils.py` merkezi modulunu kullanir. 3 katmanli mimari:

### 1. Teknik Terim Korumasi

Ceviri oncesinde 130+ teknik terim `XTRM####X` formatiyla placeholder'lara donusturulur. Ceviri sonrasi geri yerlestirilir. Ek olarak:

- **URL'ler** (`https://...`) otomatik korunur
- **Surum numaralari** (`v1.2.3`, `9.3.1`) otomatik korunur
- **CVE numaralari** (`CVE-2024-12345`) otomatik korunur
- **Backtick kod parcalari** (`` `kubectl get pods` ``) otomatik korunur
- **SIG etiketleri** (`[SIG Node]`) otomatik korunur
- **GitHub URL'leri** ve paket isimleri otomatik korunur

Terimler uzunluktan kisaya siralanarak islenir — kisa terimlerin kelime icinde eslesmesin onlenir.

### 2. Parca Tabanli Ceviri

Uzun metinler cumle sinirlarindan 4500 karakterlik parcalara bolunur (saglayici istek boyutu sinirlarini asmamak icin). Her parca icin ayri terim koruma uygulanir. LibreTranslate bu parcalari kendi icinde ayrica 160 karakterlik alt parcalara boler (`LIBRETRANSLATE_CHUNK_CHARS`); Gemini yukseltmesi kayit basina tek istekte calisir.

### 3. Turkce Post-Processing

Ceviri sonrasi otomatik duzeltmeler:

- Cumle basi ve satir basi buyuk harf
- Noktalama duzeltmeleri (noktadan sonra bosluk, parantez temizligi)
- URL/email/dosya uzantisi korumasi (post-processing'in `.co` -> `. Co` yapmasi engellenir)
- Ingilizce ay isimlerinin Turkceyecevirisi
- Bozuk Turkce karakter encoding duzeltmesi
- K8s kisaltmasinin korunmasi

### 4. Hiz Siniri ve Devre Kesici

- **LibreTranslate (cekim aninda)** — Baglanti hatasi, zaman asimi veya 5xx gelirse kendi Redis devre kesicisi `LIBRETRANSLATE_COOLDOWN` (60 sn, varsayilan) boyunca acilir; 4xx devre kesiciyi acmaz. Yeniden deneme ve ayri bir hiz siniri yoktur, eszamanlilik compose CPU siniriyla dogal olarak sinirlanir.
- **Gemini (retranslate yukseltmesi)** — Istekler arasi en az `GEMINI_MIN_INTERVAL` saniye (Redis uzerinden tum worker'lar icin ortak), gunluk `GEMINI_DAILY_BUDGET` istek tavani, 429/5xx sonrasi `GEMINI_COOLDOWN` saniye devre kesici.
- **Kayip yok** — Hicbir saglayici cevirmezse haber tam Ingilizce metniyle kaydedilir ve `needs_translation=True` isaretlenir; sonraki cekimde veya `retranslate_pending` turunde otomatik olarak yeniden denenir.

### 5. Retranslate ve Gemini Yukseltme

`retranslate_pending` Celery Beat gorevi her 2 saatte bir (tek saatlerde, dakika 05) calisir ve iki isi yapar: bekleyen (`needs_translation=True`) kayitlari LibreTranslate ile cevirir, ardindan `translation_provider='libretranslate'` kayitlari Gemini API (`gemini-3.5-flash-lite`) ile kayit basina tek istekte yukseltir. Yukseltme bolum basina `RETRANSLATE_UPGRADE_BATCH` kayitla sinirlidir. Eski `google` etiketli kayitlar yukseltilmez, etiketli kalir.

**Anahtar alma:** Google AI Studio (aistudio.google.com) → Get API key → Create API key; `cybersecurity_news/.env` icine `GEMINI_API_KEY=...` (gitignore'da). Kart gerekmez; kota asilirsa 429 doner, sistem LibreTranslate ile surer.

**Rozetler:** Her kayit `translation_provider` tasir; arayuzde `Makine çevirisi: LibreTranslate` (sari), `Çeviri: Gemini`, `Çeviri: Google` (eski kayitlar).

---

## Periyodik Cekim (Celery Beat)

`teknoloji-scheduler` container'i, `cybernews/settings.py` icindeki `CELERY_BEAT_SCHEDULE` ile tum bolumleri **6 saatte bir** (Europe/Istanbul 00:00, 06:00, 12:00, 18:00) otomatik gunceller. Worker ve ceviri yukunu dagitmak icin bolumler 10 dakika arayla kaydirilir:

| Bolum | Task | Dakika | Gun araligi |
|-------|------|--------|-------------|
| Siber Guvenlik | `fetch_news_task` | :00 | 7 |
| CVE | `fetch_cve_task` | :10 | 7 |
| Kubernetes | `fetch_k8s_task` | :20 | 30 |
| SRE | `fetch_sre_task` | :30 | 30 |
| DevTools | `fetch_devtools_task` | :40 | 30 |
| Yapay Zeka | `fetch_ai_news_task` | :50 | 30 |

Tum cekimler (manuel "Getir" dahil) `skip_existing=True` ile calisir: veritabaninda zaten cevrilmis kayitlar tekrar cevrilmez; yalnizca yeni haberler ve ceviri bekleyen (`needs_translation`) kayitlar LibreTranslate'e gonderilir. Gun araligi task varsayilanidir; her cekim (manuel "Getir" dahil) bu araligin disinda kalan eski kayitlari siler. Bekleyen ve LibreTranslate kayitlarinin Gemini ile yukseltilmesi ayri bir Beat gorevidir (bkz. [Retranslate ve Gemini Yukseltme](#5-retranslate-ve-gemini-yukseltme)).

---

## Kubernetes'e Deploy Etme (Helm)

Tek dagitim kaynagi `helm/tech-radar/` chart'idir; ham manifest isteyen `helm template` ciktisini kullanir. Chart surumu `Chart.yaml`'dadir ve SemVer'e uyar (uyumsuz degisiklik MAJOR, yeni istege bagli deger MINOR, duzeltme PATCH); her surumun degisiklikleri ve yukseltme notlari [`helm/tech-radar/CHANGELOG.md`](helm/tech-radar/CHANGELOG.md)'dedir ve CI bunu zorlar. `appVersion` uygulama imajinin etiketidir. Kararlar: [ADR-0007](docs/ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md).

> **Guvenlik:** Asagidaki komutlar sablondur; `<...>` alanlarini kendi ortaminizla doldurun ve **her komutta hedef baglami acikca verin** (`--kube-context` / `--context`). Aktif `kubectl` baglamina guvenmeyin. Gizli degerleri values dosyasina yazmayin.

### On gereksinimler

- Kubernetes kumesi, `kubectl` ve Helm 3
- Kumenin cekebilecegi bir registry'de backend ve frontend imajlari
- Ingress kullanilacaksa bir Ingress Controller (`ingress.className`, varsayilan `nginx`)

### Imajlar

```bash
docker build -t <registry>/teknoloji-haberleri-api:<surum> .
docker build -t <registry>/teknoloji-haberleri-frontend:<surum> ./frontend
docker push <registry>/teknoloji-haberleri-api:<surum>
docker push <registry>/teknoloji-haberleri-frontend:<surum>
```

`image.tag` verilmezse chart `appVersion`'i kullanir.

### Kurulum

```bash
helm upgrade --install tech-radar ./helm/tech-radar \
  --kube-context <hedef-baglam> -n <namespace> --create-namespace \
  --set secrets.secretKey="<openssl rand -hex 32>" \
  --set secrets.dbPassword="<guclu-sifre>" \
  --set ingress.host=<alan-adi> \
  --set backend.image.repository=<registry>/teknoloji-haberleri-api \
  --set backend.image.tag=<surum> \
  --set frontend.image.repository=<registry>/teknoloji-haberleri-frontend \
  --set frontend.image.tag=<surum> \
  --wait --wait-for-jobs --timeout 15m
```

`secrets.secretKey` ve `secrets.dbPassword` zorunludur (bos birakilirsa render reddedilir); PostgreSQL ve uygulama ayni `dbPassword`'u kullanir. `secrets.geminiApiKey` istege baglidir. Uretimde harici secret yonetimi (external-secrets, sealed-secrets, vault) tercih edin: Secret'i chart disinda yonetiyorsaniz `secrets.existingSecret=<ad>` verin; chart Secret olusturmaz, `secrets.*` zorunlu olmaz. Secret `SECRET_KEY`, `DB_USER`, `DB_PASSWORD`, `GEMINI_API_KEY` anahtarlarini icermelidir.

### Nasil calisir

- `migration.mode=helm` (varsayilan): her revizyonda `teknoloji-migrate-r<revizyon>` Job'u migration'lari uygular. `migration.mode=argocd`: Argo CD `helm template` kullandigi icin Job sabit adli (`teknoloji-migrate`) bir Sync hook'udur ve her senkronda yeniden olusturulur. Iki modda da api, worker ve scheduler `migrasyon-bekle` initContainer'inda `migrate --check` gecene kadar bekler. Geri alma sema geri almaz.
- Backend probe'lari `/api/v1/health/`'e `Host: localhost` ile gider. `ALLOWED_HOSTS` sablonda kurulur: `localhost`, `teknoloji-api` (kume ici tuketici), ingress host'u ve `config.django.extraAllowedHosts`.
- Statik dosyalar imajdadir; pod'lar `RUN_STARTUP_TASKS=false` ile acilir ve kok dosya sistemi salt okunurdur.
- LibreTranslate (`libretranslate.enabled`) ilk acilista ~258 MB model indirir (internet gerekir); modeller PVC'de kalir.
- Redis `emptyDir` kullanir: pod yeniden baslarsa bolum kilitleri, soguma, cache ve kuyruk kaybolur; Beat bir sonraki slotta yeniden planlar.
- `backend.name` `frontend/nginx.conf`'a baglidir (`teknoloji-api`); degistirirseniz frontend imajini yeniden derleyin.

### Guncelleme, geri alma, kaldirma

```bash
helm upgrade tech-radar ./helm/tech-radar --kube-context <hedef-baglam> -n <namespace> --reuse-values \
  --set backend.image.tag=<yeni-surum> --set frontend.image.tag=<yeni-surum> --wait --wait-for-jobs
helm history tech-radar --kube-context <hedef-baglam> -n <namespace>
helm rollback tech-radar <revizyon> --kube-context <hedef-baglam> -n <namespace>
helm uninstall tech-radar --kube-context <hedef-baglam> -n <namespace>
kubectl --context <hedef-baglam> delete namespace <namespace>   # PVC'ler (veri) de silinir
```

Yeni bir chart surumune gecmeden once `CHANGELOG.md`'deki yukseltme notunu okuyun (ornek: 2.0.0'da `postgresPassword` ve `global.namespace` kalkti).

### Ham manifest

```bash
helm template tech-radar ./helm/tech-radar -n <namespace> \
  --set secrets.secretKey=<...> --set secrets.dbPassword=<...> > tech-radar.yaml
```

Ciktida secret degerleri acik metindir; commit etmeyin.

### Yerel dogrulama (Docker Desktop Kubernetes)

Chart yalniz yerel `docker-desktop` baglaminda gercek kurulumla dogrulanir (S1-S7: kurulum, HTTP, uctan uca cekim, upgrade, PostgreSQL kaliciligi, zorunlu degerler, sokum):

```bash
scripts/helm_yerel_dogrulama.sh imaj   # :fazb-yerel imajlari
scripts/helm_yerel_dogrulama.sh kur    # S1-S6
scripts/helm_yerel_dogrulama.sh sok    # S7
```

Betik baglami degistirmez, yerel olmayan bir kumeyi reddeder, gizli degerleri calisma aninda uretir ve `helm/tech-radar/ci/yerel-values.yaml`'i kullanir.

### GitOps ile kurulum (Argo CD + Vault, yerel)

Kisisel deneme ortami Argo CD ile git'ten kurulur (ADR-0008): chart bu reponun degismez
`chart-<surum>` etiketinden (or. `chart-2.1.0`), degerler ve Vault Secrets Operator nesneleri
private `yerel-gitops` reposundan okunur; platform `yerel-platform`'da Terraform ile kurulur.

- `migration.mode=argocd` ve `secrets.existingSecret=teknoloji-secret` kullanilir (bkz. tablo).
- Her chart surumu icin etiket: `git tag chart-<Chart.yaml version>` + push. CI (`chart etiketi`)
  etiketin `Chart.yaml` ile ayni oldugunu ve CHANGELOG girdisini dogrular.
- Kumede calisan surum `yerel-gitops`'taki `targetRevision`'dir; yukseltme ve geri alma orada
  commit/`git revert` ile yapilir.

### Onemli values parametreleri

| Parametre | Varsayilan | Aciklama |
|-----------|-----------|----------|
| `secrets.secretKey` | `""` | **Zorunlu.** `openssl rand -hex 32` |
| `secrets.dbPassword` | `""` | **Zorunlu.** PostgreSQL ve uygulamanin ortak parolasi |
| `secrets.geminiApiKey` | `""` | Istege bagli; bos -> Gemini kapali |
| `secrets.existingSecret` | `""` | Doluysa chart Secret olusturmaz, bu Secret'i kullanir (or. Vault Secrets Operator) |
| `migration.mode` | `helm` | `argocd`: Job sabit adli Argo CD Sync hook'u (`helm template` ile kurulum) |
| `backend.image.tag` / `frontend.image.tag` | `""` | Bos -> `appVersion` |
| `backend.replicas` / `frontend.replicas` | `2` | Replika sayisi |
| `postgresql.enabled` | `true` | `false` = harici PostgreSQL (`config.database.host`) |
| `postgresql.storage.size` | `5Gi` | PVC boyutu |
| `redis.enabled` | `true` | `false` = harici Redis (`config.redis.*`) |
| `libretranslate.enabled` | `true` | Yerel ceviri servisi |
| `ingress.enabled` / `ingress.host` | `true` / `teknoloji.example.com` | Ingress ve alan adi (ALLOWED_HOSTS'a girer) |
| `ingress.tls.enabled` | `false` | TLS/HTTPS |
| `config.django.extraAllowedHosts` | `""` | Ek host'lar (virgulle) |
| `config.app.*` | koddaki varsayilanlar | `RETENTION_DAYS`, `REFRESH_COOLDOWN`, `GEMINI_*`, `LIBRETRANSLATE_*` ... |

---

## Ortam Degiskenleri

Uygulama tamamen ortam degiskenleri ile yapilandirabilir. Docker Compose'da `docker-compose.yml` icinde, Kubernetes'te ConfigMap + Secret ile ayarlanir.

| Degisken | Varsayilan | Aciklama |
|----------|-----------|----------|
| `SECRET_KEY` | (yok) | Zorunlu (`DEBUG=False` iken). Bos, depodaki ornek degerler, `django-insecure` onekli veya 32 karakterden kisa anahtar uygulamayi acmaz. Compose `.env`'den okur. Uretmek icin `openssl rand -hex 32` |
| `DEBUG` | `False` | Django debug modu |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Virgulle ayrilmis izinli host listesi. Compose `localhost,127.0.0.1,teknoloji-api` verir. Helm chart'i bunu sablonda acik liste olarak kurar (probe'lar `Host: localhost` gonderir) |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,...` | Frontend origin'leri |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Admin oturumuyla POST yapabilecek frontend origin'leri (Vite proxy `changeOrigin` kullandigi icin gerekli) |
| `GEMINI_API_KEY` | (bos) | Google AI Studio anahtari; bos ise Gemini hic denenmez |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model |
| `GEMINI_DAILY_BUDGET` | `400` | Gunluk istek butcesi (Pasifik gunu; ucretsiz katman 500 RPD) |
| `GEMINI_MIN_INTERVAL` | `5` | Istekler arasi saniye (15 RPM'in altinda) |
| `GEMINI_COOLDOWN` | `600` | 429/5xx sonrasi bekleme (sn) |
| `GEMINI_TIMEOUT` | `60` | Istek zaman asimi (sn) |
| `GEMINI_MAX_CHARS` | `12000` | Bu uzunlugun ustundeki kayit Gemini'ye gitmez |
| `GEMINI_CVE_RESERVE` | `0.5` | Gunluk Gemini butcesinin CVE'ye ayrilan payi; CVE tavani 400, diger bolumler 200 ([ADR-0005](docs/ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md)) |
| `RETRANSLATE_BATCH` | `100` | Retranslate turunda bolum basina taranan bekleyen kayit sayisi |
| `RETRANSLATE_UPGRADE_BATCH` | `40` | Tur ve bolum basina yukseltme siniri |
| `TRANSLATE_MIN_RATIO` | `0.4` | Ceviri kirpilma esigi: 80+ karakterlik metinde cikti/girdi orani bunun altindaysa ceviri reddedilir, kayit `needs_translation` kalir |
| `RETENTION_DAYS` | `90` | Saklama penceresi; `updated_at` bundan eski kayitlar cekim basinda silinir (cekim penceresinden ayridir) |
| `REFRESH_COOLDOWN` | `900` | `/api/v1/*/refresh/` sonrasi bolum sogumasi (sn) — **tum token'lar arasinda paylasilir** |
| `REFRESH_LOCK_TTL` | `3600` | Bolum cekim kilidinin omru (sn); worker olurse kilit bu surede kendiliginden duser |
| `DB_HOST` | _(bos)_ | Doluysa PostgreSQL kullanilir. Bossa yalniz `DEBUG=True` iken SQLite (`db.sqlite3`); `DEBUG=False` iken uygulama acilmaz. Compose `yerel-postgres` verir |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `cybernews` | Veritabani adi |
| `DB_USER` | `cybernews` | Veritabani kullanicisi |
| `DB_PASSWORD` | _(bos)_ | Veritabani sifresi. Compose: `.env`'deki `DB_PASSWORD` (yerel-platform `cybernews` kullanicisi) |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis baglantisi (cache) |
| `CELERY_BROKER_URL` | `redis://127.0.0.1:6379/1` | Redis baglantisi (Celery broker) |

> **Hostta `manage.py` calistirmak:** `DEBUG` varsayilani `False` oldugu icin anahtarsiz
> `python manage.py ...` artik reddedilir. Yerelde `DEBUG=True python manage.py ...`
> kullanin ya da komutu konteynerde calistirin (`docker compose exec teknoloji-api ...`).
> `DB_HOST` vermezseniz hostta `DEBUG=True` ile yerel `db.sqlite3` kullanilir.

---

## Bilinen Kisitlamalar

- LibreTranslate cevirileri Gemini'ye gore daha dusuk kalitede olabilir (ozel ad/guvenlik terimi hatalari otomatik dogrulamayla yakalanmaz); rozetten ayirt edilir, `retranslate_pending` Gemini ile yukseltene kadar boyle kalir. Gemini gunluk butcesi (`GEMINI_DAILY_BUDGET`, varsayilan 400) asilirsa yukseltme bir sonraki gune kalir (bkz. [Hiz Siniri ve Devre Kesici](#4-hiz-siniri-ve-devre-kesici))
- Dark Reading HTML scraping'e 403 doner, bu yuzden RSS feed kullanilir
- Gunicorn timeout 300 saniye — cok fazla kaynak secilirse zaman asimi olabilir
- Her fetch'te toplam makale sayisi **30 ile sinirlidir** (Gunicorn timeout'undan kacinmak icin)
- Redis blog sayfasi JS-rendered — `blockContent` div'inden icerik cekilir, eger site yapisi degisirse guncelleme gerekebilir
- Elastic 8.x serisi release notes farkli URL'de (`/guide/en/...`), sadece 9.x serisi icin detayli changelog cekilir
- Yapay Zeka bolumu yalnizca haber RSS'lerini kapsar; benchmark/leaderboard skorlari ertelenmistir ([ADR-0002](docs/ADR-0002-AI-Benchmark.md))
- `artificialintelligence-news.com` RSS'i 403 dondugu icin yerine MIT Technology Review AI kullanilir

---

## Mimari Kararlar (ADR)

| ADR | Konu | Durum |
|-----|------|-------|
| [ADR-0001](docs/ADR-0001-AI-News.md) | AI News bileseni | Accepted |
| [ADR-0002](docs/ADR-0002-AI-Benchmark.md) | AI Benchmark / Leaderboard bileseni | Proposed (ertelendi) |
| [ADR-0003](docs/ADR-0003-Entegrasyon-API-v1.md) | Dis tuketiciler icin `/api/v1/` entegrasyon katmani (imlecli delta, token, refresh, ceviri dogrulugu) | Accepted (A1–A5b uygulandi, canlida dogrulandi) |
| [ADR-0004](docs/ADR-0004-Ceviri-Saglayici-Zinciri.md) | Ceviri saglayici zinciri (LibreTranslate yedek; 2026-09-15: Google kaldirildi, Gemini yukseltme) | Accepted (degisiklik 2026-09-15) |
| [ADR-0005](docs/ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md) | Saklama olcusu `updated_at` (sil/yeniden yaz dongusu) ve CVE'ye Gemini butce onceligi | Accepted (uygulandi 2026-09-18, canlida dogrulandi) |
| [ADR-0006](docs/ADR-0006-FetchRun-Gorunurlugu-ve-Status-Ucu.md) | `FetchRun` gorunurlugu, durum semantigi ve dar `GET /api/v1/status/` ucu (ADR-0003 bolum 11'in yerine gecer) | Accepted (uygulandi 2026-09-21, canlida dogrulandi) |
| [ADR-0007](docs/ADR-0007-PostgreSQL-Gecisi-ve-Helm-Dogrulamasi.md) | SQLite'tan paylasilan yerel PostgreSQL'e kayipsiz gecis ve Helm chart dogrulamasi (Faz B) | Accepted (B1 2026-10-02 ve B2 2026-10-03 uygulandi; docker-desktop'ta dogrulandi) |

---

## Lisans

Bu proje MIT lisansi ile yayimlanmistir. Tam metin icin [LICENSE](LICENSE)
dosyasina bakin.
