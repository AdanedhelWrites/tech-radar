# Guvenlik Temizligi Uygulama Plani

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Depodaki tum acik guvenlik bulgularini kapatmak ya da gerekcesiyle
bilinerek kabul etmek: Dependabot 14 -> 0, code scanning 89 -> ~8.

**Architecture:** Dokuz bagimsiz is, ucuzdan riskliye siralanmis. Her is kendi
dalinda yapilir, kendi dogrulama kapisindan gecer, `main`'e `--no-ff` ile
merge edilir ve push edilir. Bir is kapisini gecemezse dal silinir, `main`
hic kirilmaz ve sirasi gelen bir sonraki ise gecilir.

**Tech Stack:** Django 4.2.30 -> 5.2.16, DRF 3.17.2 -> 3.18.1, Python 3.11,
Docker Compose (alti servis), React + vite, Node 18 -> 22, GitHub code
scanning / Dependabot / Trivy / CodeQL / Scorecard / zizmor.

**Spec:** `docs/superpowers/specs/2026-09-22-guvenlik-temizligi-design.md`

## Global Constraints

Bunlar **her** gorev icin gecerlidir, her seferinde tekrar yazilmaz:

- Kod yorumlari ve docstring'ler **aksansiz Turkce**.
- Her is **ayri commit**; commit mesajlari aksansiz Turkce ve sonunda
  `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` satiri.
- **324 test kirilmamali.** Test sayisi degisirse (gorev 4 test ekleyebilir)
  yeni sayi commit mesajinda yazilir.
- **Subagent code review ACILMAYACAK.** Dogrulama bu plandaki komutlarla
  yapilir. (Kullanicinin kalici talimati.)
- **force-push YOK.** `main`'e dogrudan push edilir, dal uzerinden merge ile.
- **`scraper_multi.py` SILINMEYECEK** — canli koddur (`news/tasks.py`,
  `news/views.py`, `news/retranslate.py`, `news/tests/test_haber_aciklamasi.py`
  onu import eder). Yalniz `app.py` silinir ve o da `scraper_multi`'yi import
  ettigi icin karistirilmamalidir.
- **`gui_multi.py` KAPSAM DISI.** Kullanilmiyor olabilir ama uzerinde guvenlik
  bulgusu yok; bu plan ona dokunmaz.
- **`@vitejs/plugin-react` 6.x'e YUKSELTILMEYECEK** — peer bagimliligi
  `vite: ^8.0.0`. Mevcut 4.7.0 vite 6 ile uyumludur.
- Bir gorev dogrulama kapisini gecemezse: dal silinir (`git checkout main &&
  git branch -D <dal>`), ne kirildigi raporlanir, sonraki goreve gecilir.
  **Ileri dogru hata ayiklama yapilmaz.**

### Tam kapi (bircok gorevde "tam kapi" diye anilir)

```bash
cd "C:/Users/Adanedhel/Desktop/OpenCodeProjects/CyberNews/cybersecurity_news"

# 1. Imajlari yeniden kur ve servisleri ayaga kaldir
docker compose up -d --build teknoloji-api teknoloji-worker teknoloji-scheduler

# 2. Alti servis de Up olmali
docker compose ps

# 3. Test paketi
docker compose exec -T teknoloji-api python manage.py test news

# 4. Sema saglam mi
docker compose exec -T teknoloji-api python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybernews.settings')
django.setup()
from drf_spectacular.drainage import reset_generator_stats, GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator
reset_generator_stats()
schema = SchemaGenerator().get_schema(request=None, public=True)
print('Yol sayisi:', len(schema.get('paths', {})))
print('warnings:', dict(GENERATOR_STATS._warn_cache))
print('errors:', dict(GENERATOR_STATS._error_cache))
"

# 5. Canli HTTP
curl -s -o /dev/null -w "health:%{http_code}\n" http://localhost:8000/api/v1/health/
curl -s -o /dev/null -w "schema:%{http_code}\n" http://localhost:8000/api/v1/schema/
curl -s -o /dev/null -w "frontend:%{http_code}\n" http://localhost:3000/
```

Beklenen: alti servis `Up` | `Ran 324 tests ... OK` | `Yol sayisi: 11`,
`warnings: {}`, `errors: {}` | `health:200`, `schema:401`, `frontend:200`.

Uctan uca istemci adimi (tam kapinin son parcasi):

```bash
TOKEN=$(docker compose exec -T teknoloji-api python manage.py shell -c "
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
U = get_user_model()
u, _ = U.objects.get_or_create(username='plan_dogrulama', defaults={'is_staff': True})
t, _ = Token.objects.get_or_create(user=u)
print(t.key)
" | tr -d '\r')

CYBERNEWS_TOKEN="$TOKEN" CYBERNEWS_URL=http://localhost:8000 python scripts/ornek_istemci.py

# Temizlik — token kullanici ve durum dosyasi birakilmaz
docker compose exec -T teknoloji-api python manage.py shell -c "
from django.contrib.auth import get_user_model
get_user_model().objects.filter(username='plan_dogrulama').delete()
print('silindi')
"
rm -f scripts/ornek_istemci_durum.json
```

Beklenen: alti bolum icin `degisen=` satirlari ve `... kayit upsert edildi`.

### Dal ve merge akisi (her gorevde ayni)

```bash
git checkout main && git pull origin main
git checkout -b <gorev-dali>
# ... degisiklikler + commit ...
# ... dogrulama kapisi ...
git checkout main
git merge --no-ff <gorev-dali> -m "Merge <gorev-dali>: <kisa aciklama>"
git push origin main
git branch -d <gorev-dali>
```

---

### Task 1: Olu kodu sil

