# Guvenlik Temizligi — Tasarim

- **Tarih:** 2026-09-22
- **Durum:** UYGULANDI (2026-09-22). Sonuc: Dependabot 14 -> **0**,
  code scanning 89 -> **11**. Kalan 11'in tamami bolum 7'deki bilinerek
  kabul edilenlerdir; ikisi bu is sirasinda eklendi (setuptools yukseltmesi
  iki `pip install` satiri getirdi, Scorecard bunlari "pipCommand not pinned
  by hash" sayiyor — ayni kategoride zaten kabul edilmis bir bulgu turu).
  `VulnerabilitiesID` 15 acikten 1'e dustu (skor 0 -> 9).
- **Kapsam:** Depodaki tum acik guvenlik bulgularinin (Dependabot + GitHub code
  scanning) kapatilmasi ya da bilinerek kabul edilmesi
- **Baslangic durumu:** Dependabot 14 acik, code scanning 89 acik

## 1. Neden simdi ve neden bu kapsam

Depo acik kaynak birakildi. Acik kaynak bir depoda uc sey ayri ayri onemli:

1. Gercek aciklar kapali olmali.
2. Panelde gorunen uyarilar **gercegi yansitmali** — 89 uyarinin 74'unun olu
   kayit oldugu bir panel, gercek bulgulari da gorunmez yapar.
3. Depo hukuken kullanilabilir olmali. Lisans dosyasi yoksa varsayilan "her
   hakki sakli"dir; kimse kodu yasal olarak kullanamaz veya fork edemez.

Bu tasarim ucunu birden hedefler.

**Onceki oturumun KARAR 2'si (Django 5.2 ertelensin) bu tasarimla IPTAL
edilmistir.** Gerekce asagida bolum 4'te, olcume dayali olarak yazili.

## 2. Bulgularin gercek dagilimi

Panelde gorunen sayi ile gercekte yapilacak is ayni degil. Olculen dagilim:

### Dependabot (14 acik)

| Paket | Adet | Yama | Not |
|---|---|---|---|
| django | 6 | 5.2.15 / 5.2.16 | Yalniz Django 5.2 hattinda var |
| vite | 3 | 6.4.3 | Major; yalniz build zamani (devDependency) |
| rollup | 1 | 4.59.0 | vite'in transitive'i |
| esbuild | 1 | 0.25.0 | vite'in transitive'i |
| @babel/core | 1 | 7.29.6 | vite'in transitive'i |
| react-router | 2 | 7.18.0 | Major; **calisma zamani** bagimliligi |

### Code scanning (89 acik)

| Grup | Adet | Gercek durum |
|---|---|---|
| Terk edilmis SARIF kategorisi | 56 | **Olu kayit** — asagida bolum 3 |
| Bayat paket yolu | 18 | **Olu kayit** — paket zaten guncellendi |
| setuptools'a gomulu paketler | 2 | **Gercek ve canli** (jaraco.context, wheel) |
| Scorecard PinnedDependencies | 4 | 2'si arac celiskisi, 2'si karar |
| Scorecard meta | 6 | 1'i lisans, 1'i bagimlilik yansimasi, 4'u repo ayari |
| py/flask-debug | 1 | **Olu kodda** (app.py) |
| py/stack-trace-exposure | 1 | Yanlis pozitif (DRF'in guvenli 4xx mesaji) |
| py/incomplete-url-substring-sanitization | 1 | Yanlis pozitif (icerik filtresi) |

**Yani 89 uyarinin yalnizca ~9'u gercek ilgi gerektiriyor.**

## 3. Olu uyarilarin kok nedeni (olculdu, varsayilmadi)

56 uyari `my-organization/my-app` yolunda gorunuyor ve **terk edilmis bir SARIF
kategorisine** ait: `.github/workflows/trivy.yml:build`. Bu kategoriye son
yukleme **2026-09-13** tarihinde yapilmis (commit `eb5f93ae`, 76 sonuc).

Mevcut `trivy.yml` artik acik kategoriler kullaniyor: `trivy-fs`,
`trivy-image-backend`, `trivy-image-frontend`. GitHub bir uyariyi ancak **ayni
kategoriye** yeni bir analiz gelip uyari o analizde bulunmadiginda "fixed"
isaretler. Terk edilmis kategoriye bir daha yukleme olmayacagi icin bu 56 uyari
**hicbir kod degisikligiyle kapanmaz**.

Kanit: aktif `trivy-image-backend` kategorisi `e856b371`'den bu yana sonuc
sayisi **2** (B1 OS paket yukseltmesinden once de 2, sonra da 2). Yani canli
imajda OS paket acigi yok; kalan 2 sonuc taban imajin setuptools'una gomulu
`jaraco.context` ve `wheel`.

**Sonuc: bu 56 + 18 = 74 uyari icin tek dogru islem dismiss'tir.**

## 4. Django 5.2 karari

Onceki oturumda ertelenmisti. Bu tasarimda yapilacak, cunku erteleme
gerekcesinin dayandigi risk olculdu ve dusuk cikti:

- **Bagimlilik cozumu kanitlandi.** `python:3.11-slim` konteynerinde
  `pip install --dry-run` ile: `Django==5.2.16` + `djangorestframework==3.18.1`
  + mevcut tum paketler (django-redis 5.4.0, django-cors-headers 4.9.0,
  django-celery-beat 2.9.0, whitenoise 6.12.0, drf-spectacular[sidecar] 0.30.0,
  celery 5.6.3, psycopg2-binary 2.9.13) **temiz cozuluyor**. Catisma yok.
- **Kodda tek engel var.** `cybernews/settings.py:188`'deki
  `STATICFILES_STORAGE` Django 5.1'de kaldirildi; yerine `STORAGES` sozlugu
  gelecek. Django 5.x'te kaldirilan diger API'ler icin kod tarandi
  (`DEFAULT_FILE_STORAGE`, `get_storage_class`, `index_together`,
  `django.utils.timezone.utc`, `USE_L10N`, `make_random_password`, `CICharField`
  ailesi, `NullBooleanField`, `ugettext`/`force_text` ailesi): **baska kullanim
  yok**. `test_gemini.py`'deki `timezone.utc` `datetime`'in, Django'nun degil.
- **Django 5.2 ayrica PR #38'i cozer.** Dependabot'un tekrar tekrar actigi
  DRF 3.18 yukseltmesi bugun build'i kiriyor; Django 5.2 bu dongyu bitirir.

Erteleme gerekcesi ortadan kalkti, fakat **regresyon riski sifir degil**: 324
test her seyi kapsamiyor. Bu yuzden Django isi icin bolum 6'da dort ek kanit
tanimlanmistir.

## 5. Is listesi

Sira ilkesi: **ucuz ve guvenli isler once, riskli is en sonda.** Boylece Django
zaten temizlenmis bir depoya iner ve Django kirilip geri alinsa bile diger tum
kazanimlar `main`'de kalir.

Her is **ayri dal, ayri commit, ayri dogrulama kapisi**. Bir is kapisini
gecemezse **o is geri alinir**, kirik birakilmaz, sonrakine gecilir.

| # | Is | Kapattigi | Risk sinifi |
|---|---|---|---|
| 1 | Olu kodu sil | py/flask-debug + DOM XSS | A |
| 2 | LICENSE (MIT) ekle | LicenseID | A |
| 3 | Dockerfile'da pip + setuptools yukselt | 2 canli Trivy bulgusu | B |
| 4 | `NewsArticle.link` -> `unique=True` | Acik is (veri butunlugu) | C |
| 5 | vite 5 -> 6.4.3 | vite x3 + rollup + esbuild + @babel/core = 6 | D |
| 6 | Node 18 -> 22 | (7'nin on kosulu) | D |
| 7 | react-router-dom 6 -> 7 | react-router x2 | E |
| 8 | Django 5.2.16 + DRF 3.18.1 | django x6 (+ VulnerabilitiesID) | F |
| 9 | Uyari temizligi (74 olu + 2 yanlis pozitif) | 76 | A |

### Is 1 — Olu kodu sil

Silinecek: `app.py`, `templates/`, `news/templates/`.

Gerekce: Django tarafi **tamamen API-only**. `cybernews/urls.py` yalniz
`admin/`, `api/v1/` ve `news.urls` (hepsi `api/...` yollari) iceriyor; hicbir
view HTML template render etmiyor. `app.py` (Flask prototipi) ne Dockerfile'da
ne `docker-compose.yml`'de referans ediliyor.

Bu silme iki bulguyu kalici kapatir: `py/flask-debug` (app.py:140 `debug=True`)
ve `news/templates/news/index.html`'deki `innerHTML` tabanli DOM XSS.

**Tuzak:** silmeden once `grep` ile hicbir Python dosyasinin, `urls.py`'nin,
`settings.py`'nin (`TEMPLATES.DIRS`) veya testin bu dosyalara referans
vermedigi dogrulanmali. `settings.py`'deki `TEMPLATES.DIRS` `BASE_DIR /
'templates'` gosteriyorsa, dizin silinince Django'nun sikayet etmedigi ama
kafa karistirdigi bir ayar kalir — ayar da temizlenmeli.

### Is 2 — LICENSE (MIT)

Kok dizine standart MIT metni. Telif satiri: `Copyright (c) 2026 AdanedhelWrites`
(depo sahibi; farkli bir ad/kurum isteniyorsa uygulama sirasinda sorulur). `README.md`'ye lisans
satiri eklenir.

### Is 3 — pip + setuptools yukseltmesi

`Dockerfile`'in her iki asamasinda pip ve setuptools guncellenir, boylece taban
imajin getirdigi `jaraco.context` ve `wheel` acigi kapanir. Ayni `RUN`
katmaninda yapilir.

**Tuzak:** setuptools yukseltmesi derleme davranisini degistirebilir; kapi B
zorunludur.

### Is 4 — `NewsArticle.link` unique

`link = models.URLField(unique=True, ...)` + migration. Diger bes bolumde bu
kisit zaten var; `NewsArticle` istisnaydi.

Veri kontrolu yapildi: 107 kayit, **0 cift link**. Migration'in temizleyecegi
veri yok.

**Tuzak:** `news/tasks.py` bu modele `update_or_create(link=...)` ile yaziyor;
kisit eklendikten sonra yarista iki islem ayni link'i yazarsa
`IntegrityError` mumkun. Testler bu yolu kapsiyor mu kontrol edilmeli; degilse
davranis degismedigi icin ek test gerekmez, ama migration'in tersine
alinabilirligi (`migrate news <onceki>`) dogrulanmali.

### Is 5 — vite 6

`frontend/package.json`'da `vite` `^5.0.8` -> `^6.4.3`.

Olculen gercekler:
- vite 6.4.3 `engines`: `^18.0.0 || ^20.0.0 || >=22.0.0` -> **Node 18 yeterli**,
  bu is Node yukseltmesi gerektirmez.
- Kurulu `@vitejs/plugin-react@4.7.0` vite 6'yi destekler (4.6.0'in peer
  araligi `^4.2.0 || ^5.0.0 || ^6.0.0 || ^7.0.0-beta.0`). **`@vitejs/plugin-react`
  6.x'e YUKSELTILMEMELI** — onun peer'i `vite: ^8.0.0`.

### Is 6 — Node 18 -> 22

`frontend/Dockerfile` builder asamasi ve `docker-compose.yml`'deki
`teknoloji-frontend` servisi `node:18-alpine` kullaniyor. Node 18 destek disi
(EOL) ve **is 7'nin on kosulu**.

Hedef: `node:22-alpine` (gecerli LTS), digest'e sabitlenmis olarak — depodaki
mevcut sabitleme bicimine uygun.

Bu is kendi basina dogrulanabilir oldugu icin react-router'dan **ayri** tutulur:
Node 22 build'i kirarsa, bunu react-router degisikligiyle karistirmadan
goruruz.

### Is 7 — react-router-dom 7

`react-router-dom` `^6.30.6` -> `^7.18.x`. react-router 7 `engines`:
`>=20.0.0` — bu yuzden is 6 once gelir.

Kullanim yuzeyi olculdu ve cok dar: yalniz `BrowserRouter` (`main.jsx`),
`Routes`, `Route`, `NavLink` (`App.jsx`). Hepsi v7'de mevcut. Beklenen
degisiklik minimal, ama **calisma zamani** bagimliligi oldugu icin kapi E
(tarayicida rota gezinme) zorunludur.

### Is 8 — Django 5.2.16 + DRF 3.18.1

`requirements.txt`:
- `Django==4.2.30` -> `Django==5.2.16`
- `djangorestframework==3.17.2` -> `djangorestframework==3.18.1`
  (ve satirdaki "Django 4.2 LTS hattinda kaliyoruz" yorumu kaldirilir)
- `psycopg2-binary==2.9.12` -> `2.9.13` (PR #38'in digeri; ayni sette cozuldugu
  dogrulandi)

`cybernews/settings.py`:

```python
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
```

`STATICFILES_STORAGE` satiri kaldirilir.

Bu is tamamlandiginda **PR #38 kapatilabilir** (icerigi bu ise dahil edilmistir).

### Is 9 — Uyari temizligi

`gh api` ile toplu dismiss:

| Grup | Adet | `dismissed_reason` | Gerekce metni |
|---|---|---|---|
| Terk edilmis kategori | 56 | `won't fix` | 2026-09-13'te emekliye ayrilan SARIF kategorisinden kalan olu kayit; aktif tarama bu bulgulari uretmiyor |
| Bayat paket yolu | 18 | `won't fix` | Paket surumu guncellendi; uyari eski imaj yolunda kaldi |
| k8s_scraper.py:447 | 1 | `false positive` | `'registry.k8s.io' in line` bir URL dogrulamasi degil, CHANGELOG tablo satiri filtresi |
| api_v1/views.py:42 | 1 | `false positive` | DRF'in APIException `.detail` mesajlari kasitli olarak kullaniciya gosterilir; 5xx yolu zaten genel mesaja dusuyor |

Dismiss geri alinabilir bir islemdir ve gerekce uyarinin uzerinde yazili kalir.
**Bu is en sona birakilir** ki nihai sayim gercek durumu yansitsin.

## 6. Dogrulama kapilari

| Sinif | Kapsam | Kapi |
|---|---|---|
| A | Dosya silme / ekleme, panel islemi | 324 test + sema 11 yol/0 uyari + health 200. Kanit: **hicbir sey degismemeli** |
| B | Imaj (Dockerfile) | Tam kapi (asagida) |
| C | Veritabani (migration) | Tam kapi + migration geri alinabilirligi |
| D | Frontend build zinciri | `npm ci` + `npm run build` + prod imaj build + `:3000` -> 200 |
| E | Frontend calisma zamani | D + **tarayicida yedi rotanin gezilmesi** (`/`, `/news`, `/cve`, `/k8s`, `/sre`, `/devtools`, `/ai`) ve konsolda hata olmamasi |
| F | Django surumu | Tam kapi + dort ek kanit (asagida) |

**Tam kapi** (mevcut proje kurali, degistirilmedi):

1. `docker compose up -d --build teknoloji-api teknoloji-worker teknoloji-scheduler`
2. `docker compose ps` -> alti servis de Up
3. `docker compose exec -T teknoloji-api python manage.py test news` -> 324 test OK
4. Sema: 11 yol, 0 uyari, 0 hata
5. Canli HTTP: `/api/v1/health/` 200 | `/api/v1/schema/` tokensiz 401 | `:3000` 200
6. `scripts/ornek_istemci.py` uctan uca; sonra `ornek_istemci_durum.json` silinir

**Django icin dort ek kanit** (324 testin kapsamadigi yerler):

1. `manage.py check --deploy` — yeni surumun uyarilari
2. `manage.py makemigrations --check --dry-run` — 5.2 yeni migration istiyor mu
3. **Celery worker ve beat aciliyor mu** — ikisi de Django'yu import eder ve
   test paketi bu yolu hic calistirmaz; `docker compose logs` ile "ready"
   satiri gorulmeli
4. `/admin/login/` 200 — admin arayuzu 5.2'de sagliklı mi

## 7. Kapsam disi ve bilinerek kabul edilenler

Bunlar **cozulmeyecek**; gerekcesi burada yazili kalsin diye listeleniyor:

| Bulgu | Adet | Neden birakildi |
|---|---|---|
| Scorecard PinnedDependencies (trivy.yml `$/`) | 2 | zizmor `$/`'i GitHub'in resmi self-repository sozdizimi sayiyor ve `./`'yi hatali buluyor; Scorecard tam tersini istiyor. Iki arac celisiyor, zizmor'un tarafi secildi |
| Scorecard PinnedDependencies (pip hash) | 2 | Tam transitive kapanisin hash'lenmesi ve kilit dosyasinin surekli bakimi gerekir; iki medium bulgunun bedeli bunu karsilamiyor |
| BranchProtectionID | 1 | Tek kisilik depoda `main`'e dogrudan push'u kapatmak is akisini yavaslatir |
| CodeReviewID | 1 | Onaylayan ikinci kisi yok; kendi PR'ini onaylamak metrigi tatmin etmez |
| FuzzingID | 1 | Fuzzer entegrasyonu (OSS-Fuzz/CIFuzz) bu projenin buyuklugune gore orantisiz |
| CIIBestPracticesID | 1 | Harici bir rozet basvuru sureci; kod isi degil |

**`VulnerabilitiesID` bu listede degil:** o, Dependabot aciklarinin yansimasi —
is 5-8 bitince kendiliginden duzelmesi beklenir.

## 8. Beklenen sonuc

| | Baslangic | Hedef |
|---|---|---|
| Dependabot acik | 14 | **0** |
| Code scanning acik | 89 | **~8** |

Kalan ~8'in tamami bolum 7'deki bilinerek kabul edilen kalemlerdir.

## 9. Basarisizlik halinde

Bir is dogrulama kapisini gecemezse:

1. O isin degisikligi geri alinir (`git checkout` / `git revert`), **push
   edilmez**.
2. Neyin kirildigi raporlanir.
3. Sirasi gelen bir sonraki ise gecilir.

Kirik agac birakilmaz, ileri dogru hata ayiklama yapilmaz. Bu kural ozellikle
is 8 (Django) icin gecerlidir: Django kirilirsa is 1-7'nin kazanimlari `main`'de
kalmis olur.

## 10. Bu tasarimin kapsamadigi

- Kubernetes/Helm'e deploy (hic deploy edilmedi; manifestler yalniz dosya)
- Gercek bir sunucuya yayin ("yayin" burada: `main`'e push + yerel compose
  yiginini yeni surumlerle ayaga kaldirip uctan uca dogrulama)
- Frontend'in islevsel yeniden tasarimi
- Django 5.2'nin getirdigi yeni ozelliklerin benimsenmesi (yalniz uyumluluk
  hedefleniyor)
