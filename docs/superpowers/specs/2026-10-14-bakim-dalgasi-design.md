# Bakım Dalgası 2026-10: Düzeltmeler ve Geliştirmeler — Tasarım

> Tarih: 2026-10-14. Kaynak: 2026-10-13 geliştirme tavsiyesi turu (durum doğrulaması + öncelik listesi;
> hafıza `gelistirme-oncelikleri-2026-10-13`, Obsidian Daily 2026-10-13 17:14). Durum: plan yazıldı,
> uygulama kullanıcı onayı bekliyor. Uygulama planı: `docs/superpowers/plans/2026-10-14-bakim-dalgasi.md`.

## 1. Amaç

Güvenlik fazı (P5-c hariç) ve Faz B kapandıktan sonra doğrulanan dört işletme boşluğunu kapatmak, kalan
güvenlik işini (P5-c) bitirmek ve bir sonraki ürün turundan önce kalite tabanını (frontend testi, Python
linter/coverage) kurmak. Ürün özellikleri bu dalgada **yok** (bkz. §3).

**Başarı ölçütü:** dalga bitince (1) haftalık PostgreSQL yedeği alınıyor ve geri yüklenebildiği
kanıtlanmış; (2) docker-desktop K8s ortamı `main` ile aynı imajı çalıştırıyor; (3) 48 kaynağın hiçbiri
yanlış "sessiz" değil, ölü üçü listede değil; (4) `/api/v1/` ZAP ile taranıyor ve Security sekmesi 0
açık uyarı; (5) frontend'in test komutu CI'da koşuyor; (6) `ruff` ve coverage eşiği CI'da.

## 2. Doğrulanmış durum (2026-10-13/14)