**Files:**
- Delete: `app.py`
- Delete: `templates/` (dizin)
- Delete: `news/templates/` (dizin)
- Modify: `cybernews/settings.py:104` (`TEMPLATES[0]['DIRS']`)

**Interfaces:**
- Consumes: yok (ilk gorev)
- Produces: yok (silme isi; sonraki gorevler bundan bir sey kullanmaz)

- [ ] **Step 1: Dali ac**

```bash
git checkout main && git pull origin main
git checkout -b temizlik/olu-kod
```

- [ ] **Step 2: Silmeden once referans olmadigini kanitla**

```bash
grep -rn "from app import\|import app$\|render(\|render_template\|TemplateView" --include=*.py . | grep -v _arsiv | grep -v site-packages
grep -rn "news/index.html\|'index.html'\|\"index.html\"" --include=*.py . | grep -v _arsiv | grep -v site-packages
```

Beklenen: **app.py'nin kendi satirlari disinda hicbir cikti olmamali.**
Cikti varsa DUR ve raporla — silme guvenli degil.

- [ ] **Step 3: Sil**

```bash
git rm app.py
git rm -r templates news/templates
```

- [ ] **Step 4: `TEMPLATES.DIRS`'i temizle**

`cybernews/settings.py` icinde satir 104'u degistir:

```python
        'DIRS': [],
```

(Onceki hali `'DIRS': [BASE_DIR / 'templates'],` idi. `TEMPLATES` blogunun
tamami KALIR — Django admin'i `APP_DIRS` uzerinden kendi sablonlarini
kullanir.)

- [ ] **Step 5: Kapi A — hicbir seyin degismedigini kanitla**

```bash
docker compose restart teknoloji-api teknoloji-worker teknoloji-scheduler
sleep 5
docker compose ps
docker compose exec -T teknoloji-api python manage.py test news
curl -s -o /dev/null -w "health:%{http_code}\n" http://localhost:8000/api/v1/health/
curl -s -o /dev/null -w "admin:%{http_code}\n" http://localhost:8000/admin/login/
```

