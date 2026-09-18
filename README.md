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
| **Veri** | SQLite (lokal), PostgreSQL 16 (K8s), Redis 7 (cache + broker) |
| **Scraping** | BeautifulSoup4, lxml, Requests |
| **Ceviri** | Cekim aninda yerel LibreTranslate (aninda Turkce, rozetli); retranslate 2 saatte bir bekleyen ve LibreTranslate kayitlarini Gemini API (gemini-3.5-flash-lite, ucretsiz katman, kayit basina tek istek) ile yukseltir + merkezi post-processing |
| **Altyapi** | Docker Compose, Kubernetes, Nginx 1.25, Whitenoise |

---

## Kurulum (Docker Compose)

### Gereksinimler

- Docker ve Docker Compose
- Internet baglantisi (kaynak sitelere ve Gemini API'ye erisim icin; LibreTranslate yerel container'da calisir)

### Hizli Baslangic

`.env.example`'i `.env` olarak kopyalayin ve isterseniz `GEMINI_API_KEY` degerini girin (bos birakilirsa Gemini hic denenmez, sistem LibreTranslate ile calisir):

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
| `teknoloji-api` | `teknoloji-haberleri-api:latest` | 8000 | Django REST API, scraping, ceviri, veritabani |
| `teknoloji-frontend` | `node:18-alpine` | 3000 | React arayuz (Vite dev server, hot-reload) |
| `teknoloji-redis` | `redis:7-alpine` | 6379 | Cache + Celery message broker |
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

# Django shell
docker compose exec teknoloji-api python manage.py shell

# Sifirdan baslat (volume'lar dahil)
docker compose down -v && docker compose up -d --build
```

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
│   └── admin.py                # Django admin kayitlari
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
├── k8s/                        # Kubernetes manifest'leri (kubectl apply)
│   ├── 00-namespace.yaml
│   ├── 01-configmap.yaml       # Uygulama ayarlari
│   ├── 02-secret.yaml          # Gizli bilgiler (placeholder)
│   ├── 03-postgresql.yaml      # PostgreSQL (opsiyonel)
│   ├── 04-redis.yaml           # Redis (opsiyonel)
│   ├── 05-backend.yaml         # Django API Deployment + Service
│   ├── 06-frontend.yaml        # Nginx Frontend Deployment + Service
│   ├── 07-celery.yaml          # Worker + Beat Deployment
│   ├── 08-ingress.yaml         # Nginx Ingress kurallari
│   └── 09-migration-job.yaml   # DB migration Job
│
├── helm/tech-radar/            # Helm chart
│   ├── Chart.yaml              # Chart metadata (v1.0.0)
│   ├── values.yaml             # Varsayilan degerler
│   ├── .helmignore
│   └── templates/
│       ├── _helpers.tpl        # Paylasilan template fonksiyonlari
│       ├── namespace.yaml
│       ├── configmap.yaml
│       ├── secret.yaml
│       ├── postgresql.yaml     # postgresql.enabled ile kontrol edilir
│       ├── redis.yaml          # redis.enabled ile kontrol edilir
│       ├── backend.yaml
│       ├── frontend.yaml
│       ├── celery.yaml         # Worker + Beat
│       ├── ingress.yaml        # ingress.enabled ile kontrol edilir
│       ├── migration-job.yaml  # post-install/post-upgrade hook
│       └── NOTES.txt           # helm install sonrasi bilgi mesaji
│
├── values.yaml                 # Root-level values referansi (Helm chart'a kopyasi)
├── docker-compose.yml          # 5 servis (lokal gelistirme)
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

## Kubernetes'e Deploy Etme

### Opsion A — Manifest'lerle (kubectl apply)

#### On Gereksinimler

- Kubernetes cluster (minikube, k3s, EKS, GKE, AKS, vb.)
- `kubectl` CLI kurulu ve cluster'a bagli
- Docker image build ortami
- Nginx Ingress Controller (opsiyonel)

#### Mimari (Kubernetes)

```
                    ┌─────────────────────┐
                    │   Ingress (Nginx)   │
                    └──────┬──────────────┘
                           │
              ┌────────────┼────────────┐
              │ /api,      │ /          │
              │ /admin,    │            │
              │ /static    │            │
              ▼            │            ▼
    ┌──────────────┐       │  ┌──────────────────┐
    │ teknoloji-api│       │  │teknoloji-frontend│
    │ replica: 2   │       │  │  replica: 2      │
    │ :8000        │       │  │  :3000 (nginx)   │
    └──────┬───────┘       │  └──────────────────┘
           │               │
    ┌──────┼───────────────┘
    │      │
    ▼      ▼
┌────────┐  ┌────────────────────┐
│ Redis  │  │    PostgreSQL      │
│ :6379  │  │    :5432           │
└────────┘  └────────────────────┘
    ▲
    │
