# Güvenlik Hattı ve Bekleyen İşler Planı

> Son güncelleme: 2026-09-14. Hat PR #3 ile kuruldu. Bu dosya, hattın nasıl okunacağını ve ertelenen işleri tutar.
> Bir iş bitince kutusunu işaretle ve ilgili PR numarasını yanına yaz.

## 1. Hatlar ne zaman çalışır?

| Workflow | Tetik | Mod | Kırmızı olursa anlamı |
|---|---|---|---|
| `CI` | PR, `main` push | **Kapı** | Test / migration / build / helm bozuk → merge etme |
| `Dependency Review` | PR | **Kapı** | PR, HIGH/CRITICAL zafiyetli bir paket getiriyor |
| `gitleaks` | PR, `main` push, Pazartesi | PR'da **kapı**, diğerlerinde rapor | PR'da: yeni secret commit'lenmiş. Push/schedule'da: araç bozuk |
| `trivy` | PR, `main` push, Çarşamba | Rapor | Bulgu değil, **araç** bozuk: DB bayat ya da paketler taranmadı |
| `DAST (ZAP baseline)` | PR, `main` push, Pazartesi | Rapor | Uygulama ayağa kalkmadı ya da ZAP hedefe ulaşamadı |
| `CodeQL Advanced` | PR, `main` push, Pazar | Rapor | Analiz çalışmadı |
| `zizmor` | `.github/` değişince, Perşembe | Rapor | Workflow denetimi çalışmadı |
| `OpenSSF Scorecard` | `main` push, Salı | Rapor | Skor üretilemedi |
| Dependabot | Pazartesi + yeni CVE çıktıkça | — | Güncelleme PR'ları açar |

**Rapor modu:** Bulgu varsa hat yine yeşil kalır, bulgular aşağıdaki yerlere düşer.
Hat sadece taramanın kendisi yapılamadıysa kırmızı olur. Bulgu yok diye "boş yeşil" geçmez.

## 2. Hatalar nereye düşer, nasıl kontrol edilir?

| Ne arıyorsun | Nereye bak |
|---|---|
| Merge sonrası kırmızı olan hat | **Actions** sekmesi (ayrıca GitHub bildirimi / mail gelir) |
| Kod ve imaj zafiyetleri, secret'lar, workflow sorunları | **Security → Code scanning** (Tool filtresi: Trivy, CodeQL, gitleaks, zizmor, Scorecard) |
| Bağımlılık CVE'leri | **Security → Dependabot** |
| ZAP (DAST) bulguları | Actions → `DAST (ZAP baseline)` koşusu → **Summary** tablosu + `zap-baseline` artefaktı (HTML rapor) |
| SBOM (CycloneDX) | Actions → `trivy` koşusu → `sbom-*` artefaktları |

### Haftalık kontrol rutini (~10 dk)
1. **Actions:** Son 7 günde kırmızı koşu var mı? Varsa önce onu çöz, çünkü rapor hattı bozuksa bulgu listesi eksiktir.
2. **Security → Dependabot:** Açık security PR'larına bak (bkz. §3).
3. **Security → Code scanning:** Severity'e göre sırala; `critical` ve `high` olanları §4'teki P4 listesine ekle.
4. **ZAP Summary:** `FAIL-NEW` sıfırdan büyükse issue aç.

Terminalden tek liste halinde görmek istersen:

```bash
gh api "repos/AdanedhelWrites/tech-radar/code-scanning/alerts?state=open&per_page=100" --paginate --jq '.[] | "\(.tool.name) | \(.rule.security_severity_level // .rule.severity) | \(.rule.id) | \(.most_recent_instance.location.path)"'
```

```bash
gh api "repos/AdanedhelWrites/tech-radar/dependabot/alerts?state=open&per_page=100" --jq '.[] | "\(.security_advisory.severity) | \(.dependency.package.name) | \(.security_advisory.summary)"'
```

## 3. Dependabot PR'ı gelince ne yapılır?

1. PR, CI eklenmeden önceki bir `main`'den açıldıysa check listesinde `Backend (Django testleri)` yoktur. Bu durumda PR sayfasındaki **Update branch** butonuna bas (ya da `gh pr update-branch <no>`). Not: `@dependabot rebase` yorumu, PR'ı açan config değiştiyse reddedilir.
2. Bütün check'lerin bitmesini bekle.
3. **Hepsi yeşilse** merge et.
4. Aynı dosyaya dokunan iki PR'ı art arda merge ediyorsan, ilkinden sonra ikinciyi tekrar **Update branch** ile güncelle ve check'lerin yeniden yeşil gelmesini bekle. Böylece birleşik hal de test edilmiş olur.
5. **`CI` kırmızıysa merge etme.** Genelde başka bir paket de birlikte yükseltilmeli (örnek: Django 5 için `django-celery-beat` da yükseltilmeli). PR'ı kapat ve işi aşağıdaki plana ekle.

## 4. Ertelenen işler (sırayla)

