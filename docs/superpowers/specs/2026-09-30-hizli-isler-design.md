# Hizli Isler — Tasarim

- **Tarih:** 2026-09-30
- **Durum:** UYGULANDI (2026-09-30). Plan: [`../plans/2026-09-30-hizli-isler.md`](../plans/2026-09-30-hizli-isler.md)
- **Kapsam:** 2026-09-30 durum raporunun "hizli isler" listesi: eski
  `/api/*/fetch/` uclarinin korunmasi, `SECRET_KEY`/`ALLOWED_HOSTS` korumasi
  (GUVENLIK-PLANI P4), acik Dependabot PR'lari #44 ve #45
- **On kosul (tamamlandi):** PR #43 (Django 5.2.16 -> 5.2.17) 2026-09-30'da
  merge edildi (`156c358`); yerel yigin yeniden derlendi, 326 test, health/admin/
  frontend 200, worker ready, beat starting dogrulandi.

## 1. Neden

2026-09-30 durum raporunda iki guvenlik acigi ve iki bekleyen PR kaldi:

1. **Eski `POST /api/*/fetch/` uclari herkese acik ve korumasiz.**
   `news/views.py`'deki alti `fetch_*` view'i `AllowAny`; throttle, bolum kilidi
   ve soguma yok. `fetch_news` ve `fetch_cves` `days`'i dogrulamadan task'a
   veriyor. ADR-0003 karar 5'in uc katmanli korumasi (kaynak siteler ve ceviri
   kotasi icin) yalniz v1'de gecerli; eski uclar onu tamamen atliyor.
2. **Uretim `SECRET_KEY`'i placeholder.** `settings.py` varsayilani
   `django-insecure-change-in-production`; `docker-compose.yml` uc serviste
   `your-secret-key-here-change-in-production` veriyor ve `DEBUG=False`.
   Helm, k8s, README ve kokteki `values.yaml` de ornek degerler tasiyor.
   `ALLOWED_HOSTS` varsayilani `*`.

## 2. Is 1 — Eski fetch uclari (karar: A)

**Kullanici karari:** "Cek" butonunu anonim kullanicilar da kullanacak; uclar
acik kalir ama korunur.

### Secilen yaklasim: v1 `RefreshGate`'i paylasmak

Eski uclar `news/api_v1/refresh.py::trigger()` uzerinden gecer. Bolum kilidi ve
15 dk soguma **v1 ile ayni Redis anahtarlarini** kullanir: kaynak sitelere ve
ceviri kotasina giden yuk, tetikleyenin kim oldugundan bagimsiz, global olarak
sinirlanir (ADR-0003 karar 5'in "kac token olursa olsun" ilkesi).

| Elenen | Neden |
|---|---|
| Ayri gate (farkli onek) | Iki bagimsiz soguma; yuk ikiye katlanabilir |
| Yalniz IP basina throttle | Farkli IP'lerden eszamanli cift kazimayi engellemez |
| `IsAdminUser` | Kullanici anonim kullanimi istedi |

### Degisiklikler

1. **`refresh.trigger()`** iki istege bagli parametre kazanir:
   - `task_kwargs: Optional[dict]` — `{'skip_existing': True}` ile birlestirilir
     (`{'skip_existing': True, **task_kwargs}`).
   - `trigger_label: str = 'api'` — `fetchrun_trigger` header'i.
   v1 cagrilari parametre vermez; davranislari **degismez**.
2. **Girdi dogrulamasi:** `news/serializers.py`'deki alti `Fetch*RequestSerializer`
   kullanilir (bugun dordu kullaniliyor; `fetch_news` ve `fetch_cves` kullanmiyor).
   - `sources`: `ListField(max_length=20, child=CharField(max_length=100))`.
     Bilinmeyen kaynak adlari scraper'larda zaten filtreleniyor (dogrulandi:
     `cve/k8s/sre/devtools_scraper`, `ai_scraper`, `scraper_multi`); kaynak
     listesine karsi dogrulama eklenmez (YAGNI).
   - `FetchCVERequestSerializer.days` varsayilani **30 -> 7**: bugunku
     `fetch_cves` davranisi (`request.data.get('days', 7)`) ve task varsayilani
     ile ayni kalsin.
3. **Tek yardimci:** alti kopya view govdesi `news/views.py::_tetikle(request, bolum)`
   yardimcisina toplanir. Bolum -> (serializer, cache anahtarlari, gorunen ad)
   eslemesi `_FETCH_BOLUMLERI` sozlugundedir. View adlari ve URL'ler degismez.
   `fetch_*_task` importlari `views.py`'den kalkar (kullanilmaz hale gelir).