| Ölçüm | Değer | Kaynak |
|---|---|---|
| `main` | `50c17ec` = `origin/main`, ağaç temiz, açık PR 0, son koşular yeşil | `git`, `gh` |
| Kayıt | 8.229 (CVE 6.541), DB 37 MB | `manage.py shell` |
| FetchRun son 14 gün | 441 başarılı / 16 başarısız (hepsi bilinen: SQLite kilidi, interrupted, FieldError) | DB |
| Sessiz kaynak (fetched=0, son 8 tur) | MinIO, MongoDB, RabbitMQ, CIRCL, KDnuggets | DB `by_source` |
| MongoDB canlı | **çalışıyor**: 2026-10-14 05:01 turunda fetched=3 (tag'ler 10-13 19:00Z'de geldi) | DB |
| RabbitMQ canlı | **çalışıyor**: son sürüm v4.3.6 2026-09-14, devtools penceresi 30 gün → 0 olağan | GitHub API |
| MinIO | upstream son sürüm 2025-10-16; bir yıldır yok | GitHub API |
| CIRCL `/api/last/50` | 50/50 PYSEC/GHSA, `published` 2024-11..2025-03 → 7 günlük pencerede hep 0 | canlı istek |
| KDnuggets | 403 (tüm UA'lar); DB'de 1 kayıt (2026-08-31) | hafıza + DB |
| Code scanning | 16 açık, hepsi ZAP: 5× `10055-6` style-src, 7× `10031` login XSS, 4× `10010` csrftoken HttpOnly | `gh api` |
| Dependabot | 0 açık | `gh api` |
| PostgreSQL yedeği | **hiç alınmamış**: `yerel-platform/yedekler/` yalnız `vault-20261004-003702.snap`; zamanlanmış görev yok | dosya sistemi, `Get-ScheduledTask` |
| K8s (docker-desktop) | imaj `2026.10.2`, `chart-2.1.1`; `main` Chart 2.2.0 / appVersion 2026.10.2; `chart-2.2.0` etiketi yok → PR #57–#62 kodu K8s'te yok | `kubectl`, `git tag` |
| `.env` | yalnız `GEMINI_API_KEY`, `SECRET_KEY`, `DB_PASSWORD`; `GITHUB_TOKEN`/`NVD_API_KEY` boş | `.env` anahtar adları |
| Çeviriden vazgeçilen (attempts ≥ 5) | 27: news 13 (SecurityWeek 9), k8s 5, devtools 5, ai 4; 15'i > 12.000 karakter (GEMINI_MAX_CHARS) | DB |
| Frontend test | yok (yalnız ESLint + build) | `package.json` |
| Python linter/coverage | yok; `ruff --select F` 34 bulgu (26 F401, 5 F841, 3 F541); tüm kurallarla 489 | `ruff 0.17.0` |
| `requirements_docker.txt` | ölü Flask kalıntısı (hiçbir yerden okunmuyor) | `grep` |
| Kök artıklar | `CyberNews/` altında iki Eylül SQLite yedeği (13 MB), `;W`, `test.py`, `test_browser.py`; repo içinde `C:` (17 MB bind-mount artığı, içinde hassas `.fazb/dump.json`) ve `helm;C` — git ikisini görmüyor | `ls`, `git status --ignored` |

## 3. Kapsam

**Bu dalga (sırayla):** PostgreSQL yedek döngüsü · kaynak turu 2 · Vitest altyapısı · sağlık şeridi ·
çeviri kalıntıları · ZAP triyajı · P5-c v1 API ZAP · Python kalite kapısı · K8s sürümü 2026.10.3 ·
yerel hijyen.

**Kapsam dışı (bilinçli):**
- Ürün özellikleri: CVE önceliklendirme (EPSS + KEV + DevTools yığını eşlemesi), PostgreSQL tam metin arama,
  günlük Türkçe özet çıkışı. Ayrı brainstorming + spec ister; bu dalga kalite tabanını hazırlar.
- Platform adayları (README "Aday"): Vault dinamik PostgreSQL kimliği, Argo CD ApplicationSet, Image Updater.
- Dependabot için PAT: hayır (uyarı 0; güvenlik PR'ları zaten PR listesinde; rotasyon yükü).
- `style-src 'unsafe-inline'` için nonce'lu şablon override: hayır (D8).
- `GEMINI_MAX_CHARS` üstü kayıtlar için parçalı/özetli Gemini çevirisi: hayır (D10).
- Compose frontend servisinde `npm install` → `npm ci`: hayır (her yeniden başlatmada tam kurulum; lockfile
  zaten `npm install` ile korunuyor).

## 4. Kararlar

### D1. PostgreSQL yedek döngüsü (yerel-platform)
Haftalık `pg_dumpall` (mevcut `scripts/yedekle.sh`), en yeni 8 yedek saklanır, her yedekten sonra
**geri yükleme provası** (geçici konteyner, satır sayıları canlıyla karşılaştırılır, konteyner silinir).
Görev Zamanlayıcı: `yerel-platform PostgreSQL yedek`, Pazar 10:00, `StartWhenAvailable` (makine kapalıysa
ilk açılışta). Yedek önce `.part` adıyla yazılır, `gzip -t` ve boyut kontrolünden sonra adlandırılır; yarım
dosya asla "en yeni yedek" olmaz. Log: `yedekler/yedek.log` (git dışı). **Gerekçe:** veri tek Docker
volume'unda; SQLite yedeği 10-03'te silindi; geri yüklenemeyen yedek yedek değildir.

### D2. K8s ortamı `main`'e getirilir — dalganın sonunda, tek sürüm
`appVersion 2026.10.3`, chart `2.2.1` (PATCH: yalnız appVersion), `chart-2.2.1` etiketi, `yerel-gitops`
`targetRevision` güncellemesi, Argo CD otomatik sync, `k8s_dogrulama.sh t6`. Dalganın **sonunda** yapılır
ki tek imajla tüm değişiklikler K8s'e gitsin (iki sürüm yerine bir). K8s paralel deneme ortamıdır, canlı
compose'tur; gecikme risk değil. **Gerekçe:** README "Surumleme" kuralları; ADR-0008 akışı.

### D3. Kaynak turu 2: üç kaynak çıkar, iki kaynak girer (48 → 47)
- Çıkar: **KDnuggets** (403, 43 gündür 0), **MinIO** (upstream bir yıldır sürüm yok), **CIRCL**
  (`/api/last` artık yalnız PYSEC/GHSA ve eski `published` döndürüyor; NVD + GitHub Advisory aynı veriyi
  kapsıyor).
- Ekle (2026-10-14 canlı doğrulandı: HTTP 200, güncel): **Ars Technica AI** (`arstechnica.com/ai/feed/`,
  RSS, 20 madde, günlük) ve **Import AI** (`importai.substack.com/feed`, RSS, haftalık bülten).
- MongoDB ve RabbitMQ **kalır** (çalışıyorlar; sorun sessizlik ölçüsünde, D4).
- Bölüm sayıları: news 12, cve 5, kubernetes 3, sre 5, devtools 13, ai 9.

### D4. Sessizlik ölçüsü kadans farkındalığı kazanır
Mevcut kural (ardışık `SOURCE_SILENT_RUNS`=4 tur fetched=0) seyrek yayınlayan kaynaklarda yanlış pozitif
veriyor (RabbitMQ aylık yama, MongoDB tag kadansı). Yeni kural: `silent = zero_runs >= eşik VE (hiç kayıt
yok VEYA son kayıt beklenen aralıktan eski)`. Beklenen aralık: kaynak başına tablo
(`BEKLENEN_ARALIK_GUN`, örn. RabbitMQ 60, Moodle/Ceph 90), tabloda olmayan kaynak için bölümün çekim
penceresi (`BOLUM_PENCERESI_GUN`: news/cve 7, diğerleri 30). Status ucu iki yeni alan verir:
`expected_gap_days`, `days_since_record`. Mevcut testler değişmez (fixture'larda kayıt yok → sessiz).

### D5. `GITHUB_TOKEN` ve `NVD_API_KEY` compose `.env`'e (kullanıcı), K8s'e değil
Değerler yalnız `.env`'e yazılır (git dışı), hiçbir dosyaya/loga basılmaz. K8s tarafında chart 2.2.0
`secrets.githubToken/nvdApiKey` `optional: true` ile zaten hazır; Vault'a yazılması ayrı küçük iş,
bu dalgada değil.

### D6. Sağlık şeridi: anonim `GET /api/saglik/`, ana sayfada
`/api/v1/status/` token ister; arayüz anonimdir. Yeni uç **dar**dır: bölüm başına `last_success_at`,
`last_status`, `pending_translation`, `translation_given_up`, `silent_sources`. Toplamlar, kaynak başına
ayrıntı, `by_provider`, `error` **yok** (operatör verisi v1/status ve admin'de kalır). 60 sn cache
(`kaynak_durumlari` bölüm başına FetchRun + `Max(created_at)` sorgusu yapar). Ana sayfada altı kutu:
bölüm adı, "N sa önce", yeşil `ok` / kırmızı `N sessiz` veya `son tur hatalı`. 5 dk'da bir
`useAraliklaYenile` ile yenilenir. **Gerekçe:** curl rutini 10-08'den beri işlememiş; kullanıcı arayüze
her gün bakıyor.

### D7. Vitest altyapısı
`vitest` + `jsdom` + `@testing-library/react` + `@testing-library/jest-dom`; `npm test` = `vitest run`;
CI `Frontend (Vite build)` işine lint ile build arasında adım (yeni zorunlu check **yok**, ruleset
değişmez). İlk testler: `utils/html.js` (XSS kaçışı — şu an yalnız backend'den dolaylı sınanıyor),
`hooks/useAraliklaYenile`, `CeviriEtiketi`, `utils/zaman`, `SaglikSeridi`. ESLint test dosyalarında
`globals.vitest` tanır.

### D8. ZAP triyajı: 16 uyarı gerekçeli kapanır
- 7× `10031` (login formu XSS adayı): **false positive** — Django alanı escape eder, çalışan payload yok.
- 4× `10010` (csrftoken HttpOnly): **won't fix** — axios `xsrfCookieName` ile okur; token gizli değil.
- 5× `10055-6` (style-src unsafe-inline): **won't fix** — Django admin ve Swagger UI şablonları inline
  `style=` **attribute** kullanır; CSP nonce yalnız `<style>` elemanlarını kapsar, attribute'ları
  kapsamaz. `script-src` nonce'lu; XSS vektörü değil. Yorum ≤ 280 karakter (GitHub sessizce reddeder).
Dismiss edilen uyarı aynı parmak iziyle yeniden açılmaz; haftalık özet Issue'su kapananları sayar.

### D9. P5-c: `/api/v1/` ZAP API taraması, aynı DAST işinde
- Şema: `manage.py spectacular --file` (API konteynerinde, kimlik gerekmez) → `schema.yml`.
- Kimlik: CI DB'sinde geçici `zap-dast` kullanıcısı + token; token `::add-mask::` ile maskelenir,
  `.zap/api-token.txt` dosyasına yazılır (gitignore `*.txt`), tarama sonrası silinir.
- Enjeksiyon: `.zap/api_hooks.py` `zap_started` kancası `replacer` kuralıyla `Authorization: Token …`
  ekler (ZAP'ın `--hook` mekanizması; env geçişi gerekmez).
- Hedef: `zaproxy/action-api-scan@v0.10.0` (SHA pinli), `-O http://localhost:8000` (spectacular
  `servers` üretmez), `-a`, `.zap/rules.tsv`.
- Throttle: `V1_THROTTLE_READ`/`V1_THROTTLE_REFRESH` ortam değişkenleri (yeni; varsayılan 120/min,
  12/hour) DAST konteynerinde gevşetilir; aksi halde tarama 429'a boğulur.
- Çıktı: rapor modu; `zap_sarif.py` ile SARIF, kategori **`zap-api`**; `/api/v1/` adresi raporda yoksa
  iş kırmızı (boş hedefe yeşil yok, ADR-008 ilkesi).
- Aktif tarama `/api/v1/refresh/` POST'larını tetikler: CI'da worker yok, Celery kuyruğu Redis'te kalır;
  zararsız.

### D10. Çeviri kalıntıları
- `GEMINI_MAX_CHARS` (12.000) üstü 15 kayıt ve yankı/kırpılma doğrulamasını geçemeyen 12 kayıt
  **İngilizce kalır**; parçalı Gemini çevirisi tasarım işi, bu dalgada değil. Obsidian görevi
  `cybernews-uzun-k8s-kaydi-karari` bu kararla kapanır.
- Arayüz dürüst olur: `needs_translation=true` ve `translation_provider=''` kayıtlar "Çevrilmedi: orijinal
  metin" rozeti alır (şu an rozetsiz İngilizce gösteriliyor).
- Admin'de altı modelde "Çeviri denemelerini sıfırla" eylemi (`translation_attempts=0`,
  `needs_translation=True`): kök neden giderildiğinde seçili kayıtlar yeniden kuyruğa alınır.

### D11. Python kalite kapısı
`requirements-dev.txt` (`ruff==0.17.0`, `coverage==7.16.2`), `pyproject.toml` ile `ruff` **yalnız `F` ve
`E9`** (hata sınıfı; stil kuralları 489 bulgu veriyor, ayrı PR), 34 bulgu düzeltilir. CI Backend işinde
`ruff check .` ve `coverage run manage.py test` + `coverage report --fail-under`; eşik ilk ölçümden 2 puan
altına sabitlenir. `requirements_docker.txt` silinir.

### D12. Yerel hijyen
Repo dışı artıklar silinmez, `_arsiv/2026-10-14-kok-temizlik/` altına taşınır (SQLite yedekleri,
`test.py`, `test_browser.py`); boş `;W` silinir. Repo içi `C:` ve `helm;C` silinir (`cmd /c rd /s /q`,
tam yol; MSYS `rm -rf "C:"` **çalışma dizinini** siler — hafıza 2026-10-09). Her silme kullanıcı onayıyla.

## 5. Doğrulama

| Karar | Gözlemlenebilir çıktı |
|---|---|
| D1 | `tests/yedek_dondurme_test.sh` GEÇTİ; `scripts/yedek_prova.sh` "GECTI"; `Get-ScheduledTask` görev `Ready`; elle `Start-ScheduledTask` sonrası `yedekler/yedek.log` "bitti" ve yeni `.sql.gz` |
| D2 | `chart etiketi` iş akışı yeşil; Argo `Synced/Healthy`, `status.sync.revision` = `chart-2.2.1`; pod imajları `2026.10.3`; worker logunda `[FetchRun] Acilis:`; `k8s_dogrulama.sh t6` GEÇTİ |
| D3 | `test_kayit_defterleri_toplam_47_kaynak`; canlı `by_source`'ta `Ars Technica AI`/`Import AI` fetched > 0; README/ana sayfa sayıları |
| D4 | Yeni testler: RabbitMQ 29 gün → sessiz değil, 61 gün → sessiz, Dark Reading 10 gün → sessiz; canlı `/api/v1/status/` `silent_sources` RabbitMQ/MongoDB içermez |
| D5 | `docker compose exec teknoloji-worker sh -c 'test -n "$GITHUB_TOKEN" && echo tanimli'` |
| D6 | `test_saglik.py` 4 test; tarayıcıda ana sayfa şeridi; `curl -s localhost:8000/api/saglik/` tokensiz 200 |
| D7 | `npm test` yeşil; CI Frontend işinde "Testler (Vitest)" adımı |
| D8 | `gh api .../code-scanning/alerts?state=open` → 0 |
| D9 | DAST koşusunda step summary "ZAP API (/api/v1/)" tablosu; Security → Code scanning'de `zap-api` kategorisi; yerel kuru koşu raporunda `/api/v1/status/` 200 |
| D10 | Admin eylemi testi; `CeviriEtiketi` testi; arayüzde SecurityWeek #823 rozetli |
| D11 | CI Backend "ruff (F, E9)" adımı yeşil; coverage özeti; `requirements_docker.txt` yok |
| D12 | `ls CyberNews/` ve `ls cybersecurity_news/` temiz; `git status` temiz |

## 6. Riskler

- **Vitest/Vite uyumu:** Vite 6.4 ile `vitest@4` eşleşir; `npm ls vite vitest` peer hatası verirse
  Vite 7'ye geçiş ayrı PR (Dependabot major'ları filtreler).
- **`ruff --fix` yanlış pozitifi:** `cybernews/__init__.py` `__all__` ile re-export yapar; diff gözle
  incelenir, tam test koşusu şart.
- **ZAP API aktif taraması canlıya değil, CI'daki tek kullanımlık DB'ye** gider; yerel kuru koşu canlı
  compose'a gider ve 12/hour refresh sınırı yüzünden 429 üretir — beklenir, token'ın çalıştığını kanıtlar.
- **K8s imaj görünürlüğü:** 2026.10.2 `pullPolicy: Never` ile çalıştı; aynı yol.
- **Yedek provası canlı sunucuya yalnız `count(*)` sorar;** geçici konteyner `yedek-prova` her çıkışta
  silinir (`trap`).
