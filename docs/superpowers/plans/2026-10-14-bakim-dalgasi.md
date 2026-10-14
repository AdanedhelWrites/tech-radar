# Bakım Dalgası 2026-10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Doğrulanmış dört işletme boşluğunu (yedek yok, K8s geride, yanlış sessiz kaynaklar, boş token'lar) kapatmak, P5-c'yi bitirmek ve frontend/Python kalite kapılarını kurmak; ürün özelliği yok.

**Architecture:** On görev, üç repo: `yerel-platform` (yedek), `tech-radar` (uygulama, CI, docs), `yerel-gitops` (K8s sürüm pini). Her `tech-radar` görevi ayrı dal + PR + 5 zorunlu check; K8s sürümü dalganın sonunda tek imajla. Kod ASCII Türkçe, belgeler diakritikli.

**Tech Stack:** Django 5.2 / DRF 3.18 / Celery (Python 3.11), React 18 + Vite 6 + Vitest 4, Helm 2.2.x + Argo CD (docker-desktop), GitHub Actions (SHA pinli), ZAP, Bash (Git Bash), PowerShell (Görev Zamanlayıcı).

**Spec:** `docs/superpowers/specs/2026-10-14-bakim-dalgasi-design.md`

## Global Constraints

- `main` korumalı: her değişiklik `git checkout -b <tur>/<slug>` → commit → `git push -u origin <dal>` → `gh pr create --repo AdanedhelWrites/tech-radar` → 5 check yeşil → `gh pr merge <n> --merge --delete-branch` → `git checkout main && git pull --ff-only`. `gh` komutlarında `MSYS_NO_PATHCONV=1`.
- Commit mesajı ASCII Türkçe, sonunda boş satır + `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Kod ve yorumlar ASCII Türkçe (diakritik yok); `docs/*.md` ve `README.md` mevcut biçimlerini korur (README ASCII).
- Sır değeri hiçbir dosyaya, loga, ekrana, commit'e girmez. Token/parola yalnız `.env`, `.zap/api-token.txt` (git dışı, iş sonunda silinir) ve `yedekler/` (git dışı).
- Küme komutları yalnız `kubectl --context docker-desktop` / `k()`; `aks-gokbulut`'a asla komut gitmez. Registry push, GitHub Release yok; yalnız `chart-*` etiketi.
- **Kullanıcı onayı gereken adımlar** (dur ve sor): `git push`, `git tag` + push, `gh pr merge`, GitHub uyarı dismiss, Görev Zamanlayıcı kaydı, her silme (Task 10), ZAP imajı çekimi (~1,5 GB), `.env`'e token yazma (kullanıcı kendisi yazar).
- Action SHA'ları mevcut dosyalardan kopyalanır: `step-security/harden-runner@e14015d583714f6e62063499dc959a02595150a1 # v2.21.1`, `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`, `github/codeql-action/upload-sarif@2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2 # v4.38.2`; yeni: `zaproxy/action-api-scan@5158fe4d9d8fcc75ea204db81317cce7f9e5453d # v0.10.0`.
- Helm: `helm/tech-radar/` altındaki her değişiklik `Chart.yaml version` artırır ve `CHANGELOG.md` `## [surum]` ister (`scripts/chart_surum_kontrol.sh`).
- Testler: backend `scripts/pg_test.sh test news --noinput` (CI ile aynı yol) ya da `docker compose exec teknoloji-api python manage.py test news.tests.<modul> --noinput`; frontend `cd frontend && npm test`; yerel-platform `bash tests/<ad>_test.sh`.
- Bash aracında `\` sadeleşir: ters bölülü içerik (Windows yolu, regex) Write/Edit ile yazılır.
- Review politikası: rutin görevlerde subagent review yok; riskli diff (kullanıcı girdisi, HTML/XSS, kimlik) için açılır (Task 4 backend ucu, Task 7).

## Review Focus

1. **Yarım yedek dosyası:** Docker kapalıyken `yedekle.sh` boş `.sql.gz` bırakırsa prova onu "en yeni yedek" sanır → Task 1 Step 3 `.part` + `gzip -t` + boyut eşiği; Step 9 `KONTEYNER=yok` ile sınanır.
2. **Seyrek kaynak yanlış sessiz:** RabbitMQ 30 günlük pencerede 0 döner ama canlıdır → Task 2 Step 6 testleri (29 gün → değil, 61 gün → sessiz).
3. **`kacis` dize olmayan girdi:** sayı/`null`/`undefined` → Task 3 Step 3 `html.test.js`.
4. **Sağlık ucu bilgi sızdırması:** anonim uç `sources`, `total`, `error` taşımamalı → Task 4 Step 2 `test_operator_alanlari_sizmaz`.
5. **ZAP API taraması token'sız "yeşil":** token dosyası yoksa kanca patlamalı, raporda `/api/v1/` yoksa iş kırmızı → Task 7 Step 6 "API hedefi gerçekten tarandı mı".

---

### Task 1: PostgreSQL yedek döngüsü (repo: `yerel-platform`)

**Files:**
- Create: `scripts/yedek_ortak.sh`
- Modify: `scripts/yedekle.sh`
- Create: `scripts/yedek_prova.sh`
- Create: `scripts/yedek_otomatik.sh`
- Create: `tests/yedek_dondurme_test.sh`
- Modify: `.github/workflows/ci.yml` (Testler adımı)
- Modify: `README.md` "Yedek ve geri yukleme"

**Interfaces:**
- Produces: `eski_yedekleri_sil <dizin> <onek> <sakla>` (Bash fonksiyonu, `yedek_ortak.sh`); `scripts/yedek_prova.sh [yedek.sql.gz]` çıkış 0 = GEÇTİ; `scripts/yedek_otomatik.sh` (Görev Zamanlayıcı hedefi).
- Consumes: `yerel-postgres` konteyneri (`docker exec … pg_dumpall -U postgres`, unix soketi parola istemez).

- [ ] **Step 1: Dal aç**

```bash
cd /c/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform && git checkout -b feat/pg-yedek-dongusu
```

- [ ] **Step 2: Döndürme testini yaz (kırmızı)** — `tests/yedek_dondurme_test.sh`

```bash
#!/usr/bin/env bash
# yedek_ortak.sh eski_yedekleri_sil testleri. Docker'a ve kumeye dokunmaz.
#   tests/yedek_dondurme_test.sh
set -uo pipefail
. "$(dirname "$0")/../scripts/yedek_ortak.sh"

basarisiz=0
esit() {   # esit <aciklama> <gelen> <beklenen>
  if [ "$2" = "$3" ]; then echo "ok    $1"; else echo "HATA  $1"; echo "      gelen:    $2"; echo "      beklenen: $3"; basarisiz=1; fi
}
say() { ls -1 "$D"/yerel-postgres-*.sql.gz 2>/dev/null | wc -l | tr -d ' '; }

D=$(mktemp -d); trap 'rm -rf "$D"' EXIT
for i in 01 02 03 04 05 06 07 08 09 10; do : > "$D/yerel-postgres-202610${i}-030000.sql.gz"; done
: > "$D/yerel-postgres-20261011-030000.sql.gz.part"
: > "$D/vault-20261004-003702.snap"

eski_yedekleri_sil "$D" yerel-postgres- 8 > /dev/null
esit "8 yedek kalir" "$(say)" 8
esit "en yeni kalir" "$(ls -1 "$D"/yerel-postgres-*.sql.gz | sort | tail -1 | xargs basename)" yerel-postgres-20261010-030000.sql.gz
esit "en eski iki silinir" "$(ls "$D"/yerel-postgres-20261001-030000.sql.gz "$D"/yerel-postgres-20261002-030000.sql.gz 2>/dev/null | wc -l | tr -d ' ')" 0
esit ".part ve snap dosyalarina dokunmaz" "$(ls "$D"/*.part "$D"/*.snap | wc -l | tr -d ' ')" 2

eski_yedekleri_sil "$D" yerel-postgres- 8 > /dev/null
esit "ikinci kosu bir sey silmez" "$(say)" 8

eski_yedekleri_sil "$D" yerel-postgres- 0 2>/dev/null
esit "sakla=0 reddedilir, dosya kalir" "$(say)" 8

rm -f "$D"/yerel-postgres-*.sql.gz
eski_yedekleri_sil "$D" yerel-postgres- 8 > /dev/null
esit "yedek yokken hata vermez" "$?" 0

if [ "$basarisiz" = 0 ]; then echo "GECTI yedek_dondurme"; else echo "KALDI yedek_dondurme"; exit 1; fi
```

- [ ] **Step 3: Testi koş, kırmızı gör**

Run: `bash tests/yedek_dondurme_test.sh`
Expected: `scripts/yedek_ortak.sh: No such file or directory` ile çıkış ≠ 0.

- [ ] **Step 4: `scripts/yedek_ortak.sh` yaz**

```bash
#!/usr/bin/env bash
# Yedek betiklerinin ortak parcasi (yedekle.sh, tests/yedek_dondurme_test.sh). Yalniz dosya sistemi.

# eski_yedekleri_sil <dizin> <onek> <sakla>
# <dizin>/<onek>*.sql.gz dosyalarindan en yeni <sakla> tanesini birakir, gerisini siler.
# Dosya adi tarih tasidigi icin ad sirasi = zaman sirasi. .part (yarim yedek) ve baska dosyalara dokunmaz.
eski_yedekleri_sil() {
  local dizin=$1 onek=$2 sakla=$3 dosyalar
  [ "$sakla" -ge 1 ] 2>/dev/null || { echo "eski_yedekleri_sil: sakla >= 1 olmali ($sakla)" >&2; return 1; }
  dosyalar=$(ls -1 "$dizin"/"$onek"*.sql.gz 2>/dev/null | sort -r) || true
  [ -n "$dosyalar" ] || return 0
  printf '%s\n' "$dosyalar" | tail -n +"$((sakla + 1))" | while IFS= read -r eski; do
    [ -n "$eski" ] || continue
    rm -f -- "$eski" && echo "silindi: $eski"
  done
  return 0
}
```

- [ ] **Step 5: Testi koş, yeşil gör**

Run: `bash tests/yedek_dondurme_test.sh`
Expected: 7 `ok` satırı ve `GECTI yedek_dondurme`.

- [ ] **Step 6: `scripts/yedekle.sh`'yi yarım dosyaya karşı sağlamlaştır** (dosyanın tamamı)

```bash
#!/usr/bin/env bash
# Tum veritabanlarinin tam yedegi (pg_dumpall) -> yedekler/yerel-postgres-<tarih>.sql.gz
# Yedek kullanici parola hash'lerini ve uygulama verisini icerir: commit edilmez
# (.gitignore), paylasilmaz. Geri yukleme ve prova: README "Yedek ve geri yukleme".
#   scripts/yedekle.sh                    # yedek al; en yeni YEDEK_SAKLA (8) dosya kalir
#   YEDEK_SAKLA=12 scripts/yedekle.sh
#   KONTEYNER=yok scripts/yedekle.sh      # hata yolu provasi: dosya birakmadan cikis 1
# Yedek once .part adiyla yazilir; gzip butunlugu ve boyut esigi gecince adlandirilir.
# Boylece yarim/bos bir dosya asla "en yeni yedek" olmaz (prova ve dondurme .part'i gormez).
set -euo pipefail

cd "$(dirname "$0")/.."
. scripts/yedek_ortak.sh
umask 077
mkdir -p yedekler
KONTEYNER="${KONTEYNER:-yerel-postgres}"
hedef="yedekler/yerel-postgres-$(date +%Y%m%d-%H%M%S).sql.gz"
part="$hedef.part"
trap 'rm -f -- "$part"' EXIT

docker exec "$KONTEYNER" pg_dumpall -U postgres | gzip > "$part"
gzip -t "$part"
[ "$(wc -c < "$part")" -gt 1024 ] || { echo "yedek suphe verici kucuk: $part" >&2; exit 1; }
mv -- "$part" "$hedef"
echo "yedek: $hedef ($(du -h "$hedef" | cut -f1))"
eski_yedekleri_sil yedekler yerel-postgres- "${YEDEK_SAKLA:-8}"
```

- [ ] **Step 7: `scripts/yedek_prova.sh` yaz**

```bash
#!/usr/bin/env bash
# Yedek geri yukleme provasi: yedegi GECICI bir PostgreSQL konteynerine yukler, cybernews
# tablolarinin satir sayisini canli sunucuyla karsilastirir, konteyneri siler. Canliya yazmaz
# (yalniz count(*) sorar). Cikis 0 = GECTI.
#   scripts/yedek_prova.sh                          # en yeni yedek
#   scripts/yedek_prova.sh yedekler/<dosya>.sql.gz
set -euo pipefail
cd "$(dirname "$0")/.."

# docker-compose.yml ile ayni imaj ve digest
IMAJ="postgres:16.15-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea"
AD=yedek-prova
yedek="${1:-$(ls -1 yedekler/yerel-postgres-*.sql.gz 2>/dev/null | sort | tail -1)}"
[ -n "$yedek" ] && [ -s "$yedek" ] || { echo "KALDI yedek yok: ${yedek:-<bos>}" >&2; exit 1; }

temizle() { docker rm -f "$AD" >/dev/null 2>&1 || true; }
trap temizle EXIT
temizle
docker run -d --name "$AD" -e POSTGRES_PASSWORD=prova-gecici "$IMAJ" >/dev/null
for _ in $(seq 1 30); do
  docker exec "$AD" pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1 && break
  sleep 1
done
docker exec "$AD" pg_isready -h 127.0.0.1 -U postgres >/dev/null

# pg_dumpall "CREATE ROLE postgres" icerir; o hata beklenir, geri kalan ERROR satirlari sayilir
hatalar=$(gunzip -c "$yedek" | docker exec -i "$AD" psql -U postgres -d postgres -q 2>&1 >/dev/null \
  | grep -v 'role "postgres" already exists' | grep -c ERROR || true)
[ "$hatalar" = 0 ] || { echo "KALDI geri yuklemede $hatalar hata ($yedek)"; exit 1; }

basarisiz=0
for tablo in news_cveentry news_newsarticle news_ainewsentry news_fetchrun; do
  canli=$(docker exec yerel-postgres psql -U postgres -d cybernews -tAc "select count(*) from $tablo")
  prova=$(docker exec "$AD" psql -U postgres -d cybernews -tAc "select count(*) from $tablo")
  if [ "$canli" = "$prova" ]; then
    echo "ok    $tablo canli=$canli prova=$prova"
  else
    echo "fark  $tablo canli=$canli prova=$prova (yedekten sonra yazilan satirlar olabilir)"
  fi
  [ "$prova" -gt 0 ] || basarisiz=1
done
if [ "$basarisiz" = 0 ]; then echo "GECTI yedek provasi: $yedek"; else echo "KALDI yedek provasi: bos tablo"; exit 1; fi
```

- [ ] **Step 8: `scripts/yedek_otomatik.sh` yaz**

```bash
#!/usr/bin/env bash
# Gorev Zamanlayici hedefi (haftalik): Docker/yerel-postgres hazir olana kadar bekler (en fazla
# BEKLE_DK dk), yedek alir, provasini yapar. Cikti yedekler/yedek.log'a eklenir (sir icermez).
#   scripts/yedek_otomatik.sh        # elle deneme
# Gorev kaydi: README "Yedek ve geri yukleme".
set -uo pipefail
KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$KOK/yedekler"
LOG="$KOK/yedekler/yedek.log"
BEKLE_DK="${BEKLE_DK:-10}"
exec >>"$LOG" 2>&1
echo "=== $(date '+%F %T') basladi (bekleme siniri ${BEKLE_DK} dk)"

son=$(( $(date +%s) + BEKLE_DK * 60 ))
until docker exec yerel-postgres pg_isready -h 127.0.0.1 -U postgres >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$son" ]; then
    echo "$(date '+%F %T') yerel-postgres ${BEKLE_DK} dk icinde hazir olmadi; vazgecildi"
    exit 1
  fi
  sleep 20
done
bash "$KOK/scripts/yedekle.sh" || { echo "$(date '+%F %T') yedekle.sh basarisiz"; exit 1; }
bash "$KOK/scripts/yedek_prova.sh" || { echo "$(date '+%F %T') yedek_prova.sh basarisiz"; exit 1; }
echo "$(date '+%F %T') bitti"
```

- [ ] **Step 9: Gerçek yedek + hata yolu + prova**

Run:
```bash
KONTEYNER=yok scripts/yedekle.sh; echo "cikis=$?"; ls yedekler/
```
Expected: `cikis=1`, `yedekler/` içinde `.sql.gz` ya da `.part` **yok** (yalnız `vault-*.snap`).

Run:
```bash
scripts/yedekle.sh && scripts/yedek_prova.sh
```
Expected: `yedek: yedekler/yerel-postgres-<tarih>.sql.gz (…M)`, dört `ok`/`fark` satırı (prova > 0), `GECTI yedek provasi`. `docker ps -a --filter name=yedek-prova` boş.

- [ ] **Step 10: CI ve shellcheck** — `.github/workflows/ci.yml` Testler adımına `bash tests/yedek_dondurme_test.sh` satırını ekle (`bash tests/env_json_test.sh` satırından sonra). Yerelde:

```bash
docker run --rm -v "$(pwd -W):/mnt" -w /mnt koalaman/shellcheck:v0.11.0@sha256:61862eba1fcf09a484ebcc6feea46f1782532571a34ed51fedf90dd25f925a8d -x -S warning scripts/*.sh tests/*.sh
```
Expected: çıktı yok (uyarı sıfır).

- [ ] **Step 11: README "Yedek ve geri yukleme" bölümünü değiştir** (mevcut 2 satırlık blokun yerine)

```markdown
## Yedek ve geri yukleme

```bash
scripts/yedekle.sh                        # yedekler/yerel-postgres-<tarih>.sql.gz; en yeni 8 kalir (YEDEK_SAKLA)
scripts/yedek_prova.sh                    # en yeni yedegi gecici konteynere yukler, satir sayilarini canliyla karsilastirir
gunzip -c yedekler/<dosya>.sql.gz | docker exec -i yerel-postgres psql -U postgres -d postgres   # gercek geri yukleme
```

Haftalik otomatik yedek + prova (Gorev Zamanlayici, Pazar 10:00; makine kapaliysa ilk acilista;
log `yedekler/yedek.log`). Bir kez PowerShell'de:

```powershell
$bash  = 'C:\Program Files\Git\bin\bash.exe'
$betik = 'C:\Users\<kullanici>\Desktop\OpenCodeProjects\yerel-platform\scripts\yedek_otomatik.sh'
$eylem = New-ScheduledTaskAction -Execute $bash -Argument ('-l "' + $betik + '"')
$tetik = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 10:00
$ayar  = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName 'yerel-platform PostgreSQL yedek' -Action $eylem -Trigger $tetik -Settings $ayar -RunLevel Limited -Force
```

Yedek parola hash'lerini ve tum uygulama verisini icerir; `yedekler/` git'e girmez. Yedek once `.part`
olarak yazilir, `gzip -t` ve boyut esigi gecince adlandirilir; yarim dosya asla en yeni yedek sayilmaz.
```

- [ ] **Step 12: Görevi kaydet (KULLANICI ONAYI) ve bir kez elle çalıştır** — README'deki PowerShell bloğunu `<kullanici>` = `Adanedhel` ile çalıştır; sonra:

```powershell
Start-ScheduledTask -TaskName 'yerel-platform PostgreSQL yedek'; Start-Sleep 90; Get-Content 'C:\Users\Adanedhel\Desktop\OpenCodeProjects\yerel-platform\yedekler\yedek.log' -Tail 8
```
Expected: `basladi` … `yedek: …` … `GECTI yedek provasi` … `bitti`.

- [ ] **Step 13: Commit, push (ONAY), PR, merge**

```bash
git add scripts/yedek_ortak.sh scripts/yedekle.sh scripts/yedek_prova.sh scripts/yedek_otomatik.sh tests/yedek_dondurme_test.sh .github/workflows/ci.yml README.md
git commit -m "feat(yedek): haftalik pg_dumpall + dondurme + geri yukleme provasi + Gorev Zamanlayici

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Sonra `git push -u origin feat/pg-yedek-dongusu`, `MSYS_NO_PATHCONV=1 gh pr create --repo AdanedhelWrites/yerel-platform --fill`, CI yeşil → merge.

---

### Task 2: Kaynak turu 2 (repo: `tech-radar`)

**Files:**
- Modify: `news/ai_scraper.py:19-28` (KDnuggets çıkar, iki kaynak ekle)
- Modify: `news/devtools_scraper.py` (docstring 1-16, `MinIOScraper` sınıfı 84-121, `scrapers` sözlüğü 965)
- Modify: `news/cve_scraper.py` (`CIRCLScraper` sınıfı 585-~710, `MultiCVEScraper.__init__` 930/940)
- Modify: `news/kaynaklar.py` (kadans tablosu, `kaynak_durumlari`)
- Modify: `news/api_v1/schema.py:204-207` (`KaynakDurumuV1` iki alan)
- Modify: `news/tests/test_kaynak_sagligi.py` (sayılar + 3 yeni test + şema testi)
- Modify: `news/tests/test_kaynaklar.py` (yeni AI kaynağı testleri)
- Modify: `.env.example` (GITHUB_TOKEN açıklamasındaki MinIO), `README.md` (başlık sayıları 120/149/170, kaynak listeleri, satır 749, "Tamamlanan asamalar"), `frontend/src/App.jsx:118,168`

**Interfaces:**
- Produces: `kaynaklar.BOLUM_PENCERESI_GUN`, `kaynaklar.BEKLENEN_ARALIK_GUN`, `kaynaklar.beklenen_aralik(bolum, ad) -> int`; `kaynak_durumlari()` sözlüğünde yeni anahtarlar `expected_gap_days: int`, `days_since_record: int | None`. Task 4 `silent_sources`'u aynı fonksiyondan okur.
- Consumes: `news/tests/test_kaynak_sagligi.py::_tur(bolum, by_source, gun_once, status='success')` (mevcut yardımcı), `news/tests/test_kaynaklar.py::_rss/_item/SahteYanit/yonlendir` (mevcut).

- [ ] **Step 1: Dal aç** — `git checkout -b feat/kaynak-turu-2`

- [ ] **Step 2: Kayıt defteri testini güncelle (kırmızı)** — `news/tests/test_kaynak_sagligi.py` içinde `test_kayit_defterleri_toplam_48_kaynak`'ı şununla değiştir:

```python
    def test_kayit_defterleri_toplam_47_kaynak(self):
        # 2026-10-14: KDnuggets (403), MinIO (ust kaynak olu), CIRCL (/api/last artik CVE donmuyor) cikti;
        # Ars Technica AI ve Import AI girdi.
        beklenen = {'news': 12, 'cve': 5, 'kubernetes': 3, 'sre': 5, 'devtools': 13, 'ai': 9}
        for bolum, adet in beklenen.items():
            with self.subTest(bolum=bolum):
                self.assertEqual(len(kaynaklar.bolum_kaynaklari(bolum)), adet)
        self.assertIn('CISA KEV', kaynaklar.bolum_kaynaklari('cve'))
        self.assertIn('Bleeping Computer', kaynaklar.bolum_kaynaklari('news'))
        self.assertIn('Ars Technica AI', kaynaklar.bolum_kaynaklari('ai'))
        self.assertIn('Import AI', kaynaklar.bolum_kaynaklari('ai'))
        for bolum, ad in (('ai', 'KDnuggets'), ('devtools', 'MinIO'), ('cve', 'CIRCL')):
            self.assertNotIn(ad, kaynaklar.bolum_kaynaklari(bolum))
```

`news/tests/test_kaynaklar.py` sonuna ekle:

```python
class YeniAIKaynaklariTests(SimpleTestCase):
    """2026-10-14: KDnuggets yerine Ars Technica AI + Import AI (ikisi de RSS, canli dogrulandi)."""

    def test_ars_technica_rss_okunur_eski_elenir(self):
        from news.ai_scraper import AINewsScraper
        s = AINewsScraper('https://feed.test/ai', 'Ars Technica AI')
        rss = _rss([_item('Yeni model', 'https://ornek.test/yeni', 1, desc='Ozet metin'),
                    _item('Eski', 'https://ornek.test/eski', 45)])
        with mock.patch.object(s.session, 'get', side_effect=yonlendir({'https://feed.test/ai': SahteYanit(rss)})):
            entries = s.fetch_entries(days=30)

        self.assertEqual([e['source'] for e in entries], ['Ars Technica AI'])
        self.assertEqual(entries[0]['link'], 'https://ornek.test/yeni')
        self.assertEqual(entries[0]['title'], 'Yeni model')

    def test_ai_kayit_defteri_adresleri(self):
        from news.ai_scraper import MultiAINewsScraper
        s = MultiAINewsScraper().scrapers
        self.assertEqual(s['Ars Technica AI'].feed_url, 'https://arstechnica.com/ai/feed/')
        self.assertEqual(s['Import AI'].feed_url, 'https://importai.substack.com/feed')
        self.assertNotIn('KDnuggets', s)
```

Run: `docker compose exec teknoloji-api python manage.py test news.tests.test_kaynak_sagligi news.tests.test_kaynaklar --noinput`
Expected: 3 FAIL (`47` testi, iki yeni AI testi).

- [ ] **Step 3: Kaynakları çıkar ve ekle**

`news/ai_scraper.py` sözlüğünde `'KDnuggets': …` satırını sil; `'OpenAI Blog'` satırından sonra ekle:

```python
            # 2026-10-14: KDnuggets (tum UA'larla 403, 43 gun 0) yerine iki canli RSS
            'Ars Technica AI': AINewsScraper('https://arstechnica.com/ai/feed/', 'Ars Technica AI'),
            'Import AI': AINewsScraper('https://importai.substack.com/feed', 'Import AI'),
```

`news/devtools_scraper.py`: `# 1. MinIO — GitHub Releases API` başlığından `return entries`'e kadar `MinIOScraper` bloğunu sil; `self.scrapers` içindeki `'MinIO': MinIOScraper(),` satırını sil; modül docstring'inde `14 kaynak:` → `13 kaynak:` ve `- MinIO …` satırını sil, yerine `# 2026-10-14: MinIO cikarildi (ust kaynak Ekim 2025'ten beri surum yayinlamiyor)` notu docstring sonuna.

`news/cve_scraper.py`: `class CIRCLScraper(CVEScraper):` sınıfını (bir sonraki `class` ya da `# ===` başlığına kadar) sil; `MultiCVEScraper.__init__` içinde `self.circl_scraper = CIRCLScraper()` ve `'CIRCL': self.circl_scraper,` satırlarını sil; sınıf docstring'i/yorumunda CIRCL geçiyorsa `# 2026-10-14: CIRCL cikarildi (/api/last yalniz PYSEC/GHSA ve eski published donuyor; NVD + GitHub Advisory kapsiyor)`.

Run: `grep -rnE "CIRCL|MinIO|KDnuggets" news/*.py` → yalnız 2026-10-14 notları.

- [ ] **Step 4: Testleri koş, yeşil gör** — Step 2 komutu. Expected: OK. Ayrıca `news.tests.test_status` OK (news 12 değişmedi).

- [ ] **Step 5: Kadans testlerini yaz (kırmızı)** — `test_kaynak_sagligi.py` `KaynakDurumlariTests` sınıfına ekle (dosya başı import'lara `DevToolsEntry` ekle: `from news.models import DevToolsEntry, FetchRun, NewsArticle`; `from datetime import date` ekle):

```python
    def _devtools_kaydi(self, gun_once):
        kayit = DevToolsEntry.objects.create(source='RabbitMQ', original_title='RabbitMQ v4.3.6',
                                             original_description='D', link='https://ornek.test/r',
                                             published_date=date(2026, 9, 14))
        DevToolsEntry.objects.filter(pk=kayit.pk).update(created_at=timezone.now() - timedelta(days=gun_once))

    def test_seyrek_kaynak_pencere_disinda_sessiz_degil(self):
        # RabbitMQ 30 gunluk pencerede 0 doner ama son surum 29 gun once; beklenen aralik 60 gun
        self._devtools_kaydi(29)
        for i in range(4):
            _tur('devtools', {'RabbitMQ': {'fetched': 0, 'saved': 0}}, i)

        durum = kaynaklar.kaynak_durumlari('devtools', DevToolsEntry)['RabbitMQ']

        self.assertEqual(durum['zero_runs'], 4)
        self.assertEqual(durum['expected_gap_days'], 60)
        self.assertEqual(durum['days_since_record'], 29)
        self.assertFalse(durum['silent'])

    def test_seyrek_kaynak_beklenen_araligi_asinca_sessiz(self):
        self._devtools_kaydi(61)
        for i in range(4):
            _tur('devtools', {'RabbitMQ': {'fetched': 0, 'saved': 0}}, i)

        self.assertTrue(kaynaklar.kaynak_durumlari('devtools', DevToolsEntry)['RabbitMQ']['silent'])

    def test_akis_kaynagi_bolum_penceresini_kullanir(self):
        # Haber penceresi 7 gun: 10 gun once kayit + 4 sifir tur = sessiz
        kayit = NewsArticle.objects.create(source='Dark Reading', original_title='T', turkish_title='T',
                                           link='https://ornek.test/d', date=date(2026, 10, 1),
                                           original_date='2026-10-01')
        NewsArticle.objects.filter(pk=kayit.pk).update(created_at=timezone.now() - timedelta(days=10))
        for i in range(4):
            _tur('news', {'Dark Reading': {'fetched': 0, 'saved': 0}}, i)

        durum = kaynaklar.kaynak_durumlari('news', NewsArticle)['Dark Reading']

        self.assertEqual(durum['expected_gap_days'], 7)
        self.assertEqual(durum['days_since_record'], 10)
        self.assertTrue(durum['silent'])
```

`test_sema_kaynak_alanlarini_tasir` testine iki satır ekle:

```python
        kaynak = sema['components']['schemas']['KaynakDurumuV1']['properties']
        self.assertIn('expected_gap_days', kaynak)
        self.assertIn('days_since_record', kaynak)
```

Run: `docker compose exec teknoloji-api python manage.py test news.tests.test_kaynak_sagligi --noinput`
Expected: 4 FAIL (`KeyError: 'expected_gap_days'` ve şema).

- [ ] **Step 6: `news/kaynaklar.py` kadans kuralı** — `BOLUMLER = …` satırından sonra ekle:

```python
# Bolum basina cekim penceresi (news/tasks.py fetch_* varsayilan `days`): kaynaktan bu
# pencerede en az bir kayit gelmesi beklenir.
BOLUM_PENCERESI_GUN = {'news': 7, 'cve': 7, 'kubernetes': 30, 'sre': 30, 'devtools': 30, 'ai': 30}

# Seyrek yayinlayan kaynaklar (2026-10-14 olcumu): RabbitMQ aylik yama, Moodle/Ceph iki-uc ayda bir
# surum, Krebs/PagerDuty seyrek yazi. Pencerede 0 donmeleri olagan; sessizlik ancak son kayit bu
# kadar gunden eskiyse (RabbitMQ/MongoDB yanlis pozitifleri bu yuzden).
BEKLENEN_ARALIK_GUN = {
    'RabbitMQ': 60, 'MongoDB': 45, 'Moodle': 90, 'Ceph': 90, 'Seq': 60, 'Elastic': 60,
    'Redis': 60, 'PostgreSQL': 60, 'Keycloak': 60, 'GitLab': 45,
    'Krebs on Security': 21, 'PagerDuty Eng': 60, 'Import AI': 21,
}


def beklenen_aralik(bolum: str, ad: str) -> int:
    """Kaynaktan iki kayit arasinda beklenen en uzun gun sayisi."""
    return BEKLENEN_ARALIK_GUN.get(ad, BOLUM_PENCERESI_GUN.get(bolum, 30))
```

`kaynak_durumlari` içinde `from django.db.models import Max` satırının altına `from django.utils import timezone` ve `simdi = timezone.now()`; döngüdeki `durum[ad] = {…}` bloğunu şununla değiştir:

```python
        son = son_kayit.get(ad)
        yas = (simdi - son).days if son else None
        aralik = beklenen_aralik(bolum, ad)
        durum[ad] = {
            'last_record_at': son,
            'last_fetched_count': son_gelen,
            'zero_runs': sifir,
            'expected_gap_days': aralik,
            'days_since_record': yas,
            # Iki kosul: ardisik sifir turlar VE son kayit beklenen araliktan eski (ya da hic
            # kayit yok). Seyrek yayinlayan kaynak yalniz pencere disinda kaldigi icin sessiz sayilmaz.
            'silent': sifir >= SESSIZ_TUR_ESIGI and (yas is None or yas > aralik),
        }
```

Docstring'e (kaynak_durumlari) bir cümle: `Sessizlik 2026-10-14'ten beri kadans farkindalikli: bkz. BEKLENEN_ARALIK_GUN.`

`news/api_v1/schema.py` `KaynakDurumuV1`'e (`silent = …` satırından önce):

```python
    expected_gap_days = serializers.IntegerField()
    days_since_record = serializers.IntegerField(allow_null=True)
```

- [ ] **Step 7: Testleri koş, yeşil gör** — Run: `scripts/pg_test.sh test news --noinput`. Expected: tüm testler OK (sayı 491 + 5 yeni = 496 civarı; kırmızı yok).

- [ ] **Step 8: Belgeler ve arayüz metinleri**

- `README.md`: `### CVE Zafiyetleri (6 kaynak)` → `(5 kaynak)` ve CIRCL maddesi silinir; `### DevTools — Altyapi Araclari (14 kaynak)` → `(13 kaynak)` ve MinIO maddesi silinir; `### Yapay Zeka (8 kaynak)` → `(9 kaynak)`, KDnuggets maddesi yerine iki madde:

```markdown
- Ars Technica AI — https://arstechnica.com/ai/feed/ (RSS)
- Import AI — https://importai.substack.com/feed (haftalik bulten, RSS)
```

  Satır 749 paragrafının sonuna:

```markdown
2026-10-14: sessizlik kadans farkindalikli — seyrek yayinlayan kaynak (RabbitMQ, Moodle, Ceph...) icin kaynak basina beklenen aralik (`news/kaynaklar.py` `BEKLENEN_ARALIK_GUN`), digerleri icin bolum penceresi; status ucu `expected_gap_days` ve `days_since_record` verir.
```

  "Tamamlanan asamalar" tablosuna satır:

```markdown
| 2026-10-14 | Kaynak turu 2: 48 → 47 (KDnuggets/MinIO/CIRCL cikti, Ars Technica AI/Import AI girdi); kadans farkindalikli sessizlik | `news/tests/test_kaynak_sagligi.py` |
```
- `frontend/src/App.jsx`: satır 118 `6 kaynaktan (CISA KEV dahil)` → `5 kaynaktan (CISA KEV dahil)`; satır 168 `14 kaynaktan altyapı araçları güncellemelerini çekin — PostgreSQL, MongoDB,` → `13 kaynaktan …` (devamı aynı).
- `.env.example` GITHUB_TOKEN yorumundaki `(MinIO, RabbitMQ, …` → `(RabbitMQ, …`.

Run: `cd frontend && npm run lint && npm run build` → hata yok.

- [ ] **Step 9: Commit, push (ONAY), PR, merge**

```bash
git add news/ai_scraper.py news/devtools_scraper.py news/cve_scraper.py news/kaynaklar.py news/api_v1/schema.py news/tests/test_kaynak_sagligi.py news/tests/test_kaynaklar.py README.md frontend/src/App.jsx .env.example
git commit -m "feat(kaynaklar): KDnuggets/MinIO/CIRCL cikarildi, Ars Technica AI + Import AI; sessizlik kadans farkindalikli

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
PR başlığı: `feat(kaynaklar): kaynak turu 2 - 48 -> 47, kadans farkindalikli sessizlik`. Merge sonrası compose worker'ı yeniden başlat (`docker compose restart teknoloji-worker teknoloji-api`), bir sonraki `ai`/`devtools` turunda `by_source`'ta `Ars Technica AI`/`Import AI` fetched > 0.

- [ ] **Step 10: Token'lar (KULLANICI)** — Kullanıcı `.env`'e `GITHUB_TOKEN=` (fine-grained, "Public repositories (read-only)") ve `NVD_API_KEY=` yazar; `docker compose up -d teknoloji-api teknoloji-worker` (env değişikliği restart ister). Doğrulama (değer basmadan):

```bash
docker compose exec -T teknoloji-worker sh -c 'test -n "$GITHUB_TOKEN" && echo GITHUB_TOKEN tanimli; test -n "$NVD_API_KEY" && echo NVD_API_KEY tanimli'
```

---

### Task 3: Vitest altyapısı (repo: `tech-radar`, `frontend/`)

**Files:**
- Modify: `frontend/package.json` (devDependencies, `scripts.test`)
- Modify: `frontend/vite.config.js` (`test` bloğu)
- Create: `frontend/src/test/setup.js`
- Create: `frontend/src/utils/html.test.js`, `frontend/src/hooks/useAraliklaYenile.test.jsx`, `frontend/src/components/CeviriEtiketi.test.jsx`
- Modify: `frontend/eslint.config.js` (test dosyaları için `globals.vitest`)
- Modify: `.github/workflows/ci.yml` (Frontend işi: Testler adımı)
- Modify: `README.md` "Gelistirme ve Test" (bir paragraf)

**Interfaces:**
- Produces: `npm test` (= `vitest run`), `src/test/setup.js` (jest-dom eşleştiricileri); Task 4 ve 5 testleri bu altyapıyı kullanır.

- [ ] **Step 1: Dal aç ve paketleri kur**

```bash
git checkout -b feat/vitest-altyapisi
cd frontend && npm install -D vitest@4 jsdom@30 @testing-library/react@16 @testing-library/jest-dom@7 --no-audit --no-fund && npm ls vite vitest
```
Expected: `npm ls` peer hatası yok (`vitest@4.x` altında `vite@6.4.x`). Hata verirse dur ve bildir (spec §6).

- [ ] **Step 2: Yapılandırma** — `package.json` scripts'e `"test": "vitest run"`; `vite.config.js` `defineConfig({…})` içine `server`'dan sonra:

```js
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.test.{js,jsx}'],
  },
```

`src/test/setup.js`:

```js
// Vitest kurulumu: jest-dom eslestiricileri (toBeInTheDocument, toBeEmptyDOMElement...)
import '@testing-library/jest-dom/vitest'
```

`eslint.config.js` dizisinin sonuna:

```js
  {
    files: ['**/*.test.{js,jsx}', 'src/test/**'],
    languageOptions: { globals: { ...globals.browser, ...globals.vitest } },
  },
```

- [ ] **Step 3: `src/utils/html.test.js` yaz (kırmızı değil; mevcut kodu sabitler — önce koş, hepsi geçmeli)**

```js
import { describe, it, expect } from 'vitest'
import { kacis, guvenliHref } from './html'

describe('kacis', () => {
  it('bes HTML karakterini kacislar', () => {
    expect(kacis('<script>alert("x") & \'y\'</script>'))
      .toBe('&lt;script&gt;alert(&quot;x&quot;) &amp; &#39;y&#39;&lt;/script&gt;')
  })
  it('null ve undefined bos dize olur', () => {
    expect(kacis(null)).toBe('')
    expect(kacis(undefined)).toBe('')
  })
  it('sayi dizeye cevrilir, duz metin degismez', () => {
    expect(kacis(42)).toBe('42')
    expect(kacis('CVE-2026-1234 kritik')).toBe('CVE-2026-1234 kritik')
  })
})

describe('guvenliHref', () => {
  it('http ve https kabul edilir ve kacislanir', () => {
    expect(guvenliHref('https://ornek.test/a?b=1&c=2')).toBe('https://ornek.test/a?b=1&amp;c=2')
    expect(guvenliHref('HTTP://ornek.test')).toBe('HTTP://ornek.test')
  })
  it('javascript:, data:, goreli ve bos deger bos dize olur', () => {
    expect(guvenliHref('javascript:alert(1)')).toBe('')
    expect(guvenliHref('data:text/html,x')).toBe('')
    expect(guvenliHref('/yerel/yol')).toBe('')
    expect(guvenliHref('')).toBe('')
    expect(guvenliHref(undefined)).toBe('')
  })
})
```

- [ ] **Step 4: `src/hooks/useAraliklaYenile.test.jsx` yaz**

```jsx
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import useAraliklaYenile from './useAraliklaYenile'

const gorunurluk = (gizli) => Object.defineProperty(document, 'hidden', { configurable: true, get: () => gizli })

describe('useAraliklaYenile', () => {
  beforeEach(() => { vi.useFakeTimers(); gorunurluk(false) })
  afterEach(() => { vi.useRealTimers(); gorunurluk(false) })

  it('aralik dolunca callback cagrilir', () => {
    const cb = vi.fn()
    renderHook(() => useAraliklaYenile(cb, 1000))
    vi.advanceTimersByTime(2500)
    expect(cb).toHaveBeenCalledTimes(2)
  })

  it('sekme arka plandayken istek atmaz, one gelince hemen yeniler', () => {
    const cb = vi.fn()
    renderHook(() => useAraliklaYenile(cb, 1000))
    gorunurluk(true)
    vi.advanceTimersByTime(3000)
    expect(cb).not.toHaveBeenCalled()
    gorunurluk(false)
    document.dispatchEvent(new Event('visibilitychange'))
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('unmount sonrasi zamanlayici ve dinleyici durur', () => {
    const cb = vi.fn()
    const { unmount } = renderHook(() => useAraliklaYenile(cb, 1000))
    unmount()
    vi.advanceTimersByTime(3000)
    document.dispatchEvent(new Event('visibilitychange'))
    expect(cb).not.toHaveBeenCalled()
  })

  it('en guncel callback kullanilir', () => {
    const ilk = vi.fn()
    const son = vi.fn()
    const { rerender } = renderHook(({ cb }) => useAraliklaYenile(cb, 1000), { initialProps: { cb: ilk } })
    rerender({ cb: son })
    vi.advanceTimersByTime(1000)
    expect(ilk).not.toHaveBeenCalled()
    expect(son).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 5: `src/components/CeviriEtiketi.test.jsx` yaz**

```jsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import CeviriEtiketi, { ceviriEtiketiHtml } from './CeviriEtiketi'

describe('CeviriEtiketi', () => {
  it('LibreTranslate kaydi sari uyari rozeti alir', () => {
    render(<CeviriEtiketi kayit={{ translation_provider: 'libretranslate' }} />)
    expect(screen.getByText('Makine çevirisi: LibreTranslate')).toBeInTheDocument()
  })
  it('Gemini kaydi gri bilgi rozeti alir', () => {
    render(<CeviriEtiketi kayit={{ translation_provider: 'gemini' }} />)
    expect(screen.getByText('Çeviri: Gemini')).toBeInTheDocument()
  })
  it('saglayicisiz ve ceviri beklemeyen kayit rozet almaz; kayit yoksa cokmez', () => {
    const { container } = render(<CeviriEtiketi kayit={{ translation_provider: '', needs_translation: false }} />)
    expect(container).toBeEmptyDOMElement()
    expect(render(<CeviriEtiketi />).container).toBeEmptyDOMElement()
  })
  it('html cikti saglayiciya gore rozet uretir, bilinmeyen icin bos', () => {
    expect(ceviriEtiketiHtml({ translation_provider: 'gemini' })).toContain('Çeviri: Gemini')
    expect(ceviriEtiketiHtml({ translation_provider: 'x' })).toBe('')
    expect(ceviriEtiketiHtml(undefined)).toBe('')
  })
})
```

- [ ] **Step 6: Koş**

Run: `cd frontend && npm test && npm run lint`
Expected: 3 dosya, 11 test geçer; lint temiz. Bir test kırmızıysa kodu değil testi düzelt (bu adım mevcut davranışı sabitler); gerçek bir hata bulursan ayrı commit.

- [ ] **Step 7: CI ve README** — `.github/workflows/ci.yml` Frontend işinde `- name: Lint (ESLint)` adımından sonra:

```yaml
      - name: Testler (Vitest)
        run: npm test
```

README "Gelistirme ve Test" bölümünde ESLint paragrafının sonuna:

```markdown
Frontend birim testleri Vitest + Testing Library ile `frontend/src/**/*.test.{js,jsx}` altindadir (`npm test`); CI'da lint ile build arasinda kosar. Ilk kapsam: HTML kacisi (`utils/html.js`), aralikli yenileme hook'u, ceviri rozeti.
```