┌───┴──────────────┐  ┌───────────────────┐
│ teknoloji-worker │  │teknoloji-scheduler│
│ (Celery Worker)  │  │ (Celery Beat)     │
└──────────────────┘  └───────────────────┘
```

Docker Compose'dan farkli olarak Kubernetes'te:
- **PostgreSQL** kullanilir (SQLite yerine — coklu replica destegi)
- Frontend **Nginx** ile statik dosya olarak sunulur (Vite dev server yerine)
- Tum konfigrasyon **ConfigMap** ve **Secret** ile yonetilir

#### Adim 1 — Docker Image'larini Build Edin

```bash
# Backend
docker build -t teknoloji-haberleri-api:latest .

# Frontend (production Nginx build)
docker build -t teknoloji-haberleri-frontend:latest ./frontend
```

Private registry kullaniyorsaniz tag'leyip push edin:

```bash
docker tag teknoloji-haberleri-api:latest REGISTRY/teknoloji-haberleri-api:latest
docker tag teknoloji-haberleri-frontend:latest REGISTRY/teknoloji-haberleri-frontend:latest
docker push REGISTRY/teknoloji-haberleri-api:latest
docker push REGISTRY/teknoloji-haberleri-frontend:latest
```

Registry kullandiginizda K8s manifest'lerindeki `image:` degerlerini ve `imagePullPolicy` satirini guncellemeyi unutmayin.

#### Adim 2 — Secret'lari Olusturun

`k8s/02-secret.yaml` dosyasindaki placeholder degerleri gercek degerlerle degistirin:

```yaml
stringData:
  SECRET_KEY: "min-50-karakter-rastgele-guclu-bir-key"
  DB_USER: "cybernews"
  DB_PASSWORD: "guclu-veritabani-sifresi"
  POSTGRES_PASSWORD: "guclu-veritabani-sifresi"
```

Veya dogrudan kubectl ile:

```bash
kubectl create namespace teknoloji-haberleri

kubectl create secret generic teknoloji-secret \
  --namespace=teknoloji-haberleri \
  --from-literal=SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=DB_USER=cybernews \
  --from-literal=DB_PASSWORD="$(openssl rand -hex 16)" \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 16)"
```

#### Adim 3 — Manifest'leri Uygulayin

```bash
# Tum manifest'leri uygula
kubectl apply -f k8s/

# Veya adim adim:
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml
kubectl apply -f k8s/02-secret.yaml
kubectl apply -f k8s/03-postgresql.yaml     # Mevcut PostgreSQL varsa ATLA
kubectl apply -f k8s/04-redis.yaml           # Mevcut Redis varsa ATLA
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=teknoloji-postgresql \
  -n teknoloji-haberleri --timeout=120s
kubectl apply -f k8s/09-migration-job.yaml
kubectl wait --for=condition=complete job/teknoloji-migrate \
  -n teknoloji-haberleri --timeout=120s
kubectl apply -f k8s/05-backend.yaml
kubectl apply -f k8s/06-frontend.yaml
kubectl apply -f k8s/07-celery.yaml
kubectl apply -f k8s/08-ingress.yaml         # Ingress Controller yoksa ATLA
```

#### Adim 4 — Dogrulama

```bash
kubectl get pods -n teknoloji-haberleri
kubectl logs -f deployment/teknoloji-api -n teknoloji-haberleri
```

Ingress yoksa port forward:

```bash
kubectl port-forward svc/teknoloji-frontend 3000:3000 -n teknoloji-haberleri
kubectl port-forward svc/teknoloji-api 8000:8000 -n teknoloji-haberleri
```

### Opsion B — Helm Chart ile Deploy

Helm chart `helm/tech-radar/` dizininde bulunur. Tum K8s kaynaklarini tek komutla deploy eder ve `values.yaml` uzerinden yapilandirma saglar.

#### On Gereksinimler

- Kubernetes cluster (minikube, k3s, EKS, GKE, AKS, vb.)
- `kubectl` CLI kurulu ve cluster'a bagli
- [Helm 3](https://helm.sh/docs/intro/install/) kurulu
- Docker image'lar build edilmis (Opsion A, Adim 1'e bakin)

#### Adim 1 — values.yaml Duzenleme

`helm/tech-radar/values.yaml` dosyasini ortaminiza gore duzenleyin:

```yaml
# Onemli degerler:
secrets:
  secretKey: "min-50-karakter-rastgele-guclu-bir-key"
  dbUser: "cybernews"
  dbPassword: "guclu-veritabani-sifresi"
  postgresPassword: "guclu-veritabani-sifresi"

ingress:
  enabled: true
  host: teknoloji.example.com      # Kendi domain adiniz

# Harici PostgreSQL kullaniyorsaniz:
postgresql:
  enabled: false                    # Cluster icine kurma