4. **Yanit sozlesmesi** (eski zarf `success/message/count/data` korunur):

   | `trigger` sonucu | HTTP | Govde |
   |---|---|---|
   | `started` | 200 | `success: true`, "... cekimi baslatildi", `job_id` |
   | `already_running` | 200 | `success: true`, "... cekimi zaten suruyor", `job_id` |
   | `cooldown` | 429 + `Retry-After` | `success: false`, "... N dk sonra tekrar deneyin", `retry_after` |
   | gecersiz girdi | 400 | `success: false`, "Gecersiz istek" |
   | beklenmeyen hata | 500 | `success: false`, `GENEL_SUNUCU_HATASI` (loglanir) |

5. **Cache yalniz `started`'da silinir.** Bugun her istekte siliniyor; soguma
   veya calisan is varken silmek frontend'e bos liste gosterirdi. Silme artik
   kuyruga atmadan hemen **sonra** olur; task ilk cache'i 10 kayittan sonra
   kurdugu icin bu sira pratikte farksizdir.
6. **Frontend:** `frontend/src/services/api.js`'e ortak
   `istekHataMesaji(err, varsayilan)` yardimcisi; sunucunun `message`'ini
   tercih eder. Alti bilesenin fetch `catch` blogu bunu kullanir; kullanici
   "Request failed with status code 429" yerine soguma mesajini gorur.
7. **`trigger` etiketi `admin` kalir.** `FetchRun.TETIKLEYICILER`'de
   `('admin', 'Arayuz')` olarak zaten "Arayuz" gosteriliyor; yeni deger icin
   migration gerekmez.

### Kabul edilen sinirlar

- v1 tuketicisi tetikledikten sonra arayuz butonu 15 dk sogumada kalir ve tersi.
  Istenen davranis budur.
- Beat'in baslattigi isler hala kilit almaz (refresh.py'de bilinen sinir).
- `already_running` durumunda frontend'in toast'i hala "basladi" der (bilesen
  metni sabit). Kayitlar zaten akacagi icin zararsiz; metin degistirilmez.
- ADR-0003 karar 1'in "`news/views.py` dokunulmaz" maddesinden ikinci bilincli
  sapma (birincisi ADR-0006 karar 5). URL'ler ve basari yaniti zarfi degismez;
  yeni olan 429 ve `job_id`/`retry_after` alanlaridir. ADR-0003'e not dusulur.

## 3. Is 2 — `SECRET_KEY` ve `ALLOWED_HOSTS` (GUVENLIK-PLANI P4)