- [ ] **Step 8: Commit, push (ONAY), PR, merge**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/eslint.config.js frontend/src/test/setup.js frontend/src/utils/html.test.js frontend/src/hooks/useAraliklaYenile.test.jsx frontend/src/components/CeviriEtiketi.test.jsx .github/workflows/ci.yml README.md
git commit -m "test(frontend): Vitest altyapisi; html kacisi, useAraliklaYenile ve CeviriEtiketi testleri; CI adimi

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Sağlık şeridi (repo: `tech-radar`; backend + frontend)

**Files:**
- Modify: `news/fetch_runs.py` (`bolum_ozetleri()`)
- Modify: `news/views.py` (`get_saglik`), `news/urls.py` (`api/saglik/`)
- Create: `news/tests/test_saglik.py`
- Modify: `frontend/src/services/api.js` (`saglikApi`)
- Create: `frontend/src/utils/zaman.js`, `frontend/src/utils/zaman.test.js`, `frontend/src/components/SaglikSeridi.jsx`, `frontend/src/components/SaglikSeridi.test.jsx`
- Modify: `frontend/src/App.jsx` (`HomePage` içine `<SaglikSeridi />`)
- Modify: `README.md` ("API Endpoints" tablosuna `GET /api/saglik/`; "Saglik ve gorunurluk")

