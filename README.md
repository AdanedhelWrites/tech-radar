# Teknoloji Radar

Siber guvenlik haberleri, CVE zafiyetleri, Kubernetes ekosistemi, SRE (Site Reliability Engineering) haberleri ve DevTools altyapi araclari guncellemelerini **27 farkli kaynaktan** toplayan, Turkceye ceviren ve modern bir arayuzde sunan full-stack haber agregasyon uygulamasi.

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
                               │   (27 kaynak)          │
                              │   + Google Translate    │
                              └─────────────────────────┘
```

## Ozellikler

- **27 farkli kaynak** — 5 siber guvenlik, 5 CVE, 3 Kubernetes, 5 SRE, 9 DevTools
- **Tam makale cevirisi** — Kisaltma yok, tum icerik Turkceye cevrilir
- **Teknik terim korumasi** — 130+ terim (Kubernetes, Docker, Elasticsearch, CVE, CVSS, vb.) ceviri sirasinda bozulmaz
- **Turkce imla post-processing** — Cumle basi buyuk harf, noktalama duzeltme, URL/surum koruma
- **Parca tabanli ceviri** — Uzun makaleler cumle sinirlarindan 4500 karakterlik parcalara bolunerek cevrilir
- **Karanlik mod** — Koyu tonlarda arayuz (steel blue `#5b86a7` vurgu rengi)
- **DevTools takibi** — MinIO, Seq, Ceph, MongoDB, PostgreSQL, RabbitMQ, Elasticsearch+Kibana, Redis, Moodle release guncellemeleri
- **Tarih filtresi** — 1-15 gun (haberler) / 1-60 gun (DevTools) slider ile filtreleme
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

---

## Teknoloji Yigini

| Katman | Teknolojiler |
|--------|-------------|
| **Backend** | Python 3.11, Django 4.2, Django REST Framework 3.14, Celery 5.3, Gunicorn |
| **Frontend** | React 18, Vite 5, React Bootstrap 2.9, React Router DOM 6, Axios |
| **Veri** | SQLite (lokal), PostgreSQL 16 (K8s), Redis 7 (cache + broker) |
| **Scraping** | BeautifulSoup4, lxml, Requests |
| **Ceviri** | deep-translator (Google Translate) + merkezi post-processing |
| **Altyapi** | Docker Compose, Kubernetes, Nginx 1.25, Whitenoise |

---

## Kurulum (Docker Compose)

### Gereksinimler

- Docker ve Docker Compose
- Internet baglantisi (kaynak sitelere ve Google Translate'e erisim)

### Hizli Baslangic

```bash
git clone https://github.com/AdanedhelWrites/tech-radar.git
cd tech-radar/cybersecurity_news

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

---

## Kullanim

Her sayfa ayni duzeni takip eder:

1. Sol panelden **gun araligini** (1-15 / DevTools icin 1-60) ve **kaynaklari** secin
2. **"Getir"** butonuna tiklayin
3. Haberler cekilir, Turkceye cevrilir ve orta panelde listelenir
4. Bir habere tiklayarak sag panelde detayini goruntuleyin

**Ek butonlar:**
- **Yenile** — Mevcut verileri yeniden yukler
- **Sifirla** — Tum verileri temizler
- **Indir** — Koyu temali HTML rapor olarak disa aktarir

---

## API Endpoints

Her bolum (news, cve, k8s, sre, devtools) ayni endpoint yapisini kullanir:

| Method | Endpoint Deseni | Aciklama |
|--------|-----------------|----------|
| GET | `/api/{bolum}/` | Kayitli verileri listele |
| POST | `/api/{bolum}/fetch/` | Yeni verileri cek (body: `{"days": 7, "sources": [...]}`) |
| POST | `/api/{bolum}/clear/` | Tum verileri sil |
| GET | `/api/{bolum}/stats/` | Istatistikleri getir |
| GET | `/api/{bolum}/export/` | HTML rapor olarak disa aktar |

**Bolum isimleri:** `news` (Siber Guvenlik, fetch endpoint: `/api/fetch/`), `cve`, `k8s`, `sre`, `devtools`

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
│   ├── models.py               # NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry
│   ├── views.py                # API endpoint'leri (5 bolum x 5 endpoint = 25)
│   ├── serializers.py          # DRF serializer'lari
│   ├── urls.py                 # API URL pattern'leri
│   ├── translation_utils.py    # Merkezi ceviri modulu (terim koruma + post-processing)
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
│   │   │   └── DevToolsComponent.jsx   # DevTools sayfasi
│   │   └── services/
│   │       └── api.js          # Axios API servisleri
│   ├── Dockerfile              # Production build: Node + Nginx
│   ├── nginx.conf              # SPA routing + /api proxy
│   ├── vite.config.js          # Dev proxy ayarlari
│   ├── index.html
│   └── package.json
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

Uzun metinler cumle sinirlarindan 4500 karakterlik parcalara bolunur (Google Translate 5000 karakter limiti). Her parca icin ayri terim koruma uygulanir. Parcalar arasi 0.3 saniye bekleme (rate limit).

### 3. Turkce Post-Processing

Ceviri sonrasi otomatik duzeltmeler:

- Cumle basi ve satir basi buyuk harf
- Noktalama duzeltmeleri (noktadan sonra bosluk, parantez temizligi)
- URL/email/dosya uzantisi korumasi (post-processing'in `.co` -> `. Co` yapmasi engellenir)
- Ingilizce ay isimlerinin Turkceyecevirisi
- Bozuk Turkce karakter encoding duzeltmesi
- K8s kisaltmasinin korunmasi

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

- Google Translate ucretsiz API rate limit'e takilabilir — cok sayida makale cekildiginde yavaslama olabilir
- Dark Reading HTML scraping'e 403 doner, bu yuzden RSS feed kullanilir
- Gunicorn timeout 300 saniye — cok fazla kaynak secilirse zaman asimi olabilir
- Her fetch'te toplam makale sayisi **30 ile sinirlidir** (Gunicorn timeout'undan kacinmak icin)
- Redis blog sayfasi JS-rendered — `blockContent` div'inden icerik cekilir, eger site yapisi degisirse guncelleme gerekebilir
- Elastic 8.x serisi release notes farkli URL'de (`/guide/en/...`), sadece 9.x serisi icin detayli changelog cekilir

---

## Lisans

MIT License
