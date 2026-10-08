# Güvenlik Hattı ve Bekleyen İşler Planı

> Son güncelleme: 2026-10-08 (P3, P4 ve P5-a tamamlandı; kalan P5-b/c). Hat PR #3 ile kuruldu. Bu dosya, hattın nasıl okunacağını ve ertelenen işleri tutar.
> Bir iş bitince kutusunu işaretle ve ilgili PR numarasını yanına yaz.

## 1. Hatlar ne zaman çalışır?

| Workflow | Tetik | Mod | Kırmızı olursa anlamı |
|---|---|---|---|
| `CI` | PR, `main` push | **Kapı** | Test / migration / build / helm bozuk → merge etme |
| `Dependency Review` | PR | **Kapı** | PR, HIGH/CRITICAL zafiyetli bir paket getiriyor |
| `gitleaks` | PR, `main` push, Pazartesi | PR'da **kapı**, diğerlerinde rapor | PR'da: yeni secret commit'lenmiş. Push/schedule'da: araç bozuk |
| `trivy` | PR, `main` push, Çarşamba | Rapor | Bulgu değil, **araç** bozuk: DB bayat ya da paketler taranmadı |
| `DAST (ZAP baseline)` | PR, `main` push, Pazartesi | Rapor (SARIF → Code scanning, kategori `zap-baseline`) | Uygulama ayağa kalkmadı, ZAP hedefe ulaşamadı ya da SARIF üretilemedi |
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
| ZAP (DAST) bulguları | **Security → Code scanning** (Tool: OWASP ZAP, kategori `zap-baseline`; konum sanal yol `dast/<url-yolu>`, tam URL mesajda; severity ZAP riskinden); ayrıca Actions → `DAST (ZAP baseline)` koşusu → **Summary** tablosu + `zap-baseline` artefaktı (HTML/JSON rapor) |
| SBOM (CycloneDX) | Actions → `trivy` koşusu → `sbom-*` artefaktları |

### Haftalık kontrol rutini (~10 dk)
1. **Actions:** Son 7 günde kırmızı koşu var mı? Varsa önce onu çöz, çünkü rapor hattı bozuksa bulgu listesi eksiktir.
2. **Security → Dependabot:** Açık security PR'larına bak (bkz. §3).
3. **Security → Code scanning:** Severity'e göre sırala; `critical` ve `high` olanları §4'teki P4 listesine ekle.
4. **ZAP:** Code scanning'de Tool = OWASP ZAP filtresiyle `warning`/`error` seviyesindekilere bak (Summary tablosu yedek).

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

### P0: Açık Dependabot PR'larının triajı ✅ (2026-09-14)
`dependabot.yml` ilk merge edildiğinde 15 sürüm PR'ı açıldı. Config'e semver-major filtresi eklenince Dependabot major PR'ları (#7–#10, #14–#21) kendisi kapattı.
- [x] #24 axios 1.13.5 → 1.20.0 + react-router-dom 6.30.3 → 6.30.6: test edildi, merge
- [x] #11 nginx 1.25-alpine → 1.31-alpine: #24 ile birlikte test edildi, merge (frontend imajı artık EOSL değil)
- [x] #25 python-minor-patch grubu: **kapatıldı**. Grup çelişkili: DRF 3.18.0 `django>=5.2` istiyor, grup Django'yu 4.2.30'da tutuyor → P1
- [x] #5 Django 5.2.16: **kapatıldı** → P1

> Not: P1 bitene kadar Dependabot, python-minor-patch grubunu her pazartesi aynı çelişkiyle yeniden açabilir. Kırmızıysa kapat; kalıcı çözüm P1.

### P1: Django 4.2 → 5.2 yükseltmesi ✅ (2026-09-22)
Uygulandı: Django 5.2.16 (2026-09-22), 5.2.17 PR #43 (2026-09-30). Ayrıntı: superpowers/specs/2026-09-22-guvenlik-temizligi-design.md.
Django 4.2 LTS'nin desteği Nisan 2026'da bitti. Açık Dependabot alert'lerinin çoğu Django'ya ait (2 critical, 14 high).
Dependabot PR #5 tek başına kırıldı, çünkü `django-celery-beat 2.5.0` `Django<5.0` istiyor.