**Interfaces:**
- Consumes: `news.kaynaklar.kaynak_durumlari(bolum, model)` (`silent` anahtarı, Task 2), `news.fetch_runs.BOLUM_MODELLERI`, `news.retranslate.RETRANSLATE_MAX_ATTEMPTS`, `useAraliklaYenile(callback, ms)`.
- Produces: `fetch_runs.bolum_ozetleri() -> dict[str, dict]` (anahtarlar: `last_success_at: str|None` (ISO), `last_status: str|None`, `pending_translation: int`, `translation_given_up: int`, `silent_sources: list[str]`); `GET /api/saglik/` → `{"generated_at": ISO, "sections": {...}}`; `saglikApi.getSaglik()`; `goreliZaman(iso, simdi=Date.now()) -> string`; `<SaglikSeridi />`.

- [ ] **Step 1: Dal aç** — `git checkout -b feat/saglik-seridi`

- [ ] **Step 2: Backend testini yaz (kırmızı)** — `news/tests/test_saglik.py`

```python
"""GET /api/saglik/ (2026-10-14 bakim dalgasi): anonim, dar, 60 sn cache'li saglik ozeti.

Neden: /api/v1/status/ token ister, arayuz anonimdir; sessiz kaynaklar curl rutinine kaldigi
icin 2026-10-08'den sonra kimse bakmadi. Bu uc yalniz tazelik + sessizlik verir; operator
alanlari (sources, total, by_provider, error) v1/status ve admin'de kalir.
"""
from datetime import date, timedelta

from django.core.cache import cache
from django.utils import timezone

from news.models import FetchRun, NewsArticle
from news.tests.base import V1TestCase


def _tur(bolum, by_source, gun_once, status='success'):
    kayit = FetchRun.objects.create(section=bolum, trigger='beat', status=status, by_source=by_source,
                                    finished_at=timezone.now())
    zaman = timezone.now() - timedelta(hours=6 * gun_once)
    FetchRun.objects.filter(pk=kayit.pk).update(started_at=zaman, finished_at=zaman)
    return kayit


class SaglikUcuTests(V1TestCase):

    def setUp(self):
        super().setUp()
        cache.delete('saglik_ozeti')

    def test_tokensiz_200_ve_alti_bolum(self):
        yanit = self.client.get('/api/saglik/')

        self.assertEqual(yanit.status_code, 200)
        govde = yanit.json()
        self.assertIn('generated_at', govde)
        self.assertEqual(set(govde['sections']), {'news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai'})
        haber = govde['sections']['news']
        self.assertIsNone(haber['last_success_at'])
        self.assertIsNone(haber['last_status'])
        self.assertEqual(haber['silent_sources'], [])
        self.assertEqual(haber['pending_translation'], 0)

    def test_son_basarili_tur_ve_sessiz_kaynaklar(self):
        for i in range(4):
            _tur('news', {'Bleeping Computer': {'fetched': 0, 'saved': 0},
                          'The Hacker News': {'fetched': 5, 'saved': 1}}, i)
        NewsArticle.objects.create(source='The Hacker News', original_title='T', turkish_title='T',
                                   link='https://ornek.test/1', date=date(2026, 10, 14),
                                   original_date='2026-10-14', needs_translation=True)

        haber = self.client.get('/api/saglik/').json()['sections']['news']

        self.assertEqual(haber['last_status'], 'success')
        self.assertIsNotNone(haber['last_success_at'])
        self.assertEqual(haber['silent_sources'], ['Bleeping Computer'])
        self.assertEqual(haber['pending_translation'], 1)
        self.assertEqual(haber['translation_given_up'], 0)

    def test_son_tur_hatali_ama_son_basarili_ayri(self):
        _tur('cve', {'NVD': {'fetched': 3, 'saved': 1}}, 1)
        _tur('cve', {}, 0, status='failure')

        cve = self.client.get('/api/saglik/').json()['sections']['cve']

        self.assertEqual(cve['last_status'], 'failure')
        self.assertIsNotNone(cve['last_success_at'])

    def test_operator_alanlari_sizmaz(self):
        _tur('cve', {'NVD': {'fetched': 3, 'saved': 1}}, 0)

        cve = self.client.get('/api/saglik/').json()['sections']['cve']

        self.assertEqual(set(cve), {'last_success_at', 'last_status', 'pending_translation',
                                    'translation_given_up', 'silent_sources'})

    def test_altmis_saniye_cache(self):
        self.client.get('/api/saglik/')
        _tur('sre', {'SRE Weekly': {'fetched': 1, 'saved': 0}}, 0)

        self.assertIsNone(self.client.get('/api/saglik/').json()['sections']['sre']['last_status'])
        cache.delete('saglik_ozeti')
        self.assertEqual(self.client.get('/api/saglik/').json()['sections']['sre']['last_status'], 'success')
```