1. **Yeni modul `cybernews/ayar_dogrulama.py`**, saf fonksiyon
   `dogrulanmis_secret_key(anahtar, debug) -> str`:
   - `debug=True`: anahtar bossa gelistirme anahtari doner (yerel calisma kirilmaz).
   - `debug=False` ve anahtar bos, bilinen ornek degerlerden biri,
     `django-insecure` onekli ya da 32 karakterden kisa -> `ImproperlyConfigured`.
   - Bilinen ornekler: `your-secret-key-here-change-in-production`,
     `buraya-guclu-rastgele-secret-key-yazin-min-50-karakter`,
     `min-50-karakter-rastgele-guclu-bir-key`,
     `django-insecure-change-in-production` (gitleaks baseline'daki bes
     bulgunun ve compose'un tum degerleri; git gecmisinden dogrulandi).
   `settings.py` bunu kullanir. Test: `news/tests/test_ayar_dogrulama.py`
   (test kesfi yalniz `news` altinda calistigi icin).
2. **`ALLOWED_HOSTS`** varsayilani `*` -> `localhost,127.0.0.1`; girdiler
   `strip` edilir, bos girdiler atilir. Django test calistiricisi `testserver`'i
   kendisi ekler.
3. **Compose:** uc servisteki placeholder -> `SECRET_KEY=${SECRET_KEY:?...}`
   (`.env`'den). Api/worker/scheduler'a
   `ALLOWED_HOSTS=localhost,127.0.0.1,teknoloji-api` (nginx `Host: localhost`
   iletir; Vite proxy `changeOrigin` ile `teknoloji-api` gonderir; ag ici
   tuketici `teknoloji-api:8000` kullanir).
4. **`.env.example`** `SECRET_KEY=` satiri ve uretim komutu kazanir. Yerel
   `.env`'e `openssl rand -hex 32` ile anahtar yazilir (degeri hicbir cikti
   veya commit'e girmez; `.env` gitignore'da). **Yan etki:** mevcut admin
   oturumu bir kez duser. Ikinci yan etki: `DEBUG` varsayilani `False`
   oldugu icin hostta ortam degiskeni vermeden `python manage.py ...`
   calistirmak artik reddedilir; README'ye `DEBUG=True` ile yerel calisma
   notu eklenir. (Entrypoint, CI ve DAST anahtari zaten veriyor; dogrulandi.)
5. **CI `manifests` isi** `required` ve `:?` yuzunden kirilacagi icin:
   `helm lint/template --set secrets.secretKey=ci-sahte-...` ve
   `SECRET_KEY=ci-sahte docker compose config`.
6. **Helm:** `secrets.secretKey: ""`; `templates/secret.yaml`'da
   `required "secrets.secretKey zorunlu (openssl rand -hex 32)"`.
7. **k8s:** `k8s/02-secret.yaml` -> `k8s/02-secret.yaml.example` (`git mv`);
   README'deki atiflar ve ornek deger guncellenir. Uzanti bilincli olarak
   `.yaml` ile **bitmez**: README'deki `kubectl apply -f k8s/` dizindeki her
   `.yaml`'i uygular; `02-secret.example.yaml` adi gercek secret'in ustune
   placeholder yazardi (GUVENLIK-PLANI'ndaki ad bu yuzden duzeltilir).
8. **Kokteki `values.yaml` silinir.** Helm chart'in bayat kopyasi (README'de
   "referans" diye geciyor), hicbir yerde kullanilmiyor, placeholder tasiyor.
9. **`.gitleaksignore` degismez.** Girdiler gecmis commit'lere sabitli; gecmis
   degismedigi icin silinirlerse gecmis taramasi yeniden kirmizi olur.
   GUVENLIK-PLANI'ndaki "baseline'dan da silinmeli" maddesi bu yuzden duzeltilir.

**Faz B'ye not:** Kubernetes probe'lari pod IP'siyle `Host` gonderir; Helm
configmap'ine acik bir `ALLOWED_HOSTS` girmezse probe'lar 400 alir.
`dbPassword`/`postgresPassword` placeholder'lari da Faz B'de `required` olur.

## 4. Is 0 — Dependabot PR'lari #44 ve #45

GUVENLIK-PLANI §3 proseduru: check'ler yesil mi, gerekiyorsa *Update branch*,
merge. **#45 (actions grubu)** icin diff satir satir okunur: SHA sabitlemesi
+ surum yorumu korunmali; `trivy.yml`'deki `$/` referansi (bkz. `151cdd7`
zizmor regresyonu) degismemeli. Kirmizi check varsa merge edilmez, rapor edilir.

## 5. Sira ve dogrulama

| Sira | Is | Dal | Kapi |
|---|---|---|---|
| 1 | #44 | (GitHub PR) | check'ler + `:3000` 200 |
| 2 | #45 | (GitHub PR) | check'ler + diff incelemesi |
| 3 | Is 2 | `fix/secret-key-korumasi` | Tam kapi + placeholder ile acilmayi reddetme + CI `manifests` |
| 4 | Is 1 | `fix/eski-fetch-kapisi` | Tam kapi + tarayici: "Cek"e iki kez bas |
| 5 | Belgeler | ayni dallar | — |

**Tam kapi** (proje kurali): compose yeniden derleme, 6 servis Up,
`manage.py test news` (326 + yeni testler), sema 0 uyari, `/api/v1/health/`
200, `/api/v1/schema/` tokensiz 401, `:3000` 200, `scripts/ornek_istemci.py`
uctan uca.

Her is ayri dal, `--no-ff` merge (depo kalibi). Kapiyi gecemeyen is geri
alinir, push edilmez, rapor edilir (guvenlik temizligi spec'i bolum 9 ile ayni).

## 6. Kapsam disi

- Faz B (PostgreSQL + Helm dogrulamasi) — ayri tasarim
- Olu kod temizligi (`gui*.py`, `scraper.py`, `scraper_light.py`,
  `static/js/app.js`) ve `views.py`'nin get/stats/export kopyalari — ayri is.
  (Kokteki `values.yaml` istisna: placeholder tasidigi icin burada silinir.)
- Frontend bilesenlerinin ortak hook'a toplanmasi
- `dbPassword`/`postgresPassword` `required` yapilmasi (Faz B)