### P1: Django 4.2 → 5.2 yükseltmesi (mecburi, öncelikli)
Django 4.2 LTS'nin desteği Nisan 2026'da bitti. Açık Dependabot alert'lerinin çoğu Django'ya ait (2 critical, 14 high).
Dependabot PR #5 tek başına kırıldı, çünkü `django-celery-beat 2.5.0` `Django<5.0` istiyor.

- [ ] `chore/django-5.2` branch'i aç; PR #5'i "birlikte yükseltme branch'inde yapılacak" notuyla kapat
- [ ] `requirements.txt` içinde birlikte yükselt (sürümleri uygularken PyPI'dan tekrar kontrol et; 2026-09-13 itibarıyla):
  - [ ] `Django` 4.2.7 → 5.2.x
  - [ ] `django-celery-beat` 2.5.0 → 2.9.x
  - [ ] `django-redis` 5.4.0 → 7.x (**major**, changelog oku)
  - [ ] `django-cors-headers` 4.3.1 → 4.9.x
  - [ ] `whitenoise` 6.6.0 → 6.12.x
  - [ ] `celery` 5.3.4 → 5.6.x
  - [ ] `gunicorn` 21.2.0 → güncel (2 high alert)
  - [ ] `requests` 2.31.0 → güncel (3 medium alert)
- [ ] `cybernews/settings.py`: `STATICFILES_STORAGE` Django 5.1'de kaldırıldı, `STORAGES`'a geç:
  ```python
  STORAGES = {
      "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
      "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
  }
  ```
- [ ] CI yeşil olmalı: 140+ test, `makemigrations --check`. celery-beat yeni migration getirir; migration'ı commit'le
- [ ] Lokal `docker compose` smoke testi: API, worker, beat ayağa kalkıyor mu
- [ ] Canlıya alırken migration sonrası **api / worker / scheduler restart** (migration 0008 dersi)

### P2: Frontend bağımlılıkları ve taban imajlar
- [ ] npm: `axios`, `vite`, `postcss`, `react-router-dom` yükselt (40'tan fazla alert) → `npm ci && npm run build`
- [ ] `frontend/Dockerfile`: `node:18-alpine` (EOL) → `node:22-alpine`
- [ ] `frontend/Dockerfile`: `nginx:1.25-alpine` (Trivy: EOSL) → güncel stable alpine
- [ ] `docker-compose.yml`: `node:18-alpine` → `node:22-alpine`
- [ ] `trivy` → `Imaj (frontend)` job'ında EOSL uyarısı kaybolmalı

### P3: Zorunlu status check'ler
- [ ] `main-koruma` ruleset'ine (Settings → Rules) zorunlu check ekle: `Backend (Django testleri)`, `Frontend (Vite build)`, `Helm / Compose dogrulama`, `dependency-review`, `gitleaks`
- Etkisi: Testi kırmızı PR merge edilemez. Web arayüzünden direkt `main`'e commit atmak da kapanır, her değişiklik PR'dan geçer.

### P4: Bulgu triajı (P1 ve P2'den **sonra**)
Alert'lerin çoğu yükseltmelerle kendiliğinden kapanacak; triaj kalanlara yapılmalı.
- [ ] Security → Code scanning → Tool status: eski Trivy yapılandırmasını (kategorisiz, ~76 alert) sil. Yeni kategoriler `trivy-fs`, `trivy-image-backend`, `trivy-image-frontend`
- [ ] CodeQL'deki 16 açık alert'i incele: düzelt ya da gerekçesiyle "dismiss" et
- [ ] Trivy misconfig bulguları (Helm/k8s: securityContext, resource limit vb.) → Faz B Kubernetes doğrulamasıyla birlikte ele al
- [ ] `docker-compose.yml` içindeki `SECRET_KEY=your-secret-key-here...` placeholder'ını `.env` dosyasına taşı

### P5: Görünürlük
- [ ] ZAP sonucunu SARIF'e çevirip Security sekmesine yükle; tek kontrol yeri Security olsun
- [ ] Haftalık güvenlik özeti: araç × severity tablosuyla GitHub Issue açan bir workflow
- [ ] A5 (OpenAPI şeması) çıkınca `zaproxy/action-api-scan` ile `/api/v1/` tam taransın

## 5. Geçmiş
- **2026-09-13:** PR #3 ile güvenlik hattı kuruldu. SOOS DAST (bozuk, ücretli) kaldırıldı. Saat dilimine bağlı kırmızı olan test düzeltildi (`timezone.localdate()`).
- **2026-09-13:** Dependabot alerts + security updates, private vulnerability reporting ve `main` ruleset (silme/force-push engeli) açıldı.
- **2026-09-14:** PR #4 (`djangorestframework` 3.14.0 → 3.17.2) ve PR #6 (`lxml` 5.3.0 → 6.1.0, XXE düzeltmesi) yeni CI ile, birlikte 140/140 test yeşil doğrulanıp merge edildi. PR #5 (Django 5.2.16) açık bırakıldı; bkz. P1.