Run: `docker compose exec teknoloji-api python manage.py test news.tests.test_saglik --noinput`
Expected: 5 test, hepsi 404 ile FAIL.

- [ ] **Step 3: Backend uygulaması** — `news/fetch_runs.py` sonuna:

```python
def bolum_ozetleri() -> dict:
    """Anonim /api/saglik/ icin bolum basina tazelik ozeti (2026-10-14).

    StatusView'daki (v1, token'li) raporun DAR alt kumesi: son basarili tur, son durum, ceviri
    bekleyen/vazgecilen sayilari ve sessiz kaynaklar. Toplamlar, kaynak basina ayrinti,
    by_provider ve error bilerek yok: uc anonimdir, operator verisi v1/status ve admin'de kalir.
    """
    from .kaynaklar import kaynak_durumlari
    from .retranslate import RETRANSLATE_MAX_ATTEMPTS

    ozet = {}
    for ad, model in BOLUM_MODELLERI.items():
        son = FetchRun.objects.filter(section=ad).first()
        son_basarili = FetchRun.objects.filter(section=ad, status='success').first()
        kaynaklar = kaynak_durumlari(ad, model)
        ozet[ad] = {
            'last_success_at': (son_basarili.finished_at.isoformat()
                                if son_basarili and son_basarili.finished_at else None),
            'last_status': son.status if son else None,
            'pending_translation': model.objects.filter(needs_translation=True).count(),
            'translation_given_up': model.objects.filter(
                needs_translation=True, translation_attempts__gte=RETRANSLATE_MAX_ATTEMPTS).count(),
            'silent_sources': [k for k, v in kaynaklar.items() if v['silent']],
        }
    return ozet
```