- [x] `chore/django-5.2` branch'i aç (PR #5 ve #25 kapatıldı, işler burada)
- [x] `requirements.txt` içinde birlikte yükselt (sürümleri uygularken PyPI'dan tekrar kontrol et; 2026-09-13 itibarıyla):
  - [x] `Django` 4.2.7 → 5.2.x
  - [x] `django-celery-beat` 2.5.0 → 2.9.x
  - [ ] `django-redis` 5.4.0 → 7.x (**major**, changelog oku) — ertelendi: 5.4.0 Django 5.2 ile temiz çözülüyor (2026-09-22 dry-run), major yükseltme gerekmedi
  - [x] `django-cors-headers` 4.3.1 → 4.9.x
  - [x] `whitenoise` 6.6.0 → 6.12.x
  - [x] `celery` 5.3.4 → 5.6.x
  - [x] `gunicorn` 21.2.0 → güncel (2 high alert)
  - [x] `requests` 2.31.0 → güncel (3 medium alert)
  - [x] `djangorestframework` 3.17.2 → 3.18.x (Django 5.2 ister)
  - [ ] `redis` (py) 5.0.1 → django-redis 7 ile uyumlu sürüm — 5.3.1'de; django-redis 7 yükseltmesine bağlı, ertelendi
- [x] `cybernews/settings.py`: `STATICFILES_STORAGE` Django 5.1'de kaldırıldı, `STORAGES`'a geç:
  ```python
  STORAGES = {
      "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
      "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
  }
  ```
- [x] CI yeşil olmalı: 140+ test, `makemigrations --check`. celery-beat yeni migration getirir; migration'ı commit'le
- [x] Lokal `docker compose` smoke testi: API, worker, beat ayağa kalkıyor mu
- [x] Canlıya alırken migration sonrası **api / worker / scheduler restart** (migration 0008 dersi)

### P2: Frontend bağımlılıkları ve taban imajlar
- [x] npm: `axios` 1.20.0, `react-router-dom` 6.30.6 (PR #24)
- [x] npm: kalan alert'ler için Security → Dependabot'a bak (`vite` 5.4.21, `postcss` 8.5.6 şu anki sürümler); major gerekenler (vite 6+, react 19, react-router 7) ayrı iş
- [x] `frontend/Dockerfile`: `node:18-alpine` (EOL) → `node:22-alpine`
- [x] `frontend/Dockerfile`: `nginx:1.25-alpine` → `nginx:1.31-alpine` (PR #11)
- [x] `docker-compose.yml`: `node:18-alpine` → `node:22-alpine`
- [x] `trivy` → `Imaj (frontend)`: OS EOSL=false (PR #11 koşusunda doğrulandı)

### P3: Zorunlu status check'ler ✅ (2026-10-08)
- [x] `main-koruma` ruleset'ine zorunlu check eklendi: `Backend (Django testleri)`, `Frontend (Vite build)`, `Helm / Compose dogrulama`, `dependency-review`, `gitleaks`; `strict` (dal `main` ile güncel olmalı), PR zorunlu (0 onay; tek geliştirici), bypass yok, merge yöntemi merge/squash
- Etkisi: Testi kırmızı PR merge edilemez. `main`'e doğrudan push kapandı, her değişiklik PR'dan geçer (Dependabot dahil). Yerel akış: dal → push → `gh pr create` → check'ler yeşil → `gh pr merge --merge`

### P4: Bulgu triajı ✅ (2026-10-08)
Alert'lerin çoğu yükseltmelerle kendiliğinden kapandı; 2026-10-08 itibarıyla Dependabot 0, secret scanning 0, code scanning'de Trivy/CodeQL/gitleaks/zizmor açık bulgu yok.
- [x] Eski Trivy kategorisi: açık alert kalmadı (2026-09-22 temizliği)
- [x] CodeQL: açık alert kalmadı
- [x] Trivy misconfig (Helm/k8s): Faz B2 chart 2.0.0 ile kapandı (securityContext, salt okunur kök, resource limit)
- [x] Scorecard triajı (2026-10-08): 11 bulgudan 9'u gerekçeli dismiss — pip hash-pinning ×4 (won't fix: `requirements.txt` sürümle sabit, Dependabot günceller, hash bakım yükü kabul edilmedi), `$/.github/actions/setup-trivy` ×2 (false positive: repo içi composite action, binary sabit sürüm+SHA256), CodeReview/Fuzzing/CII (won't fix: tek geliştirici, fuzz hedefi yok, rozet hedef değil); `source-map-js` 1.2.1→1.2.2 lock-only fix (`c05ac5a`, GHSA-68fv-2mgg-jv7q); BranchProtection → P3 ile kapatıldı
- [x] `docker-compose.yml` içindeki `SECRET_KEY=your-secret-key-here...` placeholder'ını `.env` dosyasına taşı
- [x] **Varsayılan SECRET_KEY ile deploy riski:** `helm/tech-radar/values.yaml`, `values.yaml`, `k8s/02-secret.yaml` ve README'de örnek (Türkçe cümle) `SECRET_KEY` değerleri var. Bunlarla deploy edilirse anahtar herkesçe bilinir (session/CSRF imzası taklit edilebilir). Çözüm:
  - helm: `secretKey` boş, template'te `required` ✅
  - helm: `dbPassword` da `required`; ayrı `postgresPassword` kaldırıldı (tek parola) ✅ (Faz B2, ADR-0007)
  - k8s: `02-secret.yaml` → `02-secret.yaml.example` ✅ (uzantı `.yaml` ile bitmez: `kubectl apply -f k8s/` onu atlar)
  - `settings.py`: `DEBUG=False` iken boş/örnek/zayıf `SECRET_KEY` ile açılmayı reddeder ✅ (`cybernews/ayar_dogrulama.py`)
  - `.gitleaksignore` **değiştirilmedi**: girdiler geçmiş commit'lere sabitli; silinirse geçmiş taraması yeniden kırmızı olur. (İlk plandaki "baseline'dan da silinmeli" maddesi bu yüzden geçersiz.)

### P5: Görünürlük
- [x] ZAP sonucunu SARIF'e çevirip Security sekmesine yükle; tek kontrol yeri Security olsun — `scripts/zap_sarif.py` (stdlib; alert tipi = kural, instance = sonuç, konum `dast/<url-yolu>` (Code Scanning `http` şemalı konum kabul etmiyor; tam URL mesajda), `security-severity` High 8.0 / Medium 5.0 / Low 3.0 / Info 1.0, kararlı `partialFingerprints`; kural anahtarı `alertRef`, alt kurallar ayrı), 10 birim testi `news/tests/test_zap_sarif.py`; `upload-sarif` kategori `zap-baseline` (2026-10-08). İlk yükleme 70 sonuç / 11 kural (10 medium: Cross-Domain Misconfiguration, CSP yok; 60 low). Gürültü `.zap/rules.tsv` ile IGNORE: 90005 Sec-Fetch-*, 10049 Non-Storable, 10111/10112 Auth/Session Identified, 10094 Base64 (csrf token). Dikkat: ZAP'ın kural dosyası yalnız konsol özetini ve çıkış kodunu etkiler, JSON rapora IGNORE'lar yine girer; bu yüzden `zap_sarif.py --kurallar .zap/rules.tsv` aynı dosyayı okuyup SARIF'e almaz. Gerçek bulgu listeye eklenmez, Security'de dismiss edilir
- [ ] Haftalık güvenlik özeti: araç × severity tablosuyla GitHub Issue açan bir workflow
- [ ] A5 (OpenAPI şeması) çıkınca `zaproxy/action-api-scan` ile `/api/v1/` tam taransın

## 5. Geçmiş
- **2026-09-13:** PR #3 ile güvenlik hattı kuruldu. SOOS DAST (bozuk, ücretli) kaldırıldı. Saat dilimine bağlı kırmızı olan test düzeltildi (`timezone.localdate()`).
- **2026-09-13:** Dependabot alerts + security updates, private vulnerability reporting ve `main` ruleset (silme/force-push engeli) açıldı.
- **2026-09-14:** PR #4 (`djangorestframework` 3.14.0 → 3.17.2) ve PR #6 (`lxml` 5.3.0 → 6.1.0, XXE düzeltmesi) yeni CI ile, birlikte 140/140 test yeşil doğrulanıp merge edildi.
- **2026-09-14:** P0 triajı tamamlandı: #24 ve #11 merge edildi, #5 ve #25 kapatıldı → P1.
- **2026-09-14:** gitleaks `main`'de #3'ten beri her push'ta kırmızıydı. Sebep workflow hatası: runner `bash -e` ile koştuğu için rapor modunda sızıntı bulununca adım erken ölüyordu. `set +e` ile düzeltildi. Bulunan 5 bulgunun hepsi placeholder `SECRET_KEY`; `.gitleaksignore`'a baseline olarak eklendi, deploy riski P4'te.
- **2026-09-22:** Güvenlik temizliği: P1 ve P2 uygulandı, Dependabot 14 → 0, code scanning 89 → 11 (ayrıntı: superpowers/specs/2026-09-22-guvenlik-temizligi-design.md).
- **2026-09-30:** PR #43 (Django 5.2.17) merge. P4 SECRET_KEY/ALLOWED_HOSTS koruması (superpowers/specs/2026-09-30-hizli-isler-design.md).
- **2026-10-03:** Faz B: SQLite → paylaşılan yerel PostgreSQL geçişi (B1) ve Helm chart 2.0.0 yerel docker-desktop doğrulaması (B2, ADR-0007). CI'a chart sürüm/imaj etiket kapıları ve kubeconform eklendi; DAST PostgreSQL ile çalışır.
- **2026-10-08:** Dependabot PR #46/#47/#48 (nginx ve node digest, actions grubu) merge. P4 Scorecard triajı: 9 gerekçeli dismiss + `source-map-js` düzeltmesi (`c05ac5a`). P3: `main-koruma` ruleset'ine PR zorunluluğu ve 5 zorunlu check (strict, bypass yok) eklendi; `main`'e doğrudan push kapandı.
- **2026-10-08:** P5-a: ZAP baseline raporu SARIF'e çevrilip Security → Code scanning'e yükleniyor (`scripts/zap_sarif.py`, kategori `zap-baseline`).