config:
  database:
    host: "postgres.ornek-ns.svc.cluster.local"

# Harici Redis kullaniyorsaniz:
redis:
  enabled: false
config:
  redis:
    url: "redis://redis.ornek-ns.svc.cluster.local:6379/0"
    celeryBrokerUrl: "redis://redis.ornek-ns.svc.cluster.local:6379/1"
```

#### Adim 2 — Helm Install

```bash
# Varsayilan degerlerle kurulum
helm install tech-radar ./helm/tech-radar \
  --namespace teknoloji-haberleri \
  --create-namespace

# Veya ozel values dosyasiyla
helm install tech-radar ./helm/tech-radar \
  --namespace teknoloji-haberleri \
  --create-namespace \
  -f my-values.yaml

# Veya komut satirindan deger gecirerek
helm install tech-radar ./helm/tech-radar \
  --namespace teknoloji-haberleri \
  --create-namespace \
  --set ingress.host=radar.example.com \
  --set secrets.secretKey="$(openssl rand -hex 32)" \
  --set secrets.dbPassword="$(openssl rand -hex 16)" \
  --set secrets.postgresPassword="$(openssl rand -hex 16)"
```

> **Not:** Migration job, Helm `post-install` ve `post-upgrade` hook olarak otomatik calisir. Manuel calistirmaya gerek yoktur.

#### Adim 3 — Dogrulama

```bash
# Pod durumlari
kubectl get pods -n teknoloji-haberleri

# Helm release durumu
helm status tech-radar -n teknoloji-haberleri

# Uygulama loglari
kubectl logs -f deployment/teknoloji-api -n teknoloji-haberleri
```

Ingress yoksa port forward:

```bash
kubectl port-forward svc/teknoloji-frontend 3000:3000 -n teknoloji-haberleri
kubectl port-forward svc/teknoloji-api 8000:8000 -n teknoloji-haberleri
```

#### Guncelleme (Helm Upgrade)

```bash
# Yeni image build sonrasi
helm upgrade tech-radar ./helm/tech-radar \
  --namespace teknoloji-haberleri \
  --set backend.image.tag=v2 \
  --set frontend.image.tag=v2

# Veya values dosyasini guncelleyip
helm upgrade tech-radar ./helm/tech-radar \
  --namespace teknoloji-haberleri \
  -f my-values.yaml
```

Migration job her upgrade'de otomatik calisir (post-upgrade hook).

#### Geri Alma (Rollback)

```bash
# Onceki surume geri don
helm rollback tech-radar -n teknoloji-haberleri

# Belirli bir revision'a geri don
helm history tech-radar -n teknoloji-haberleri
helm rollback tech-radar 2 -n teknoloji-haberleri
```

#### Kaldirma

```bash
helm uninstall tech-radar -n teknoloji-haberleri
kubectl delete namespace teknoloji-haberleri
```

#### Helm Chart Yapisi

```
helm/tech-radar/
├── Chart.yaml            # name: tech-radar, version: 1.0.0
├── values.yaml            # Tum varsayilan degerler
├── .helmignore
└── templates/
    ├── _helpers.tpl       # Paylasilan label/image fonksiyonlari
    ├── NOTES.txt          # Install sonrasi bilgi mesaji
    ├── namespace.yaml
    ├── configmap.yaml     # Django, DB, Redis ortam degiskenleri
    ├── secret.yaml        # SECRET_KEY, DB_USER, DB_PASSWORD
    ├── postgresql.yaml    # PVC + Deployment + Service (postgresql.enabled)
    ├── redis.yaml         # Deployment + Service (redis.enabled)
    ├── backend.yaml       # Django API Deployment + Service
    ├── frontend.yaml      # Nginx Frontend Deployment + Service
    ├── celery.yaml        # Worker + Beat Deployment
    ├── ingress.yaml       # Nginx Ingress (ingress.enabled)
    └── migration-job.yaml # post-install/post-upgrade hook