(`FetchRun.Meta.ordering = ['-started_at']` olduğu için `.first()` en yeni turdur; `FetchRun` modülde zaten import edilidir — değilse `from .models import FetchRun` ekle.)

`news/views.py` sonuna:

```python
SAGLIK_CACHE_SURESI = 60


@api_view(['GET'])
@permission_classes([AllowAny])
def get_saglik(request):
    """Ana sayfa saglik seridi: bolum basina son basarili cekim ve sessiz kaynaklar (2026-10-14).

    Tokensizdir (arayuz anonim); bu yuzden v1 /status/'un dar alt kumesidir ve 60 sn cache'lenir
    (kaynak_durumlari bolum basina FetchRun + Max(created_at) sorgusu yapar).
    """
    from django.utils.timezone import now

    from .fetch_runs import bolum_ozetleri

    govde = cache.get('saglik_ozeti')
    if govde is None:
        govde = {'generated_at': now().isoformat(), 'sections': bolum_ozetleri()}
        cache.set('saglik_ozeti', govde, SAGLIK_CACHE_SURESI)
    return Response(govde)
```

`news/urls.py` `urlpatterns` başına (`# Haber API endpoints` yorumundan önce):

```python
    # Ana sayfa saglik seridi (anonim, dar, 60 sn cache; 2026-10-14)
    path('api/saglik/', views.get_saglik, name='get_saglik'),
```

- [ ] **Step 4: Backend testleri yeşil** — Step 2 komutu → 5 OK. Canlı: `curl -s http://localhost:8000/api/saglik/ | head -c 400` → `"sections"` ve altı bölüm.

- [ ] **Step 5: Frontend yardımcı + test** — `frontend/src/utils/zaman.js`:

```js
// ISO zamani "15 dk önce" gibi goreli metne cevirir (saglik seridi). Bos/bozuk/gelecek deger: '-'.
export const goreliZaman = (iso, simdi = Date.now()) => {
  if (!iso) return '-'
  const fark = Math.floor((simdi - Date.parse(iso)) / 1000)
  if (Number.isNaN(fark) || fark < 0) return '-'
  if (fark < 60) return 'az önce'
  if (fark < 3600) return `${Math.floor(fark / 60)} dk önce`
  if (fark < 86400) return `${Math.floor(fark / 3600)} sa önce`
  return `${Math.floor(fark / 86400)} gün önce`
}
```

`frontend/src/utils/zaman.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { goreliZaman } from './zaman'

const T = Date.parse('2026-10-14T12:00:00Z')

describe('goreliZaman', () => {
  it('saniye, dakika, saat, gun esikleri', () => {
    expect(goreliZaman('2026-10-14T11:59:30Z', T)).toBe('az önce')
    expect(goreliZaman('2026-10-14T11:45:00Z', T)).toBe('15 dk önce')
    expect(goreliZaman('2026-10-14T06:00:00Z', T)).toBe('6 sa önce')
    expect(goreliZaman('2026-10-11T12:00:00Z', T)).toBe('3 gün önce')
  })
  it('bos, bozuk ve gelecek deger tire olur', () => {
    expect(goreliZaman(null, T)).toBe('-')
    expect(goreliZaman(undefined, T)).toBe('-')
    expect(goreliZaman('bozuk', T)).toBe('-')
    expect(goreliZaman('2026-10-14T13:00:00Z', T)).toBe('-')
  })
})
```

Run: `cd frontend && npm test -- zaman` → 2 test OK.

- [ ] **Step 6: Bileşen testi (kırmızı)** — `frontend/src/components/SaglikSeridi.test.jsx`

```jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import SaglikSeridi from './SaglikSeridi'
import { saglikApi } from '../services/api'

vi.mock('../services/api', () => ({ saglikApi: { getSaglik: vi.fn() } }))

const bolum = (ek = {}) => ({
  last_success_at: new Date(Date.now() - 3600 * 1000).toISOString(),
  last_status: 'success', pending_translation: 0, translation_given_up: 0, silent_sources: [], ...ek,
})

describe('SaglikSeridi', () => {
  beforeEach(() => vi.clearAllMocks())

  it('alti bolumu, goreli zamani ve sorun rozetlerini gosterir', async () => {
    saglikApi.getSaglik.mockResolvedValue({ data: { sections: {
      news: bolum(), cve: bolum(), kubernetes: bolum(), sre: bolum(),
      devtools: bolum({ silent_sources: ['MinIO', 'RabbitMQ'] }), ai: bolum({ last_status: 'failure' }),
    } } })

    render(<SaglikSeridi />)

    expect(await screen.findByText('DevTools')).toBeInTheDocument()
    expect(screen.getByText('2 sessiz')).toBeInTheDocument()
    expect(screen.getByText('son tur hatalı')).toBeInTheDocument()
    expect(screen.getAllByText('ok')).toHaveLength(4)
    expect(screen.getAllByText('1 sa önce')).toHaveLength(6)
    expect(screen.getByTitle('Sessiz: MinIO, RabbitMQ')).toBeInTheDocument()
  })

  it('istek basarisizsa sessiz bir uyari gosterir', async () => {
    saglikApi.getSaglik.mockRejectedValue(new Error('500'))

    render(<SaglikSeridi />)

    expect(await screen.findByText('Sağlık bilgisi alınamadı.')).toBeInTheDocument()
  })
})
```

Run: `npm test -- SaglikSeridi` → FAIL (`Failed to resolve import "./SaglikSeridi"`).

- [ ] **Step 7: `saglikApi`, bileşen ve ana sayfa**

`frontend/src/services/api.js` sonuna:

```js
// Saglik seridi (anonim, 60 sn cache'li; 2026-10-14)
export const saglikApi = {
  getSaglik: () => api.get('/saglik/'),
}
```

`frontend/src/components/SaglikSeridi.jsx`:

```jsx
import { useCallback, useEffect, useState } from 'react'
import { Badge } from 'react-bootstrap'
import { saglikApi } from '../services/api'
import useAraliklaYenile from '../hooks/useAraliklaYenile'
import { goreliZaman } from '../utils/zaman'

// Ana sayfa saglik seridi (2026-10-14): bolum basina son basarili cekim ve sessiz kaynaklar.
// Amac: /api/v1/status/ curl rutinine bagimli kalmadan olu kaynagi arayuzde gormek.
export const BOLUM_ETIKETLERI = {
  news: 'Siber Güvenlik', cve: 'CVE', kubernetes: 'Kubernetes',
  sre: 'SRE', devtools: 'DevTools', ai: 'Yapay Zeka',
}
const YENILEME_MS = 5 * 60 * 1000

export default function SaglikSeridi() {
  const [veri, setVeri] = useState(null)
  const [hata, setHata] = useState(false)

  const yukle = useCallback(async () => {
    try {
      const yanit = await saglikApi.getSaglik()
      setVeri(yanit.data.sections)
      setHata(false)
    } catch {
      setHata(true)
    }
  }, [])

  useEffect(() => { yukle() }, [yukle])
  useAraliklaYenile(yukle, YENILEME_MS)

  if (hata) return <div className="text-muted small mb-4">Sağlık bilgisi alınamadı.</div>
  if (!veri) return null

  return (
    <div className="d-flex flex-wrap justify-content-center gap-2 mb-4" data-testid="saglik-seridi">
      {Object.entries(BOLUM_ETIKETLERI).map(([ad, etiket]) => {
        const b = veri[ad] || {}
        const sessiz = b.silent_sources || []
        const sorun = sessiz.length > 0 || b.last_status === 'failure'
        const baslik = sessiz.length ? `Sessiz: ${sessiz.join(', ')}` : 'Tüm kaynaklar veri döndürüyor'
        return (
          <span key={ad} className="border rounded px-2 py-1 small" title={baslik}>
            <strong>{etiket}</strong>{' '}
            <span className="text-muted">{goreliZaman(b.last_success_at)}</span>{' '}
            {sorun
              ? <Badge bg="danger">{sessiz.length ? `${sessiz.length} sessiz` : 'son tur hatalı'}</Badge>
              : <Badge bg="success">ok</Badge>}
          </span>
        )
      })}
    </div>
  )
}
```

`frontend/src/App.jsx`: import listesine `import SaglikSeridi from './components/SaglikSeridi'`; `HomePage` içinde `<p className="lead mb-5">…</p>` kapanışından hemen sonra `<SaglikSeridi />`.

- [ ] **Step 8: Frontend yeşil + canlı bakış**

Run: `cd frontend && npm test && npm run lint && npm run build` → tüm testler OK, lint temiz.
Tarayıcı: `http://localhost:3000/` ana sayfada altı kutu; kutu başlığı (title) sessiz kaynakları gösterir.

- [ ] **Step 9: README** — "API Endpoints" bölümündeki tabloya `| GET | /api/saglik/ | Bolum basina son basarili cekim, son durum, ceviri bekleyen/vazgecilen, sessiz kaynaklar (anonim, 60 sn cache) |`; "Saglik ve gorunurluk" alt bölümüne `curl -s localhost:8000/api/saglik/ | jq '.sections[] | .silent_sources'` satırı (tokensiz).

- [ ] **Step 10: Commit, push (ONAY), PR, merge**