Beklenen: alti servis `Up` | `Ran 324 tests ... OK` | `health:200` |
`admin:200` (admin sablonlari `APP_DIRS`'ten gelmeye devam ediyor — bu adim
`DIRS: []` degisikliginin admin'i kirmadiginin kanitidir).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: servis edilmeyen olu kodu kaldir (app.py ve HTML sablonlari)

Django tarafi tamamen API-only: cybernews/urls.py yalniz admin/,
api/v1/ ve news.urls (hepsi api/... yollari) iceriyor, hicbir view
HTML render etmiyor. app.py (Flask prototipi) ne Dockerfile'da ne
docker-compose.yml'de referans ediliyor.

Kapanan bulgular:
- CodeQL py/flask-debug (app.py, debug=True)
- news/templates/news/index.html icindeki innerHTML tabanli DOM XSS

TEMPLATES.DIRS artik var olmayan bir dizini gosterdigi icin bosaltildi;
TEMPLATES blogu duruyor cunku admin sablonlari APP_DIRS'ten geliyor
(admin/login/ 200 ile dogrulandi).

scraper_multi.py SILINMEDI: canli kod, news/tasks.py ve news/views.py
onu kullaniyor.

Dogrulama: 324 test OK, alti servis Up, health 200, admin 200.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7: Merge ve push**

```bash
git checkout main
git merge --no-ff temizlik/olu-kod -m "Merge temizlik/olu-kod: servis edilmeyen app.py ve sablonlar"
git push origin main
git branch -d temizlik/olu-kod
```

---

### Task 2: LICENSE (MIT) ekle

**Files:**
- Create: `LICENSE`
- Modify: `README.md` (sonuna lisans bolumu)

**Interfaces:**
- Consumes: yok
- Produces: yok

- [ ] **Step 1: Dali ac**

```bash
git checkout main && git pull origin main
git checkout -b docs/mit-lisansi
```

- [ ] **Step 2: `LICENSE` dosyasini olustur**

```
MIT License

Copyright (c) 2026 AdanedhelWrites

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: `README.md` sonuna lisans bolumu ekle**

```markdown
## Lisans

Bu proje MIT lisansi ile yayimlanmistir. Ayrintilar icin [LICENSE](LICENSE)
dosyasina bakin.
```

- [ ] **Step 4: Kapi A**

```bash
docker compose exec -T teknoloji-api python manage.py test news
```

Beklenen: `Ran 324 tests ... OK` (kod degismedi, kanit amacli).

- [ ] **Step 5: Commit, merge, push**

```bash
git add LICENSE README.md
git commit -m "$(cat <<'EOF'
docs: MIT lisansi ekle

Depo acik kaynak ama lisans dosyasi yoktu; lisanssiz kodun varsayilani
"her hakki sakli"dir ve kimse kodu yasal olarak kullanamaz veya fork
edemez. Scorecard LicenseID bulgusunu da kapatir.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
git checkout main
git merge --no-ff docs/mit-lisansi -m "Merge docs/mit-lisansi: MIT lisansi"
git push origin main
git branch -d docs/mit-lisansi
```

---

### Task 3: Dockerfile'da pip ve setuptools yukselt

**Files:**
- Modify: `Dockerfile` (builder asamasi ve runtime asamasi)

**Interfaces:**
- Consumes: yok
- Produces: yok

Amac: taban imajin getirdigi `jaraco.context` ve `wheel` aciklarini kapatmak.
Bunlar `requirements.txt`'te degil, `python:3.11-slim`'in kendi setuptools
paketinin icinde vendored olarak geliyor.

- [ ] **Step 1: Dali ac ve mevcut durumu olc**

```bash
git checkout main && git pull origin main
git checkout -b fix/setuptools-yukseltme

MSYS_NO_PATHCONV=1 docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.74.0 image teknoloji-haberleri-api:latest \
  --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --format json \
  2>/dev/null | jq '[.Results[]? | select(.Class=="lang-pkgs") | .Vulnerabilities[]? | {id: .VulnerabilityID, pkg: .PkgName}]'
```

Beklenen (degisiklikten ONCE): `jaraco.context` ve `wheel` icin iki kayit.
Bu, degisiklik sonrasi karsilastirmanin temelidir.

- [ ] **Step 2: `Dockerfile` builder asamasina pip/setuptools yukseltmesi ekle**

`RUN apt-get update && apt-get upgrade -y && apt-get install ...` satirindan
SONRA, `COPY requirements.txt .` satirindan ONCE:

```dockerfile
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
```

- [ ] **Step 3: `Dockerfile` runtime asamasina ayni yukseltmeyi ekle**

Runtime asamasindaki (`FROM python:3.11-slim@sha256:...`, `AS builder`
OLMAYAN) `RUN apt-get ...` satirindan sonra ayni satir eklenir:

```dockerfile
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
```

Gerekce: son imajda kalan setuptools runtime asamasinin kendisinden gelir;
yalniz builder'i yukseltmek bulguyu kapatmaz.

- [ ] **Step 4: Tam kapi**

Global Constraints bolumundeki **tam kapiyi** bastan sona calistir (imaj
degistigi icin `docker compose up -d --build` sarttir, `restart` yetmez).

- [ ] **Step 5: Bulgunun gercekten kapandigini olc**

```bash
MSYS_NO_PATHCONV=1 docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:0.74.0 image teknoloji-haberleri-api:latest \
  --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --format json \
  2>/dev/null | jq '[.Results[]? | .Vulnerabilities[]?] | length'
```

Beklenen: `0`. Deger 0 degilse kalan bulgularin ne oldugunu yazdirip DUR.

- [ ] **Step 6: Commit, merge, push**

```bash
git add Dockerfile
git commit -m "$(cat <<'EOF'
fix: imajda pip ve setuptools'u yukselt

Taban imajin (python:3.11-slim) setuptools paketine gomulu
jaraco.context ve wheel icin iki HIGH bulgu vardi; bunlar
requirements.txt'te olmadigi icin ancak pip/setuptools yukseltmesiyle
kapanir. Hem builder hem runtime asamasina eklendi: son imajdaki
setuptools runtime asamasindan geliyor.

Dogrulama: trivy image ... --ignore-unfixed -> 0 bulgu (once 2),
tam kapi gecti (324 test OK, alti servis Up, sema 11 yol/0 uyari,
health 200, uctan uca istemci calisti).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
git checkout main
git merge --no-ff fix/setuptools-yukseltme -m "Merge fix/setuptools-yukseltme: imajda pip/setuptools yukseltmesi"
git push origin main
git branch -d fix/setuptools-yukseltme
```

---

### Task 4: `NewsArticle.link` alanina `unique=True`

**Files:**
- Modify: `news/models.py:11`
- Create: `news/migrations/0012_newsarticle_link_unique.py` (ad `makemigrations`
  ciktisina gore degisebilir)
- Test: `news/tests/test_modeller.py` (yoksa olusturulur)

**Interfaces:**
- Consumes: yok
- Produces: `NewsArticle.link` artik veritabani duzeyinde tekil. Sonraki
  gorevler bu kisiti varsayabilir.

- [ ] **Step 1: Dali ac ve veriyi kontrol et**

```bash
git checkout main && git pull origin main
git checkout -b fix/newsarticle-link-unique

docker compose exec -T teknoloji-api python manage.py shell -c "
from news.models import NewsArticle
from django.db.models import Count
d = NewsArticle.objects.values('link').annotate(n=Count('id')).filter(n__gt=1)
print('toplam:', NewsArticle.objects.count(), '| cift link grubu:', d.count())
for x in d[:10]: print(' ', x)
"
```

Beklenen: `cift link grubu: 0`. **Sifir degilse DUR** — migration cift
kayitlarda patlar; once temizleme stratejisi kullaniciya sorulmali.

- [ ] **Step 2: Basarisiz testi yaz**

`news/tests/test_modeller.py` dosyasina ekle (dosya yoksa olustur):

```python
from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from news.models import NewsArticle


class NewsArticleLinkTekilligiTests(TestCase):
    """link alani veritabani duzeyinde tekil olmali (diger bes bolumde oldugu gibi)."""

    def _kayit(self, link):
        return NewsArticle.objects.create(
            source='test',
            original_title='baslik',
            turkish_title='baslik',
            link=link,
            date=date(2026, 1, 1),
            original_date='2026-01-01',
        )

    def test_ayni_link_ikinci_kez_eklenemez(self):
        self._kayit('https://ornek.test/haber-1')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._kayit('https://ornek.test/haber-1')

    def test_farkli_linkler_eklenebilir(self):
        self._kayit('https://ornek.test/haber-1')
        self._kayit('https://ornek.test/haber-2')
        self.assertEqual(NewsArticle.objects.count(), 2)
```

- [ ] **Step 3: Testi calistir, DUSTUGUNU gor**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_modeller -v 2
```

Beklenen: `test_ayni_link_ikinci_kez_eklenemez` **FAIL** —
`IntegrityError` beklenirken hic istisna olusmuyor.

- [ ] **Step 4: Modeli degistir**

`news/models.py` satir 11:

```python
    link = models.URLField(unique=True, verbose_name='Link')
```

- [ ] **Step 5: Migration uret**

```bash
docker compose exec -T teknoloji-api python manage.py makemigrations news
```

Beklenen: `news/migrations/0012_*.py` olusturuldu (`Alter field link on
newsarticle`).

- [ ] **Step 6: Migration'i uygula ve testi tekrar calistir**

```bash
docker compose exec -T teknoloji-api python manage.py migrate news
docker compose exec -T teknoloji-api python manage.py test news.tests.test_modeller -v 2
```

Beklenen: iki test de PASS.

- [ ] **Step 7: Migration'in geri alinabilir oldugunu kanitla**

```bash
docker compose exec -T teknoloji-api python manage.py migrate news 0011
docker compose exec -T teknoloji-api python manage.py migrate news
```

Beklenen: iki komut da hatasiz. (Geri alma yolu calismazsa sorun canlida
fark edilmeden birikir.)

- [ ] **Step 8: Tam kapi**

Global Constraints'teki tam kapiyi calistir. Test sayisi artik **326**
olmali (324 + 2 yeni test).

- [ ] **Step 9: Commit, merge, push**

```bash
git add news/models.py news/migrations/ news/tests/test_modeller.py
git commit -m "$(cat <<'EOF'
fix: NewsArticle.link alanina unique kisiti ekle

Diger bes bolumde (CVEEntry.cve_id, Kubernetes/SRE/DevTools/AINews.link)
tekillik kisiti vardi, NewsArticle istisnaydi: yazma yolu
update_or_create(link=...) ile tekillik varsayiyordu ama sema bunu
garanti etmiyordu.

Migration oncesi veri kontrol edildi: 107 kayit, 0 cift link ->
temizlenecek veri yok. Geri alinabilirlik de dogrulandi
(migrate news 0011 -> migrate news).

Dogrulama: 326 test OK (2 yeni), tam kapi gecti.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
git checkout main
git merge --no-ff fix/newsarticle-link-unique -m "Merge fix/newsarticle-link-unique: link tekillik kisiti"
git push origin main
git branch -d fix/newsarticle-link-unique
```

---

### Task 5: vite 5 -> 6.4.3

**Files:**
- Modify: `frontend/package.json` (devDependencies.vite)
- Modify: `frontend/package-lock.json` (npm uretir)

**Interfaces:**
- Consumes: yok
- Produces: vite 6 ile calisan build zinciri. Task 7 bunun uzerine biner.

Kapanan Dependabot uyarilari: vite x3 + rollup + esbuild + @babel/core = **6**.
Son ucu vite'in transitive bagimliliklaridir, vite yukselince kendiliginden
duserler.

- [ ] **Step 1: Dali ac**

```bash
git checkout main && git pull origin main
git checkout -b deps/vite-6
```

- [ ] **Step 2: `frontend/.dockerignore` olustur (bu adim atlanamaz)**

Bu dosya bugun **yok** ve olmadan Step 5'teki `docker build` kesin olarak
su hatayla duser:

```
ERROR: invalid file request node_modules/.bin/baseline-browser-mapping
```

Sebep: `docker-compose.yml` `./frontend`'i konteynere bind mount ediyor,
dolayisiyla `npm install` host'taki `frontend/node_modules` dizinini
olusturuyor; `docker build ./frontend` de bu dizini build baglamina almaya
calisiyor ve icindeki sembolik baglantilarda takiliyor.

`frontend/.dockerignore` iceriği:

```
node_modules
dist
.dockerignore
```

(Kok dizindeki `.dockerignore` bu build'i etkilemez: o yalniz kok baglamla
yapilan backend build'i icin gecerlidir.)

- [ ] **Step 3: `frontend/package.json`'da vite surumunu yukselt**

```json
    "vite": "^6.4.3"
```

(`devDependencies` icinde. `@vitejs/plugin-react` satirina **DOKUNMA** —
mevcut `^4.2.1` araligi vite 6'yi destekler, 6.x'e cikarsa `vite ^8` ister.)

- [ ] **Step 4: Lockfile'i yenile ve build al**

```bash
docker compose exec -T teknoloji-frontend sh -c "npm install --no-audit --no-fund && npm run build"
```

Beklenen: kurulum hatasiz; `vite build` ciktisinda `dist/index.html`,
`dist/assets/*.css`, `dist/assets/*.js` ve `built in ...` satiri.
`npm error` veya `Unsupported engine` gorulurse DUR.

- [ ] **Step 5: Surumun gercekten degistigini dogrula**

```bash
docker compose exec -T teknoloji-frontend sh -c "npm ls vite --depth=0"
```

Beklenen: `vite@6.4.3` (veya daha yuksek 6.x).

- [ ] **Step 6: Kapi D — prod imaji da derlenmeli**

```bash
docker build -t frontend-vite6-dogrulama -f frontend/Dockerfile ./frontend
docker run -d --rm --name frontend-vite6-dogrulama \
  --network cybersecurity_news_teknoloji-network -p 3099:3000 frontend-vite6-dogrulama
sleep 3
curl -s -o /dev/null -w "prod-frontend:%{http_code}\n" http://localhost:3099/
docker rm -f frontend-vite6-dogrulama
docker rmi frontend-vite6-dogrulama
curl -s -o /dev/null -w "dev-frontend:%{http_code}\n" http://localhost:3000/
```

Beklenen: `prod-frontend:200` ve `dev-frontend:200`.

Build yine "invalid file request node_modules/..." ile duserse Step 2'deki
`.dockerignore` olusturulmamis demektir.

- [ ] **Step 7: Commit, merge, push**

```bash
git add frontend/package.json frontend/package-lock.json frontend/.dockerignore
git commit -m "$(cat <<'EOF'
build(deps): vite 5 -> 6.4.3

Alti Dependabot uyarisini kapatir: vite x3 dogrudan, rollup + esbuild +
@babel/core ise vite'in transitive bagimliliklari oldugu icin.

vite 6.4.3 engines: ^18.0.0 || ^20.0.0 || >=22.0.0 -> mevcut Node 18
yeterli, bu is Node yukseltmesi gerektirmiyor. @vitejs/plugin-react
4.x'te birakildi: 6.x'in peer bagimliligi vite ^8.0.0.

Ayrica frontend/.dockerignore eklendi: compose bind mount'u host'ta
node_modules olusturdugu icin `docker build ./frontend` build baglamina
o dizini alip sembolik baglantilarda duruyordu.

Dogrulama: npm install + npm run build hatasiz, prod imaj derlendi ve
200 dondu, dev sunucusu 200.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
git checkout main
git merge --no-ff deps/vite-6 -m "Merge deps/vite-6: vite 6.4.3"
git push origin main
git branch -d deps/vite-6
```

---

### Task 6: Node 18 -> 22

**Files:**
- Modify: `frontend/Dockerfile` (builder asamasi `FROM`)
- Modify: `docker-compose.yml` (`teknoloji-frontend.image`)

**Interfaces:**
- Consumes: Task 5'in vite 6 kurulumu
- Produces: Node 22 calisma ortami. **Task 7'nin on kosuludur** (react-router 7
  `engines: >=20.0.0` ister).

- [ ] **Step 1: Dali ac ve hedef digest'i al**

```bash
git checkout main && git pull origin main
git checkout -b deps/node-22

docker pull node:22-alpine
docker inspect node:22-alpine --format '{{index .RepoDigests 0}}'
```

Ciktidaki `node@sha256:...` degerini not al; asagida `<DIGEST>` yerine
yazilacak.

- [ ] **Step 2: `frontend/Dockerfile` builder asamasini guncelle**

```dockerfile
FROM node:22-alpine@sha256:<DIGEST> AS builder
```

(Yalniz builder asamasi. Ikinci asama `nginx:1.31-alpine@sha256:...` olarak
KALIR.)

- [ ] **Step 3: `docker-compose.yml`'de dev sunucusunun imajini guncelle**

`teknoloji-frontend` servisinde:

```yaml
    image: node:22-alpine
```

- [ ] **Step 4: Dev konteynerini yeni Node ile ayaga kaldir**

```bash
docker compose up -d --force-recreate teknoloji-frontend
sleep 15
docker compose exec -T teknoloji-frontend node --version
docker compose logs teknoloji-frontend --tail 20
```

Beklenen: `v22.x.x` | log'da `VITE v6...  ready in ...`.

**Tuzak:** bind mount'taki `node_modules` Node 18 ile kurulmustu; native
modul varsa uyumsuzluk cikabilir. Hata gorulurse:
`docker compose exec -T teknoloji-frontend sh -c "rm -rf node_modules && npm install --no-audit --no-fund"`.

- [ ] **Step 5: Kapi D**

```bash
docker compose exec -T teknoloji-frontend sh -c "npm run build"
docker build -t frontend-node22-dogrulama -f frontend/Dockerfile ./frontend
docker run -d --rm --name frontend-node22-dogrulama \
  --network cybersecurity_news_teknoloji-network -p 3099:3000 frontend-node22-dogrulama
sleep 3
curl -s -o /dev/null -w "prod-frontend:%{http_code}\n" http://localhost:3099/
docker rm -f frontend-node22-dogrulama
docker rmi frontend-node22-dogrulama
curl -s -o /dev/null -w "dev-frontend:%{http_code}\n" http://localhost:3000/
```

Beklenen: build hatasiz, `prod-frontend:200`, `dev-frontend:200`.

- [ ] **Step 6: Commit, merge, push**

```bash
git add frontend/Dockerfile docker-compose.yml
git commit -m "$(cat <<'EOF'
build: Node 18 -> 22 (frontend imaji ve dev sunucusu)

Node 18 destek disi (EOL) ve react-router 7 engines: >=20.0.0 istiyor;
bu yukseltme o isin on kosulu. Ayri bir is olarak yapildi ki Node
kaynakli bir kirilma react-router degisikligiyle karistirilmasin.

Taban imaj digest'e sabitlendi (depodaki mevcut bicime uygun).
nginx asamasi degismedi.

Dogrulama: node --version v22, vite build hatasiz, prod imaj 200,
dev sunucusu 200.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
git checkout main
git merge --no-ff deps/node-22 -m "Merge deps/node-22: Node 22'ye gecis"
git push origin main
git branch -d deps/node-22
```

---

### Task 7: react-router-dom 6 -> 7

**Files:**
- Modify: `frontend/package.json` (dependencies.react-router-dom)
- Modify: `frontend/package-lock.json` (npm uretir)

**Interfaces:**
- Consumes: Task 6'nin Node 22 ortami (zorunlu)
- Produces: yok

Kullanim yuzeyi olculdu ve dar: `BrowserRouter` (`frontend/src/main.jsx:3`),
`Routes` / `Route` / `NavLink` (`frontend/src/App.jsx:2`). Hepsi v7'de mevcut.

- [ ] **Step 1: Dali ac ve Node surumunu dogrula**

```bash
git checkout main && git pull origin main
git checkout -b deps/react-router-7
docker compose exec -T teknoloji-frontend node --version
```

Beklenen: `v22.x.x`. `v18` goruluyorsa Task 6 tamamlanmamis demektir — DUR.

- [ ] **Step 2: `frontend/package.json`'da surumu yukselt**

```json
    "react-router-dom": "^7.18.0"
```

- [ ] **Step 3: Kur ve build al**

```bash
docker compose exec -T teknoloji-frontend sh -c "npm install --no-audit --no-fund && npm run build"
docker compose exec -T teknoloji-frontend sh -c "npm ls react-router-dom --depth=0"
```

Beklenen: kurulum hatasiz, build hatasiz, `react-router-dom@7.18.x`.

**Tuzak:** v7 bazi API'leri `react-router` paketine tasidi ve
`react-router-dom`'dan yeniden disa aktardi. Build `does not provide an
export named` hatasi verirse, ilgili import `react-router-dom` yerine
`react-router`'dan alinir; degistirilen dosya commit mesajinda yazilir.

- [ ] **Step 4: Kapi E — tarayicida yedi rotayi gez**

```bash
docker compose restart teknoloji-frontend
sleep 10
curl -s -o /dev/null -w "dev-frontend:%{http_code}\n" http://localhost:3000/
```

Ardindan tarayicida `http://localhost:3000/` acilir ve **yedi rota da**
gezilir: `/`, `/news`, `/cve`, `/k8s`, `/sre`, `/devtools`, `/ai`.

Her rota icin beklenen: sayfa iceriginin gelmesi, ust menudeki aktif
baglantinin dogru vurgulanmasi (`NavLink` davranisi) ve **tarayici
konsolunda hata olmamasi**.

Bu adim atlanamaz: react-router calisma zamani bagimliligidir ve build'in
gecmesi rotalarin calistigini kanitlamaz.

- [ ] **Step 5: Prod imajini da dogrula**

```bash
docker build -t frontend-rr7-dogrulama -f frontend/Dockerfile ./frontend
docker run -d --rm --name frontend-rr7-dogrulama \
  --network cybersecurity_news_teknoloji-network -p 3099:3000 frontend-rr7-dogrulama
sleep 3
curl -s -o /dev/null -w "prod-frontend:%{http_code}\n" http://localhost:3099/
docker rm -f frontend-rr7-dogrulama
docker rmi frontend-rr7-dogrulama
```

Beklenen: `prod-frontend:200`.

- [ ] **Step 6: Commit, merge, push**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "$(cat <<'EOF'
build(deps): react-router-dom 6 -> 7

Iki Dependabot uyarisini kapatir. v7 Node >=20 istedigi icin Node 22
gecisinden (onceki is) sonra yapildi.

Kullanim yuzeyi dar: BrowserRouter (main.jsx), Routes/Route/NavLink
(App.jsx) — hepsi v7'de mevcut.

Dogrulama: npm install + build hatasiz, dev sunucusu 200, prod imaj
200 ve yedi rotanin tamami tarayicida gezildi (/, /news, /cve, /k8s,
/sre, /devtools, /ai), konsolda hata yok.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
git checkout main
git merge --no-ff deps/react-router-7 -m "Merge deps/react-router-7: react-router-dom 7"
git push origin main
git branch -d deps/react-router-7
```

---

### Task 8: Django 5.2.16 + DRF 3.18.1

**Files:**
- Modify: `requirements.txt` (uc satir)
- Modify: `cybernews/settings.py:188` (`STATICFILES_STORAGE` -> `STORAGES`)

**Interfaces:**
- Consumes: yok (onceki gorevlerden bagimsiz)
- Produces: Django 5.2 hattinda calisan uygulama

Bu planin **en riskli** isi. Kapiyi gecemezse dal silinir ve `main` onceki
gorevlerin tum kazanimlariyla saglam kalir.

- [ ] **Step 1: Dali ac**

```bash
git checkout main && git pull origin main
git checkout -b deps/django-5.2
```

- [ ] **Step 2: `requirements.txt`'i guncelle**

```
Django==5.2.16
djangorestframework==3.18.1
```

ve

```
psycopg2-binary==2.9.13
```

`djangorestframework` satirindaki `# DRF 3.18+ django>=5.2 ister; Django 4.2
LTS hattinda kaliyoruz` yorumu **silinir** (artik gecersiz).

- [ ] **Step 3: `cybernews/settings.py`'de depolama ayarini yeni bicime cevir**

Satir 188'deki

```python
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
```

yerine:

```python
# Django 5.1 STATICFILES_STORAGE'i kaldirdi; yerini STORAGES sozlugu aldi.
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
```

- [ ] **Step 4: Imajlari yeniden kur**

```bash
docker compose up -d --build teknoloji-api teknoloji-worker teknoloji-scheduler
sleep 10
docker compose ps
```

Beklenen: build hatasiz, alti servis `Up`.
`ResolutionImpossible` gorulurse DUR ve raporla.

- [ ] **Step 5: Surumlerin gercekten degistigini dogrula**

```bash
docker compose exec -T teknoloji-api python -c "import django, rest_framework; print('Django', django.get_version()); print('DRF', rest_framework.VERSION)"
```

Beklenen: `Django 5.2.16`, `DRF 3.18.1`.

- [ ] **Step 6: Test paketi**

```bash
docker compose exec -T teknoloji-api python manage.py test news
```

Beklenen: `Ran 326 tests ... OK` (Task 4 iki test ekledi).

- [ ] **Step 7: Django'ya ozel dort ek kanit**

```bash
# 1) Dagitim kontrolu
docker compose exec -T teknoloji-api python manage.py check --deploy

# 2) 5.2 yeni migration istiyor mu
docker compose exec -T teknoloji-api python manage.py makemigrations --check --dry-run

# 3) Celery worker ve beat aciliyor mu (testler bu yolu hic calistirmaz)
docker compose logs teknoloji-worker --tail 20
docker compose logs teknoloji-scheduler --tail 20

# 4) Admin arayuzu
curl -s -o /dev/null -w "admin:%{http_code}\n" http://localhost:8000/admin/login/
```

Beklenen:
1. `check --deploy` **hata** vermemeli (guvenlik uyarilari `W...` kodlariyla
   cikabilir, bunlar Django 4.2'de de vardi; **yeni** bir `E...` hatasi varsa DUR).
2. `No changes detected` — 5.2 yeni migration istemiyor. Istiyorsa DUR ve
   ne istedigini raporla.
3. Worker log'unda `celery@... ready.`, scheduler log'unda `beat: Starting...`.
4. `admin:200`.

- [ ] **Step 8: Tam kapinin kalan adimlari**

Sema kontrolu, canli HTTP ve uctan uca istemci adimlarini Global
Constraints'teki tam kapidan calistir.

Beklenen: `Yol sayisi: 11`, `warnings: {}`, `errors: {}`, `health:200`,
`schema:401`, `frontend:200`, istemci uctan uca calisti.

- [ ] **Step 9: Commit, merge, push**

```bash
git add requirements.txt cybernews/settings.py
git commit -m "$(cat <<'EOF'
deps: Django 4.2.30 -> 5.2.16, DRF 3.17.2 -> 3.18.1

Alti Dependabot uyarisini kapatir; hepsinin yamasi yalniz Django 5.2
hattinda vardi ve Django 4.2 LTS'in omru doldugu icin 4.2'de asla
kapanmayacaklardi. Dependabot'un tekrar tekrar actigi DRF 3.18
yukseltmesi de (PR #38) bu isle cozulur.

Kodda tek uyum degisikligi gerekti: STATICFILES_STORAGE Django 5.1'de
kaldirildi, yerine STORAGES sozlugu kondu (whitenoise backend'i ayni).
Django 5.x'te kaldirilan diger API'ler icin kod tarandi, baska kullanim
yoktu.

psycopg2-binary 2.9.12 -> 2.9.13 ayni sette dogrulandi.

Dogrulama: 326 test OK, Django 5.2.16 / DRF 3.18.1 dogrulandi,
check --deploy temiz, makemigrations --check "No changes detected",
celery worker ve beat acildi, admin 200, sema 11 yol / 0 uyari,
health 200, schema tokensiz 401, frontend 200, uctan uca istemci
calisti.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
git checkout main
git merge --no-ff deps/django-5.2 -m "Merge deps/django-5.2: Django 5.2.16 ve DRF 3.18.1"
git push origin main
git branch -d deps/django-5.2
```

- [ ] **Step 10: PR #38'i kapat**

Bu isin icerigi PR #38'i kapsadigi icin o PR artik gereksiz:

```bash
gh pr close 38 --comment "Bu yukseltme main'e Django 5.2.16 ile birlikte alindi (bkz. deps/django-5.2 merge'u). DRF 3.18.1 ve psycopg2-binary 2.9.13 dahil edildi."
```

---

### Task 9: Uyari temizligi (74 olu + 2 yanlis pozitif)

**Files:**
- Kod degisikligi **yok**. Yalniz GitHub code scanning uyarilarinin durumu.

**Interfaces:**
- Consumes: Task 1-8'in tamami (nihai sayimin gercegi yansitmasi icin en sonda)
- Produces: yok

**Bu gorev en sonda yapilir.** Onceki isler bittikten sonra bazi uyarilar
kendiliginden kapanmis olabilir; once yeniden sayilir, sonra kalan olu
kayitlar kapatilir.

- [ ] **Step 1: Taramalari tazele ve bitmelerini bekle**

```bash
gh workflow run trivy.yml --ref main
gh workflow run codeql.yml --ref main
gh workflow run scorecard.yml --ref main

# Hepsinin bitmesini bekle
until [ "$(gh run list --branch main --limit 8 --json status -q '[.[] | select(.status!="completed")] | length')" = "0" ]; do sleep 20; done
gh run list --branch main --limit 8
```

Beklenen: listedeki tum kosular `completed success`. Basarisiz olan varsa
once sebebi incelenir.

- [ ] **Step 2: Guncel durumu say ve olu kayitlari tespit et**

```bash
HEAD_SHA=$(git rev-parse HEAD)
echo "main HEAD: $HEAD_SHA"

echo "--- acik uyarilarin tarandigi commit'e gore dagilimi ---"
gh api repos/AdanedhelWrites/tech-radar/code-scanning/alerts --paginate \
  -q '.[] | select(.state=="open") | .most_recent_instance.commit_sha' | sort | uniq -c | sort -rn
```

Guncel `HEAD_SHA` **disindaki** commit'lere isaretli acik uyarilar olu
kayitlardir (o kategoriye bir daha yukleme gelmeyecegi icin kendiliginden
kapanamazlar).

- [ ] **Step 3: Kapatilacak listeyi uret ve gozden gecir**

```bash
HEAD_SHA=$(git rev-parse HEAD)
gh api repos/AdanedhelWrites/tech-radar/code-scanning/alerts --paginate \
  -q ".[] | select(.state==\"open\") | select(.most_recent_instance.commit_sha != \"$HEAD_SHA\") | [.number, .rule.id, .most_recent_instance.location.path] | @tsv" \
  | sort -k2 | tee /tmp/olu_uyarilar.tsv | head -20
wc -l < /tmp/olu_uyarilar.tsv
```

Beklenen: ~74 satir. **Satir sayisi 80'i asarsa DUR** — canli bir uyariyi
yanlislikla kapatma riski var, liste elle incelenmeli.

- [ ] **Step 4: Olu kayitlari gerekcesiyle kapat**

```bash
while IFS=$'\t' read -r num rule path; do
  if [ "$path" = "my-organization/my-app" ]; then
    yorum="2026-09-13'te emekliye ayrilan SARIF kategorisinden (.github/workflows/trivy.yml:build) kalan olu kayit. Aktif trivy kategorileri (trivy-fs, trivy-image-backend, trivy-image-frontend) bu bulguyu uretmiyor; kategoriye bir daha yukleme olmayacagi icin kendiliginden kapanamaz."
  else
    yorum="Paket surumu guncellendi; uyari eski imaj taramasinin paket yolunda kaldi. Guncel imajda bu bulgu yok."
  fi
  gh api -X PATCH "repos/AdanedhelWrites/tech-radar/code-scanning/alerts/$num" \
    -f state=dismissed -f dismissed_reason="won't fix" -f dismissed_comment="$yorum" \
    --jq '.number, .state' >/dev/null && echo "kapatildi: $num ($rule)"
done < /tmp/olu_uyarilar.tsv
```

- [ ] **Step 5: Iki yanlis pozitifi kapat**

```bash
# k8s_scraper.py: icerik filtresi, URL dogrulamasi degil
K8S_NUM=$(gh api repos/AdanedhelWrites/tech-radar/code-scanning/alerts --paginate \
  -q '.[] | select(.state=="open") | select(.rule.id=="py/incomplete-url-substring-sanitization") | .number' | head -1)
gh api -X PATCH "repos/AdanedhelWrites/tech-radar/code-scanning/alerts/$K8S_NUM" \
  -f state=dismissed -f dismissed_reason="false positive" \
  -f dismissed_comment="Bu kontrol bir URL dogrulamasi degil: Kubernetes CHANGELOG'undaki tablo satirlarini (sha512, indirme linkleri) ayiklayan bir icerik filtresi. 'registry.k8s.io' bir guvenlik siniri olarak degil, atlanacak satiri tanimak icin araniyor."

# api_v1/views.py: DRF'in guvenli 4xx mesajlari
STE_NUM=$(gh api repos/AdanedhelWrites/tech-radar/code-scanning/alerts --paginate \
  -q '.[] | select(.state=="open") | select(.rule.id=="py/stack-trace-exposure") | .number' | head -1)
gh api -X PATCH "repos/AdanedhelWrites/tech-radar/code-scanning/alerts/$STE_NUM" \
  -f state=dismissed -f dismissed_reason="false positive" \
  -f dismissed_comment="Yanit govdesine giden metin DRF'in APIException.detail degeri: dogrulama/yetki hatalarinda kasitli olarak tuketiciye gosterilen, kuratorlu mesajlar. Gercekten beklenmeyen istisnalarin dustugu 5xx yolu zaten genel bir mesaja indiriliyor ve istisna sunucuda logger.exception ile kaydediliyor (handle_exception, news/api_v1/views.py)."
```

- [ ] **Step 6: Nihai sayim**

```bash
echo "--- Dependabot acik ---"
gh api repos/AdanedhelWrites/tech-radar/dependabot/alerts --paginate \
  -q '.[] | select(.state=="open") | [.security_advisory.severity, .dependency.package.name] | @tsv' | sort | uniq -c

echo "--- Code scanning acik ---"
gh api repos/AdanedhelWrites/tech-radar/code-scanning/alerts --paginate \
  -q '.[] | select(.state=="open") | .rule.id' | sort | uniq -c | sort -rn
```

Beklenen:
- Dependabot: **cikti yok** (0 acik).
- Code scanning: **~8 uyari**, tamami spec bolum 7'deki bilinerek kabul
  edilenler (PinnedDependenciesID x4, BranchProtectionID, CodeReviewID,
  FuzzingID, CIIBestPracticesID).

Beklenenden fazlasi kaliyorsa, kalanlarin listesi kullaniciya raporlanir.

- [ ] **Step 7: Sonucu belgele**

`docs/superpowers/specs/2026-09-22-guvenlik-temizligi-design.md` dosyasinin
basindaki `**Durum:**` satirini guncelle. Asagidaki `N`, Step 6'da olculen
gercek sayimla degistirilir (hem spec'te hem commit mesajinda):

```markdown
- **Durum:** Uygulandi (2026-09-22). Sonuc: Dependabot 14 -> 0,
  code scanning 89 -> N.
```

```bash
git add docs/superpowers/specs/2026-09-22-guvenlik-temizligi-design.md
git commit -m "$(cat <<'EOF'
docs: guvenlik temizligi sonucunu spec'e isle

Dependabot 14 -> 0; code scanning 89 -> N. Kalan uyarilarin
tamami spec bolum 7'de gerekcesiyle bilinerek kabul edilenlerdir.

74 olu kayit dismiss edildi (56'si emekliye ayrilan SARIF
kategorisinden, 18'i bayat paket yolundan) ve iki CodeQL yanlis
pozitifi gerekcesiyle kapatildi.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
git push origin main
```

---

## Sonuc kontrol listesi

Plan bittiginde su dogrulanmis olmali:

- [ ] Dependabot acik uyari: **0**
- [ ] Code scanning acik uyari: **~8**, hepsi belgeli bilinerek kabul
- [ ] `main`'de 326 test yesil
- [ ] Alti compose servisi Up, `health` 200, `schema` tokensiz 401,
      frontend 200
- [ ] Django 5.2.16 + DRF 3.18.1 calisiyor
- [ ] Node 22, vite 6, react-router 7 ile frontend yedi rotada calisiyor
- [ ] `LICENSE` dosyasi mevcut
- [ ] PR #38 kapatildi
- [ ] Tum workflow'lar (`ci`, `trivy`, `codeql`, `scorecard`, `gitleaks`,
      `zizmor`, `dast-zap`) `main`'de yesil