```

#### Onemli values.yaml Parametreleri

| Parametre | Varsayilan | Aciklama |
|-----------|-----------|----------|
| `backend.replicas` | `2` | API pod sayisi |
| `frontend.replicas` | `2` | Frontend pod sayisi |
| `worker.replicas` | `1` | Celery worker sayisi |
| `scheduler.replicas` | `1` | Beat scheduler (degistirmeyin!) |
| `postgresql.enabled` | `true` | `false` = harici PostgreSQL kullan |
| `redis.enabled` | `true` | `false` = harici Redis kullan |
| `ingress.enabled` | `true` | `false` = Ingress olusturma |
| `ingress.host` | `teknoloji.example.com` | Domain adiniz |
| `ingress.tls.enabled` | `false` | TLS/HTTPS aktif et |
| `backend.image.tag` | `latest` | Backend image tag |
| `frontend.image.tag` | `latest` | Frontend image tag |
| `postgresql.storage.size` | `5Gi` | PVC boyutu |

---

## Ortam Degiskenleri

Uygulama tamamen ortam degiskenleri ile yapilandirabilir. Docker Compose'da `docker-compose.yml` icinde, Kubernetes'te ConfigMap + Secret ile ayarlanir.

| Degisken | Varsayilan | Aciklama |
|----------|-----------|----------|
| `SECRET_KEY` | `django-insecure-...` | Django secret key (production'da mutlaka degistirin) |
| `DEBUG` | `False` | Django debug modu |
| `ALLOWED_HOSTS` | `*` | Virgulle ayrilmis izinli host listesi |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000,...` | Frontend origin'leri |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Admin oturumuyla POST yapabilecek frontend origin'leri (Vite proxy `changeOrigin` kullandigi icin gerekli) |
| `GEMINI_API_KEY` | (bos) | Google AI Studio anahtari; bos ise Gemini hic denenmez |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model |
| `GEMINI_DAILY_BUDGET` | `400` | Gunluk istek butcesi (Pasifik gunu; ucretsiz katman 500 RPD) |
| `GEMINI_MIN_INTERVAL` | `5` | Istekler arasi saniye (15 RPM'in altinda) |
| `GEMINI_COOLDOWN` | `600` | 429/5xx sonrasi bekleme (sn) |
| `GEMINI_TIMEOUT` | `60` | Istek zaman asimi (sn) |
| `GEMINI_MAX_CHARS` | `12000` | Bu uzunlugun ustundeki kayit Gemini'ye gitmez |
| `RETRANSLATE_UPGRADE_BATCH` | `40` | Tur ve bolum basina yukseltme siniri |
| `DATABASE_URL` | _(bos)_ | Herhangi bir deger atanirsa PostgreSQL aktif olur, bossa SQLite |
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `cybernews` | Veritabani adi |
| `DB_USER` | `cybernews` | Veritabani kullanicisi |
| `DB_PASSWORD` | _(bos)_ | Veritabani sifresi |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis baglantisi (cache) |
| `CELERY_BROKER_URL` | `redis://127.0.0.1:6379/1` | Redis baglantisi (Celery broker) |

---

## Guncelleme (Kubernetes)

### kubectl ile (Opsion A)

```bash
# Yeni image build
docker build -t teknoloji-haberleri-api:v2 .
docker build -t teknoloji-haberleri-frontend:v2 ./frontend

# Migration (gerekiyorsa)
kubectl delete job teknoloji-migrate -n teknoloji-haberleri --ignore-not-found
kubectl apply -f k8s/09-migration-job.yaml

# Deployment guncelleme
kubectl set image deployment/teknoloji-api api=teknoloji-haberleri-api:v2 -n teknoloji-haberleri
kubectl set image deployment/teknoloji-frontend frontend=teknoloji-haberleri-frontend:v2 -n teknoloji-haberleri
kubectl set image deployment/teknoloji-worker worker=teknoloji-haberleri-api:v2 -n teknoloji-haberleri
kubectl set image deployment/teknoloji-scheduler scheduler=teknoloji-haberleri-api:v2 -n teknoloji-haberleri
```

### Helm ile (Opsion B)

```bash
# Yeni image build
docker build -t teknoloji-haberleri-api:v2 .
docker build -t teknoloji-haberleri-frontend:v2 ./frontend

# Upgrade (migration otomatik calisir)
helm upgrade tech-radar ./helm/tech-radar \
  -n teknoloji-haberleri \
  --set backend.image.tag=v2 \
  --set frontend.image.tag=v2

# Geri alma
helm rollback tech-radar -n teknoloji-haberleri
```

### Kaldirma

```bash
# kubectl ile
kubectl delete namespace teknoloji-haberleri

# Helm ile
helm uninstall tech-radar -n teknoloji-haberleri
kubectl delete namespace teknoloji-haberleri
```

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
| [ADR-0003](docs/ADR-0003-Entegrasyon-API-v1.md) | Dis tuketiciler icin `/api/v1/` entegrasyon katmani (imlecli delta, token, refresh, ceviri dogrulugu) | Accepted (A1–A3 uygulandi; A4–A5 acik) |
| [ADR-0004](docs/ADR-0004-Ceviri-Saglayici-Zinciri.md) | Ceviri saglayici zinciri (LibreTranslate yedek; 2026-09-15: Google kaldirildi, Gemini yukseltme) | Accepted (degisiklik 2026-09-15) |
| [ADR-0005](docs/ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md) | Saklama olcusu `updated_at` (sil/yeniden yaz dongusu) ve CVE'ye Gemini butce onceligi | Accepted (uygulandi 2026-09-18, canlida dogrulandi) |

---

## Lisans

MIT License