```bash
git add news/fetch_runs.py news/views.py news/urls.py news/tests/test_saglik.py frontend/src/services/api.js frontend/src/utils/zaman.js frontend/src/utils/zaman.test.js frontend/src/components/SaglikSeridi.jsx frontend/src/components/SaglikSeridi.test.jsx frontend/src/App.jsx README.md
git commit -m "feat(saglik): anonim /api/saglik/ ucu ve ana sayfa saglik seridi (sessiz kaynaklar gorunur)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Backend ucu anonim ve yeni: bu PR için kısa bir review (sonnet) açılabilir (Global Constraints).

---

### Task 5: Çeviri kalıntıları (repo: `tech-radar`)

**Files:**
- Modify: `news/admin.py` (`CeviriDenemeSifirlamaMixin`, altı admin sınıfı)
- Modify: `news/tests/test_admin.py` (iki test)
- Modify: `frontend/src/components/CeviriEtiketi.jsx` (`CEVRILMEDI` rozeti), `frontend/src/components/CeviriEtiketi.test.jsx` (iki test)
- Modify: `README.md` "Retranslate ve Gemini Yukseltme" (bir paragraf)

**Interfaces:**
- Produces: admin eylemi `ceviri_denemelerini_sifirla(request, queryset)` (altı modelde); `CeviriEtiketi` için `rozetSec(kayit)`.
- Consumes: `translation_attempts`, `needs_translation`, `translation_provider` alanları (legacy API `fields='__all__'` ile döner).

- [ ] **Step 1: Dal aç** — `git checkout -b feat/ceviri-kalintilari`

- [ ] **Step 2: Admin testleri (kırmızı)** — `news/tests/test_admin.py` import'larına ekle: `from django.contrib.auth.models import User`, `from django.contrib.messages.storage.fallback import FallbackStorage`, `from django.test import RequestFactory`; dosya sonuna:

```python
class CeviriDenemeSifirlamaTests(TestCase):
    """2026-10-14: RETRANSLATE_MAX_ATTEMPTS'a ulasip kuyruktan dusen kayitlar admin'den geri alinir."""

    def setUp(self):
        self.istek = RequestFactory().get('/admin/')
        self.istek.user = User.objects.create_superuser('yonetici', 'y@ornek.test', 'gecici-parola-123')
        self.istek.session = {}
        self.istek._messages = FallbackStorage(self.istek)

    def test_eylem_alti_modelde_kayitli(self):
        for model in (NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry):
            with self.subTest(model=model.__name__):
                self.assertIn('ceviri_denemelerini_sifirla', admin.site._registry[model].get_actions(self.istek))

    def test_sayac_sifirlanir_ve_kuyruga_doner_secilmeyen_degismez(self):
        secili = SREEntry.objects.create(source='SRE Weekly', original_title='T', original_description='D',
                                         link='https://ornek.test/1', published_date=date(2026, 10, 1),
                                         needs_translation=True, translation_attempts=5)
        digeri = SREEntry.objects.create(source='SRE Weekly', original_title='T2', original_description='D',
                                         link='https://ornek.test/2', published_date=date(2026, 10, 1),
                                         needs_translation=False, translation_attempts=5)

        admin.site._registry[SREEntry].ceviri_denemelerini_sifirla(
            self.istek, SREEntry.objects.filter(pk=secili.pk))

        secili.refresh_from_db()
        digeri.refresh_from_db()
        self.assertEqual((secili.translation_attempts, secili.needs_translation), (0, True))
        self.assertEqual((digeri.translation_attempts, digeri.needs_translation), (5, False))
        self.assertEqual([str(m) for m in self.istek._messages], ['1 kayit yeniden ceviri kuyruguna alindi.'])
```

Run: `docker compose exec teknoloji-api python manage.py test news.tests.test_admin --noinput` → 2 FAIL.

- [ ] **Step 3: Admin eylemi** — `news/admin.py`'de `CEVIRI_FILTRELERI = …` satırından önce:

```python
class CeviriDenemeSifirlamaMixin:
    """Kuyruktan dusmus (RETRANSLATE_MAX_ATTEMPTS) kayitlari yeniden siraya alir (2026-10-14).

    Sayaci sifirlar ve needs_translation'i acar; bir sonraki retranslate turu kaydi yeniden dener.
    GEMINI_MAX_CHARS ustu kayitlar yine Gemini'ye gitmez (LibreTranslate yolu); kok neden
    giderilmeden toplu sifirlama Gemini butcesini bosa yakar.
    """
    actions = ['ceviri_denemelerini_sifirla']

    @admin.action(description='Ceviri denemelerini sifirla (yeniden kuyruga al)')
    def ceviri_denemelerini_sifirla(self, request, queryset):
        sayi = queryset.update(translation_attempts=0, needs_translation=True)
        self.message_user(request, f'{sayi} kayit yeniden ceviri kuyruguna alindi.')
```

Altı admin sınıfının tabanını `(CeviriDenemeSifirlamaMixin, CeviriKarsilastirmaMixin, admin.ModelAdmin)` yap (NewsArticleAdmin, CVEEntryAdmin, KubernetesEntryAdmin, SREEntryAdmin, DevToolsEntryAdmin, AINewsEntryAdmin).

Run: Step 2 komutu → OK. Tam dosya: `news.tests.test_admin` hepsi OK.

- [ ] **Step 4: Rozet testleri (kırmızı)** — `CeviriEtiketi.test.jsx`'e ekle:

```jsx
  it('saglayicisiz ama ceviri bekleyen kayit "Çevrilmedi" rozeti alir', () => {
    render(<CeviriEtiketi kayit={{ translation_provider: '', needs_translation: true }} />)
    expect(screen.getByText('Çevrilmedi: orijinal metin')).toBeInTheDocument()
  })
  it('html cikti da "Çevrilmedi" rozetini uretir', () => {
    expect(ceviriEtiketiHtml({ translation_provider: '', needs_translation: true })).toContain('Çevrilmedi: orijinal metin')
  })
```

Run: `cd frontend && npm test -- CeviriEtiketi` → 2 FAIL.

- [ ] **Step 5: Rozet** — `CeviriEtiketi.jsx`'te `ROZETLER` tanımından sonra:

```js
// Hic cevrilememis kayit (fetch aninda LibreTranslate basarisiz, retranslate 5 denemede vazgecti ya da
// GEMINI_MAX_CHARS ustu): metin Ingilizce gosterilir; okuyucu bunu bilmeli (2026-10-14).
const CEVRILMEDI = {
  metin: 'Çevrilmedi: orijinal metin',
  bg: 'light', text: 'dark', arka: '#e9ecef', on: '#212529',
  aciklama: 'Çeviri sağlayıcıları bu kaydı çeviremedi (çok uzun ya da çevrilemeyen içerik); metin İngilizce gösteriliyor.',
}

const rozetSec = (kayit) =>
  ROZETLER[kayit?.translation_provider]
  || (kayit?.needs_translation && !kayit?.translation_provider ? CEVRILMEDI : null)
```

`CeviriEtiketi` ve `ceviriEtiketiHtml` içindeki `const rozet = ROZETLER[kayit?.translation_provider]` → `const rozet = rozetSec(kayit)`.

Run: `npm test && npm run lint` → OK.

- [ ] **Step 6: README** — "Retranslate ve Gemini Yukseltme" sonuna:

```markdown
Kuyruktan dusen kayitlar (`translation_attempts >= RETRANSLATE_MAX_ATTEMPTS`) arayuzde "Cevrilmedi: orijinal metin" rozetiyle gosterilir; admin'de "Ceviri denemelerini sifirla" eylemi secili kayitlari yeniden kuyruga alir. `GEMINI_MAX_CHARS` (12.000) ustu kayitlar bilerek Ingilizce kalir (2026-10-14 karari).
```

- [ ] **Step 7: Commit, push (ONAY), PR, merge; Obsidian görevini kapat (KULLANICI)**

```bash
git add news/admin.py news/tests/test_admin.py frontend/src/components/CeviriEtiketi.jsx frontend/src/components/CeviriEtiketi.test.jsx README.md
git commit -m "feat(ceviri): admin'de deneme sayaci sifirlama eylemi; cevrilmemis kayit rozeti

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Obsidian `Tasks/cybernews-uzun-k8s-kaydi-karari.md`: `status: done`, karar "İngilizce kalır (spec D10)".

---

### Task 6: ZAP triyajı (GitHub; kod yok)

**Files:** yalnız GitHub Security sekmesi; belge güncellemesi Task 7 PR'ında (`docs/GUVENLIK-PLANI.md` §5).

- [ ] **Step 1: Açık listeyi doğrula**

```bash
cd /c/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news
MSYS_NO_PATHCONV=1 gh api "repos/AdanedhelWrites/tech-radar/code-scanning/alerts?state=open&per_page=100" --jq '.[] | "\(.number)\t\(.rule.id)"' | sort -k2
```
Expected: 16 satır — `10010`: 307 308 309 355; `10031`: 349 350 351 352 421 422 423; `10055-6`: 432 433 434 435 437. Liste farklıysa numaraları buna göre düzelt.

- [ ] **Step 2: Dismiss (KULLANICI ONAYI; yorumlar ≤ 280 karakter)**

```bash
R=repos/AdanedhelWrites/tech-radar/code-scanning/alerts
for n in 349 350 351 352 421 422 423; do
  MSYS_NO_PATHCONV=1 gh api -X PATCH "$R/$n" -f state=dismissed -f dismissed_reason="false positive" \
    -f dismissed_comment="Django admin login: alanlar Django tarafindan escape edilir; ZAP 10031 yansitilan degeri XSS adayi sayar, calisan payload yok (GUVENLIK-PLANI 3a, 2026-10-14)." --jq '.number, .state'
done
for n in 307 308 309 355; do
  MSYS_NO_PATHCONV=1 gh api -X PATCH "$R/$n" -f state=dismissed -f dismissed_reason="won't fix" \
    -f dismissed_comment="csrftoken bilerek HttpOnly degil: frontend axios xsrfCookieName ile okur (api.js). CSRF token gizli deger degildir; oturum cerezi HttpOnly (GUVENLIK-PLANI 3a, 2026-10-14)." --jq '.number, .state'
done
for n in 432 433 434 435 437; do
  MSYS_NO_PATHCONV=1 gh api -X PATCH "$R/$n" -f state=dismissed -f dismissed_reason="won't fix" \
    -f dismissed_comment="style-src unsafe-inline bilerek: Django admin ve Swagger UI inline style attribute kullanir; CSP nonce yalniz <style> elemanini kapsar. script-src nonce'lu; XSS vektoru degil (2026-10-14)." --jq '.number, .state'
done
```

- [ ] **Step 3: Doğrula**

```bash
MSYS_NO_PATHCONV=1 gh api "repos/AdanedhelWrites/tech-radar/code-scanning/alerts?state=open&per_page=100" --jq 'length'
```
Expected: `0`. Belge satırı Task 7 Step 9'da.

---

### Task 7: P5-c — `/api/v1/` ZAP API taraması (repo: `tech-radar`)

**Files:**
- Modify: `cybernews/ayar_dogrulama.py` (`v1_hiz_sinirlari`), `cybernews/settings.py:14,131-134`
- Modify: `news/tests/test_ayar_dogrulama.py` (iki test)
- Create: `.zap/api_hooks.py`
- Modify: `.gitignore` (`.zap/api-token.txt` açık satır), `.github/workflows/dast-zap.yml` (api konteyner env + 4 adım)
- Modify: `docs/GUVENLIK-PLANI.md` (P5 son kutu `[x]`, §5 Geçmiş: P5-c ve ZAP triyajı), `README.md` "CI ve Guvenlik Hatti" (bir cümle)

**Interfaces:**
- Produces: `v1_hiz_sinirlari(env: Mapping[str, str]) -> dict` (`{'v1_read': str, 'v1_refresh': str}`); ortam değişkenleri `V1_THROTTLE_READ`, `V1_THROTTLE_REFRESH`; SARIF kategorisi `zap-api`.
- Consumes: `scripts/zap_sarif.py <json> <sarif> --kurallar .zap/rules.tsv` (mevcut), `.zap/rules.tsv`, `manage.py spectacular`.

- [ ] **Step 1: Dal aç** — `git checkout -b feat/p5c-api-zap`

- [ ] **Step 2: Throttle testi (kırmızı)** — `news/tests/test_ayar_dogrulama.py` import satırına `v1_hiz_sinirlari` ekle; dosya sonuna:

```python
class V1HizSinirlariTest(SimpleTestCase):
    """DAST (P5-c) v1 throttle'ini ortamdan gevsetir; uretim varsayilani degismez."""

    def test_varsayilanlar(self):
        self.assertEqual(v1_hiz_sinirlari({}), {'v1_read': '120/min', 'v1_refresh': '12/hour'})

    def test_ortamdan_gevsetilir_bos_deger_varsayilana_duser(self):
        self.assertEqual(v1_hiz_sinirlari({'V1_THROTTLE_READ': '100000/min', 'V1_THROTTLE_REFRESH': ''}),
                         {'v1_read': '100000/min', 'v1_refresh': '12/hour'})
```

Run: `docker compose exec teknoloji-api python manage.py test news.tests.test_ayar_dogrulama --noinput` → ImportError.

- [ ] **Step 3: Uygulama** — `cybernews/ayar_dogrulama.py` sonuna:

```python
def v1_hiz_sinirlari(env: Mapping[str, str]) -> dict:
    """v1 throttle oranlari (DRF 'sayi/birim'). DAST bunlari ortamdan gevsetir: ZAP API
    taramasi dakikada yuzlerce istek atar, 120/min ile her sey 429 olurdu (P5-c, 2026-10-14).
    Bos deger varsayilana duser; bozuk bicimi DRF acilista reddeder, burada dogrulanmaz.
    """
    return {
        'v1_read': env.get('V1_THROTTLE_READ', '') or '120/min',
        'v1_refresh': env.get('V1_THROTTLE_REFRESH', '') or '12/hour',
    }
```

`cybernews/settings.py` satır 14: `from cybernews.ayar_dogrulama import dogrulanmis_secret_key, v1_hiz_sinirlari, veritabani_ayari`; `'DEFAULT_THROTTLE_RATES': {…}` bloğu → `'DEFAULT_THROTTLE_RATES': v1_hiz_sinirlari(os.environ),` (üstündeki yorum kalır, sonuna `Ortam: V1_THROTTLE_READ / V1_THROTTLE_REFRESH (yalniz DAST icin).`).

Run: Step 2 komutu → OK; `news.tests.test_refresh` ve `test_auth` OK (throttle davranışı değişmedi).

- [ ] **Step 4: Kanca ve gitignore** — `.zap/api_hooks.py`:

```python
"""ZAP API taramasi kancasi (zap-api-scan.py --hook). Token'i /zap/wrk/.zap/api-token.txt'den okur
ve her istege Authorization basligi ekler (replacer). Dosya yoksa kasten patlar: token'siz tarama
401'lerle "yesil" gorunurdu (P5-c, 2026-10-14). Token degeri hicbir yere basilmaz.
"""
TOKEN_DOSYASI = '/zap/wrk/.zap/api-token.txt'


def zap_started(zap, target):
    with open(TOKEN_DOSYASI, encoding='utf-8') as dosya:
        token = dosya.read().strip()
    if not token:
        raise RuntimeError('api-token.txt bos: v1 taramasi token olmadan calismaz')
    zap.replacer.add_rule(description='v1-token', enabled=True, matchtype='REQ_HEADER',
                          matchregex=False, matchstring='Authorization',
                          replacement='Token ' + token, initiators='')
```

`.gitignore` "Old scraper output files" bloğunun altına: `# DAST: ZAP API taramasinin gecici token dosyasi (zaten *.txt; acikca)` ve `.zap/api-token.txt`. Doğrula: `git check-ignore -v .zap/api-token.txt` bir kural gösterir.

- [ ] **Step 5: Yerel kuru koşu (ONAY: ZAP imajı ~1,5 GB çekilir)** — canlı compose'a karşı, geçici kullanıcıyla:

```bash
cd /c/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news
docker compose exec -T teknoloji-api python manage.py spectacular --file /tmp/schema.yml && docker compose cp teknoloji-api:/tmp/schema.yml ./schema.yml
docker compose exec -T teknoloji-api python manage.py shell -v 0 -c "from django.contrib.auth.models import User; from rest_framework.authtoken.models import Token; u,_=User.objects.get_or_create(username='zap-prova'); print(Token.objects.get_or_create(user=u)[0].key)" | tail -1 > .zap/api-token.txt
AG=$(docker network ls --format '{{.Name}}' | grep teknoloji-network)
MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/zap/wrk/:rw" --network "$AG" ghcr.io/zaproxy/zaproxy:stable \
  zap-api-scan.py -t schema.yml -f openapi -O http://teknoloji-api:8000 --hook=/zap/wrk/.zap/api_hooks.py -c .zap/rules.tsv -J report_json.json -r report_html.html -a
jq '[.site[].alerts[].instances[].uri] | map(select(test("/api/v1/"))) | length' report_json.json
grep -c '"statusCode": "200"\|HTTP/1.1 200' report_html.html || true
```
Expected: ZAP özeti `/api/v1/` adresleriyle biter; jq sayısı ≥ 1; `/api/v1/status/` için 200 görülür (token çalıştı; 429'lar canlı throttle yüzünden beklenir). Temizlik:

```bash
docker compose exec -T teknoloji-api python manage.py shell -v 0 -c "from django.contrib.auth.models import User; User.objects.filter(username='zap-prova').delete()"
rm -f .zap/api-token.txt schema.yml report_json.json report_html.html report_md.md
```

- [ ] **Step 6: Workflow** — `.github/workflows/dast-zap.yml`: "Uygulamayi ayaga kaldir" adımında `docker run -d --name api …` komutuna `-e CELERY_BROKER_URL=…` satırından sonra `-e V1_THROTTLE_READ=100000/min -e V1_THROTTLE_REFRESH=100000/hour \` ekle. "SARIF yukle" (baseline) adımından sonra, "API loglari"ndan önce dört adım:

```yaml
      # ---- P5-c: /api/v1/ OpenAPI tabanli, token'li API taramasi (rapor modu; kategori zap-api) ----
      - name: v1 semasi ve gecici token
        run: |
          set -euo pipefail
          docker exec api python manage.py spectacular --file /tmp/schema.yml
          docker cp api:/tmp/schema.yml schema.yml
          test -s schema.yml
          # Django 5.2 shell -c banner basar: -v 0 + tail -1
          token=$(docker exec api python manage.py shell -v 0 -c "from django.contrib.auth.models import User; from rest_framework.authtoken.models import Token; u, _ = User.objects.get_or_create(username='zap-dast'); print(Token.objects.get_or_create(user=u)[0].key)" | tail -1)
          [ "${#token}" -ge 20 ] || { echo "::error::token uretilemedi"; exit 1; }
          echo "::add-mask::${token}"
          printf '%s' "${token}" > .zap/api-token.txt

      - name: ZAP API taramasi (/api/v1/)
        uses: zaproxy/action-api-scan@5158fe4d9d8fcc75ea204db81317cce7f9e5453d # v0.10.0
        with:
          target: schema.yml
          format: openapi
          rules_file_name: .zap/rules.tsv
          cmd_options: "-O http://localhost:8000 --hook=/zap/wrk/.zap/api_hooks.py -a"
          fail_action: false
          allow_issue_writing: false
          artifact_name: zap-api

      - name: ZAP API hedefi gercekten taradi mi
        if: ${{ always() }}
        run: |
          set -euo pipefail
          rm -f .zap/api-token.txt
          test -s report_json.json || { echo "::error::ZAP API JSON raporu yok"; exit 1; }
          adres=$(jq '[.site[]? | select(."@name" | test("localhost")) | .alerts[]?.instances[]?.uri | select(test("/api/v1/"))] | length' report_json.json)
          [ "${adres}" -ge 1 ] || { echo "::error::ZAP API raporunda /api/v1/ adresi yok (token ya da sema sorunu); bos hedefe yesil yok"; exit 1; }
          {
            echo "### ZAP API (/api/v1/)"
            echo "| Risk | Alert tipi |"
            echo "|---|---|"
            jq -r '[.site[].alerts[]? | .riskdesc | split(" ")[0]] | group_by(.)[] | "| \(.[0]) | \(length) |"' report_json.json
          } >> "${GITHUB_STEP_SUMMARY}"
          python3 scripts/zap_sarif.py report_json.json zap-api.sarif --kurallar .zap/rules.tsv
          python3 -c 'import json; d=json.load(open("zap-api.sarif")); assert d["version"]=="2.1.0" and d["runs"], "SARIF iskeleti bozuk"'

      - name: API SARIF yukle
        uses: github/codeql-action/upload-sarif@2892aa5e19bbd11bc0cff5427e3b750a04d9e3c2 # v4.38.2
        with:
          sarif_file: zap-api.sarif
          category: zap-api
```

Not: baseline ve API eylemleri aynı `report_json.json` adını kullanır; baseline SARIF'i bu adımlardan önce üretilip yüklendiği için çakışma yok. `/api/v1/` filtresi baseline raporuna "yeşil" demez.

- [ ] **Step 7: Yerel statik doğrulama**

```bash
docker run --rm -v "$(pwd -W):/repo" -w /repo rhysd/actionlint:latest -color .github/workflows/dast-zap.yml
```
(ya da mevcut alışkanlık: `zizmor` CI'da). Expected: hata yok.

- [ ] **Step 8: Push (ONAY) ve PR'da DAST koşusunu izle** — `git push -u origin feat/p5c-api-zap`; PR aç; `MSYS_NO_PATHCONV=1 gh run list --repo AdanedhelWrites/tech-radar --workflow "DAST (ZAP baseline)" --limit 1`; iş yeşil, step summary'de "ZAP API (/api/v1/)" tablosu; Security → Code scanning → Tool status'ta `zap-api` kategorisi. Kırmızıysa `gh run view <id> --log-failed` ile neden: token (`#token`), şema (`schema.yml`), host override (`Using override, new target`).

- [ ] **Step 9: Belgeler** — `docs/GUVENLIK-PLANI.md`: P5'teki son kutu (`- [ ] A5 (OpenAPI şeması) çıkınca …`) şununla değişir:

```markdown
- [x] `/api/v1/` ZAP API taraması — DAST işinde ek adımlar: `manage.py spectacular` şeması, geçici `zap-dast` token'ı (`.zap/api_hooks.py` replacer kancası), `V1_THROTTLE_*` ile gevşetilmiş throttle, SARIF kategori `zap-api`; raporda `/api/v1/` adresi yoksa iş kırmızı (2026-10-14)
```

  §5 Geçmiş'e iki satır:

```markdown
- **2026-10-14:** ZAP triyajı: 16 açık uyarı gerekçeli kapatıldı (7 false positive 10031; 4+5 won't fix 10010/10055-6); Security 0 açık.
- **2026-10-14:** P5-c: `/api/v1/` ZAP API taraması canlı (kategori `zap-api`). Güvenlik planı P0–P5 tamam.
```

  Başlıktaki "Son güncelleme" satırı `2026-10-14 (P5-c tamamlandı; plan kapandı)`. README "CI ve Guvenlik Hatti" DAST cümlesinin sonuna:

```markdown
; ayni iste `/api/v1/` OpenAPI semasiyla token'li API taramasi (kategori `zap-api`)
```

- [ ] **Step 10: Commit, merge**

```bash
git add cybernews/ayar_dogrulama.py cybernews/settings.py news/tests/test_ayar_dogrulama.py .zap/api_hooks.py .gitignore .github/workflows/dast-zap.yml docs/GUVENLIK-PLANI.md README.md
git commit -m "feat(guvenlik): v1 API ZAP taramasi (P5-c): OpenAPI + token kancasi, SARIF zap-api; throttle ortamdan

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
Kimlik/DAST yüzeyi: kısa review (sonnet) uygun.

---

### Task 8: Python kalite kapısı (repo: `tech-radar`)

**Files:**
- Create: `requirements-dev.txt`, `pyproject.toml`
- Delete: `requirements_docker.txt`
- Modify: 34 `F` bulgusunun olduğu dosyalar (`ruff` listeler), `.github/workflows/ci.yml` (Backend işi), `README.md` ("Gelistirme ve Test", "Kod kurallari")

**Interfaces:**
- Produces: `ruff check .` (F, E9), `coverage run manage.py test` + `MIN_COVERAGE` eşiği (CI env).

- [ ] **Step 1: Dal aç, araçları izole kur**

```bash
git checkout -b chore/ruff-coverage
printf 'ruff==0.17.0\ncoverage==7.16.2\n' > requirements-dev.txt
py -3 -m venv .venv && .venv/Scripts/python.exe -m pip install -q -r requirements-dev.txt
```
(`.venv/` gitignore'da.)

- [ ] **Step 2: `pyproject.toml`**

```toml
[tool.ruff]
target-version = "py311"
line-length = 120
extend-exclude = ["migrations", "staticfiles", "frontend", "docs", "_arsiv", ".superpowers", ".venv"]

[tool.ruff.lint]
# Baslangic kapisi dar (2026-10-14): yalniz hata sinifi (pyflakes F, sozdizimi E9). Stil kurallari
# (E, UP, SIM, RUF...) ayni gun 489 bulgu verdi; ayri bir PR'da kademeli acilir.
select = ["F", "E9"]

[tool.coverage.run]
source = ["news", "cybernews", "scripts", "scraper_multi"]
omit = ["*/migrations/*", "*/tests/*", "cybernews/asgi.py", "cybernews/wsgi.py"]

[tool.coverage.report]
skip_empty = true
```

- [ ] **Step 3: Bulguları gör ve düzelt**

Run: `.venv/Scripts/ruff.exe check . --statistics` → `26 F401, 5 F841, 3 F541` (34). Sonra:

```bash
.venv/Scripts/ruff.exe check . --fix
git diff --stat
```
`cybernews/__init__.py` diff'te **olmamalı** (`__all__` re-export). Kalan 5 `F841` (kullanılmayan yerel değişken) için `ruff check .` çıktısındaki dosya:satır'a git; değişkeni sil ya da `_` yap (bir hata yakalama bloğunda `except Exception as e:` ile `e` kullanılmıyorsa `except Exception:`). Run: `.venv/Scripts/ruff.exe check .` → `All checks passed!`.

- [ ] **Step 4: Testler yeşil** — Run: `scripts/pg_test.sh test news --noinput` → OK (kaldırılan import'lar bir şeyi kırmadı).

- [ ] **Step 5: `requirements_docker.txt` sil** — `git rm requirements_docker.txt`; `grep -rn requirements_docker . --include=*.md --include=*.yml --include=Dockerfile` → yalnız `docs/superpowers/specs/2026-09-21-a5b-…` (tarihsel, dokunma).

- [ ] **Step 6: CI** — `.github/workflows/ci.yml` Backend işinde `- name: Bagimliliklar` adımından sonra:

```yaml
      - name: Gelistirme araclari (ruff, coverage)
        run: python -m pip install -r requirements-dev.txt

      - name: ruff (F, E9)
        run: ruff check .
```

`env:` bloğuna `MIN_COVERAGE: "0"`. "Testler" adımında `SECRET_KEY="$(openssl rand -hex 32)" python manage.py test --noinput 2>&1 | tee test.log` → `SECRET_KEY="$(openssl rand -hex 32)" coverage run manage.py test --noinput 2>&1 | tee test.log`; adımın sonuna:

```bash
          coverage report --fail-under="${MIN_COVERAGE}" | tail -1 | tee -a "${GITHUB_STEP_SUMMARY}"
```

`setup-python` `cache-dependency-path:` değerini listeye çevir:

```yaml
          cache-dependency-path: |
            requirements.txt
            requirements-dev.txt
```

- [ ] **Step 7: README** — "Kod kurallari" listesine madde:

```markdown
- Python: `ruff check .` (yalniz F ve E9; `pyproject.toml`) ve coverage esigi (`MIN_COVERAGE`, CI) kapidir; yerelde `py -3 -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt`.
```

  "Gelistirme ve Test" bölümünde `requirements_docker.txt` geçmiyor (`grep -n requirements_docker README.md` boş; doğrula).

- [ ] **Step 8: Commit 1, push (ONAY), PR; CI'da coverage'ı oku**

```bash
git add requirements-dev.txt pyproject.toml .github/workflows/ci.yml README.md $(git diff --name-only) 
git commit -m "chore(kalite): ruff (F, E9) ve coverage CI kapisi; 34 pyflakes bulgusu; requirements_docker.txt silindi

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
CI Backend step summary'de `TOTAL … NN%` satırını oku.

- [ ] **Step 9: Commit 2: eşiği sabitle** — `MIN_COVERAGE: "<floor(NN) - 2>"` (örn. 83% → `"81"`); commit `chore(kalite): coverage esigi %<N>`; CI yeşil → merge.

---

### Task 9: K8s sürümü 2026.10.3 / chart 2.2.1 (repo: `tech-radar` + `yerel-gitops`)

**Files:**
- Modify: `helm/tech-radar/Chart.yaml:12,15`, `helm/tech-radar/CHANGELOG.md` (yeni `## [2.2.1]`)
- Modify: `yerel-gitops/apps/tech-radar.yaml:16` (`targetRevision: chart-2.2.1`)

**Interfaces:**
- Consumes: `scripts/chart_surum_kontrol.sh <taban>`, `scripts/chart_etiket_kontrol.sh` (CI), `yerel-platform/scripts/k8s_dogrulama.sh t6`.
- Produces: imajlar `teknoloji-haberleri-api:2026.10.3`, `teknoloji-haberleri-frontend:2026.10.3`; git etiketi `chart-2.2.1`.

- [ ] **Step 1: Dal ve sürüm** — `git checkout main && git pull --ff-only && git checkout -b chore/chart-2.2.1`; `Chart.yaml`: `version: 2.2.1`, `appVersion: "2026.10.3"`. `CHANGELOG.md`'de `## [2.2.0]` girdisinin üstüne:

```markdown
## [2.2.1] - 2026-10-14 — appVersion 2026.10.3

Yalniz `appVersion` yukseltmesi; sablon ve values degismedi (render farki yalniz imaj etiketi ve `helm.sh/chart`).
Uygulama 2026.10.3 = main (bakim dalgasi 2026-10): 48 kaynak + kaynak sagligi + django-axes + logging (PR #57-#59),
takili tur/XSS/nginx/zehirli kayit (PR #60), worker acilisinda takili FetchRun kapatma (PR #61), haftalik guvenlik
ozeti (PR #62), kaynak turu 2 (47 kaynak, kadans farkindalikli sessizlik), anonim `/api/saglik/` ucu ve saglik
seridi, cevrilmemis kayit rozeti + admin sifirlama eylemi, v1 throttle'in ortamdan gevsetilmesi (`V1_THROTTLE_*`,
yalniz DAST), ruff duzeltmeleri. K8s ortaminda `secrets.githubToken/nvdApiKey` hala bos (optional).
```

Run: `scripts/chart_surum_kontrol.sh origin/main` → `Chart surumu 2.2.0 -> 2.2.1; CHANGELOG girdisi var.`; `helm lint helm/tech-radar --set secrets.secretKey=x --set secrets.dbPassword=y` → `1 chart(s) linted, 0 chart(s) failed`.

- [ ] **Step 2: Commit, push (ONAY), PR, merge**

```bash
git add helm/tech-radar/Chart.yaml helm/tech-radar/CHANGELOG.md
git commit -m "chore(helm): chart 2.2.1 - appVersion 2026.10.3 (bakim dalgasi)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

- [ ] **Step 3: İmajları derle (merge sonrası `main`'de)**

```bash
git checkout main && git pull --ff-only
docker build -t teknoloji-haberleri-api:2026.10.3 .
docker build -t teknoloji-haberleri-frontend:2026.10.3 ./frontend
docker image ls --format '{{.Repository}}:{{.Tag}}' | grep 2026.10.3
```
Expected: iki satır.

- [ ] **Step 4: Etiket (ONAY)**

```bash
git tag chart-2.2.1 && git push origin chart-2.2.1
MSYS_NO_PATHCONV=1 gh run list --repo AdanedhelWrites/tech-radar --workflow "chart etiketi" --limit 1
```
Expected: `completed success`.

- [ ] **Step 5: yerel-gitops (ONAY)**

```bash
cd /c/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-gitops && git pull --ff-only
sed -i 's/targetRevision: chart-2.1.1/targetRevision: chart-2.2.1/' apps/tech-radar.yaml
git add apps/tech-radar.yaml && git commit -m "tech-radar: chart-2.2.1 (appVersion 2026.10.3: bakim dalgasi)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git push
```

- [ ] **Step 6: Argo CD ve küme doğrulaması**

```bash
for _ in $(seq 1 30); do kubectl --context docker-desktop -n argocd get application tech-radar -o custom-columns=SYNC:.status.sync.status,HEALTH:.status.health.status,REV:.status.sync.revision --no-headers; sleep 10; done | tail -1
kubectl --context docker-desktop -n tech-radar get pods -o custom-columns=NAME:.metadata.name,READY:.status.containerStatuses[0].ready,IMAGE:.spec.containers[0].image
kubectl --context docker-desktop -n tech-radar get job teknoloji-migrate -o custom-columns=SUCCEEDED:.status.succeeded
kubectl --context docker-desktop -n tech-radar logs deploy/teknoloji-worker | grep -m1 "Acilis"
cd /c/Users/Adanedhel/Desktop/OpenCodeProjects/yerel-platform && scripts/k8s_dogrulama.sh t6
```
Expected: `Synced Healthy chart-2.2.1`; api/worker/frontend imajları `2026.10.3`, READY true; `SUCCEEDED 1`; `[FetchRun] Acilis: takili running satiri yok`; `GECTI T6 …`.

- [ ] **Step 7: Hafıza ve günlük** — `b3-gitops` hafızasını (K8s chart-2.2.1 / 2026.10.3) ve Obsidian Daily'yi güncelle.

---

### Task 10: Yerel hijyen (dosya sistemi; her silme KULLANICI ONAYI)

**Files:**
- Move: `CyberNews/db-yedek-ceviri-zinciri-20260914-1543.sqlite3`, `CyberNews/db-yedek-gemini-20260915-1617.sqlite3`, `CyberNews/test.py`, `CyberNews/test_browser.py` → `CyberNews/_arsiv/2026-10-14-kok-temizlik/`
- Delete: `CyberNews/;W` (boş dizin), `cybersecurity_news/C:` (17 MB bind-mount artığı; içinde hassas `.fazb/dump.json`), `cybersecurity_news/helm;C` (boş)

- [ ] **Step 1: Envanter (silmeden önce bak)**

```powershell
Set-Location 'C:\Users\Adanedhel\Desktop\OpenCodeProjects\CyberNews'
Get-ChildItem -Force | Where-Object { $_.Name -in @(';W','test.py','test_browser.py') -or $_.Name -like 'db-yedek-*' } | Select-Object Name, Length
Set-Location 'C:\Users\Adanedhel\Desktop\OpenCodeProjects\CyberNews\cybersecurity_news'
$artik = Get-ChildItem -Force | Where-Object { ($_.Name.Length -eq 2 -and $_.Name -like 'C*') -or $_.Name -eq 'helm;C' }
$artik | ForEach-Object { $_.FullName; (Get-ChildItem -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum }
```
Expected: `C?` ≈ 17 MB (`Program Files\Git\app\.fazb\dump.json`), `helm;C` 0.

- [ ] **Step 2: Arşive taşı (ONAY)**

```powershell
Set-Location 'C:\Users\Adanedhel\Desktop\OpenCodeProjects\CyberNews'
New-Item -ItemType Directory -Force '_arsiv\2026-10-14-kok-temizlik' | Out-Null
Move-Item -LiteralPath 'db-yedek-ceviri-zinciri-20260914-1543.sqlite3','db-yedek-gemini-20260915-1617.sqlite3','test.py','test_browser.py' -Destination '_arsiv\2026-10-14-kok-temizlik\'
cmd /c 'rd /q ";W"'
```

- [ ] **Step 3: Repo içi artıkları sil (ONAY; `rm -rf "C:"` ASLA — MSYS çalışma dizinine çözer)**

```powershell
Set-Location 'C:\Users\Adanedhel\Desktop\OpenCodeProjects\CyberNews\cybersecurity_news'
Get-ChildItem -Force | Where-Object { ($_.Name.Length -eq 2 -and $_.Name -like 'C*') -or $_.Name -eq 'helm;C' } | ForEach-Object { cmd /c ('rd /s /q "' + $_.FullName + '"') }
Get-ChildItem -Force | Where-Object { $_.Name -like 'C*' -or $_.Name -like 'helm;*' } | Select-Object Name
```
Expected: ikinci komut yalnız gerçek dosyaları listeler (`C?` ve `helm;C` yok).

- [ ] **Step 4: Doğrula** — `git status --porcelain` boş; `ls` temiz; Docker bind mount'un `C:` dizinini yeniden yaratıp yaratmadığını bir sonraki `docker compose up -d` sonrasında kontrol et (yaratıyorsa kaynağı `docker compose config | grep -n "C:"` ile bul ve bildir).

---

## Self-Review (yazar notu)

- **Spec kapsamı:** D1→T1, D2→T9, D3/D4→T2, D5→T2 Step 10, D6→T4, D7→T3, D8→T6, D9→T7, D10→T5, D11→T8, D12→T10. Boşluk yok.
- **Yer tutucu taraması:** "TBD/sonra doldur" yok; tek koşullu adım T3 Step 1 (`npm ls` peer hatası → dur ve bildir) ve T8 Step 9 (eşik ilk ölçümden türetilir) — ikisi de deterministik talimat.
- **Tip tutarlılığı:** `kaynak_durumlari` yeni anahtarları (`expected_gap_days`, `days_since_record`) T2'de tanımlı, T4 yalnız `silent` okur; `bolum_ozetleri()` anahtar kümesi T4 testinde birebir; `saglikApi.getSaglik` adı bileşen ve mock'ta aynı; `v1_hiz_sinirlari` imzası test ve settings'te aynı; `_tur` yardımcısı `test_saglik.py`'ye kopyalandı (test modülleri arası import yok).
- **Review Focus:** 5 madde → T1 S9, T2 S5, T3 S3, T4 S2, T7 S6 testleri/kapıları.
