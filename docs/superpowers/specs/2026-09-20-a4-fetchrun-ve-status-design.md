# A4 — `FetchRun` Gorunurlugu ve `GET /api/v1/status/` — Tasarim Dokumani

- **Tarih:** 2026-09-20
- **Durum:** Onaylandi (bolum 1-2 kullanici onayindan gecti 2026-09-20; bolum 3-5 ayni oturumda varsayim olarak yazildi, kullanici incelemesi bekleniyor). Uygulanmadi.
- **Kapsam:** `FetchRun` modeli ve migration; Celery sinyalleriyle otomatik satir acma/kapatma; alti `fetch_*` task'inin ve `retranslate_pending_task`'in donus sozlesmesinin zenginlestirilmesi; `GET /api/v1/status/`; admin duzeltmeleri
- **Kapsam disi:** drf-spectacular / ornek istemci / README (A5); `last_seen_at` (ADR-0005'te ertelendi); SRE ve DevTools kaynak incelemesi (bkz. 1.3, ayri is); Helm/Kubernetes (Faz B); alarm/bildirim gonderimi
- **Iliskili:** [ADR-0003](../../ADR-0003-Entegrasyon-API-v1.md) bolum 11 (bu tasarimin selefi), [ADR-0004](../../ADR-0004-Ceviri-Saglayici-Zinciri.md) (`by_provider` acik isi), [ADR-0005](../../ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md) (saklama, `stopped_reason` anlaminin genislemesi)
- **Selef spec:** `2026-09-12-entegrasyon-api-v1-design.md` bolum 11. **Bu dokuman onun yerine gecer**; 11.2'deki alan listesi ve 11.3'teki yanit govdesi burada guncellenmistir.
- **Migration:** **Var** (`0011_fetchrun`). Dagitimda worker/scheduler durdurma ve migration sonrasi api/worker/scheduler yeniden baslatma adimi zorunludur (ADR-0003: 2026-09-12'de atlanan yeniden baslatma bir CVE cekimini dusurmustu).

## 1. Amac

Cekim ve ceviri hattinda ne oldugunu **log eselemeden** gorebilmek.

### 1.1 Problem

Bugun tek gorunurluk worker loglarindaki `print()` satirlaridir: ucucu, aranabilir degil, konteyner yeniden baslayinca kaybolur. Bu dokuman yazilirken uc gun icinde dort ayri olay yasandi ve **dordu de yalnizca log eselenerek** bulundu:

| Tarih | Olay | Bugun nasil gorunuyor |
|---|---|---|
| 2026-09-17 18:12 | `fetch_cve_task` `disk I/O error` ile dustu | Celery'ye `succeeded` doner; hata yalniz donus govdesinde |
| 2026-09-18 12:07 | CVE tablosu elle bosaltildi (710 → 282 satir) | Hicbir yerde iz yok; silme bir task'in icinde bile degil |
| 2026-09-18 15:05 | `retranslate_pending_task` `DatabaseError` ile comdu | Celery'de `raised`; o turda diger bolumler hic yukseltme almadi |
| 2026-09-18–20 | `fetch_sre_task` / `fetch_devtools_task` her turda `success: False` | Alarma benziyor ama **saglikli** durum (bkz. 1.3) |

### 1.2 Basari kriterleri

1. Comen, asili kalan veya hata donduren bir tur, log okumadan gorulebilir.
2. Bir bolumun kaynagi bozuldugunda (`fetched_count` birkac tur 0) bu, sagliklı "yeni kayit yok" durumundan **ayirt edilebilir**.
3. Task disinda olan bir silme (tablo bosalmasi) turlar arasi farktan anlasilabilir.
4. Tuketici uygulama, veri tazeligini tek bir uctan sorgulayabilir.
5. Ceviri kalitesinin turdan tura gidisati (`by_provider`) kayit altina alinir.

### 1.3 Tasarimi degistiren bulgu — `success: False` iki farkli seyi anlatiyor

`fetch_sre_task` ve `fetch_devtools_task` 2026-09-18'den 20'ye kadar **her turda** `{'success': False, 'count': 0}` dondu. Loglar kaynaklarin aslinda kayit dondurdugunu gosteriyor (Google Cloud SRE 6, Seq 5, PostgreSQL 5, Moodle 2...); `_drop_existing` hepsini eliyor cunku kayitlar zaten veritabaninda. Yani durum sagliklidir: **bu turda yeni kayit yok.**

Mevcut donus sozlesmesi bunu hata ile ayni bayraga sikistiriyor:

```python
if entries:
    ...
    return {'success': True, 'count': saved_count}
return {'success': False, 'count': 0}      # "yeni kayit yok" da buraya dusuyor
except Exception as e:
    return {'success': False, 'error': str(e)}
```

`FetchRun.status` bu bayraktan turetilseydi SRE ve DevTools sagliklı olduklari halde her turda `failure` gorunur, pano ilk gunden kirmizi olur ve alarm korlugu yaratirdi — A4'un amacinin tam tersi.

Spec 11.2'nin `fetched_count` **ve** `saved_count`'u ayri alanlar olarak istemesinin sebebi budur: "kaynak bozuk" (`fetched=0`) ile "yeni kayit yok" (`fetched>0, saved=0`) ancak boyle ayrilir. Selef spec hakliydi; bugunku donus sozlesmesi onu besleyecek kadar zengin degil. **Bu tasarim donus sozlesmesini zenginlestirir ve durum semantigini yeniden tanimlar (bolum 3.2).**

> SRE/DevTools kaynaklarinin gercekten yeni icerik uretip uretmedigi **ayri bir istir** ve bu tasarimin kapsami disindadir. A4 yalnizca ayrimi gorunur kilar.

## 2. Secilen Yaklasim

**Sinyal iskeleti + zengin donus sozlesmesi** (brainstorming'de "Secenek C").

- `task_prerun` / `task_postrun` / `task_failure` sinyalleri `FetchRun` satirini acar ve kapatir. Comen tur **kendiliginden** yakalanir; task govdelerinde `try/finally` tekrarina gerek kalmaz.
- Zengin sayaclar (`fetched_count`, `translation_failures`, `total_after`, `by_provider`, `stopped_reason`) yalnizca task'in icinde bilinir; task'lar bunlari **donus sozlesmesine** ekler, sinyal oradan okur.

Proje bu kalibi zaten kullaniyor: `news/api_v1/job_signals.py` refresh kilidini `task_postrun` ile birakir ve `NewsConfig.ready` icinde baglanir.

### 2.1 Elenen alternatifler

| Alternatif | Neden elendi |
|---|---|
| Yalniz sinyaller, donus sozlesmesi degismeden | `fetched_count`, `translation_failures` ve `by_provider` donus govdesinde yok; sinyal onlara erisemez |
| Her task govdesinde acikca ac/kapat (selef spec'in yolu) | Yedi task'ta tekrar eden `try/finally`; comen turu yakalamak dogru kurulmus `finally`'ye bagli kalir, sinyalde ise bedava gelir |
| Operator verisini de `/status/`'a koymak | Dis sozlesme sisər; Gemini butcesi gibi icsel alanlar tuketicinin bagimli olabilecegi seylere doner ve geri almak zorlasir (kullanici karari) |
| Ayri `/api/v1/diagnostics/` ucu | Iki uc, iki yetkilendirme kurali, iki test yuzeyi; admin zaten operator icin dogru yer (kullanici karari) |
| `deleted_count` alani | `total_after` ile buyuk olcude ortusuyor; turlar arasi fark ayni bilgiyi veriyor (kullanici karari) |

## 3. Bilesenler

### 3.1 `news/models.py` — `FetchRun` (yeni, migration `0011_fetchrun`)

| Alan | Tip | Icerik |
|---|---|---|
| `section` | `CharField(20)`, indexli | `cve`, `news`, `kubernetes`, `sre`, `devtools`, `ai`, `retranslate` |
| `trigger` | `CharField(10)` | `beat`, `api`, `admin` (bkz. 3.3) |
| `started_at` | `DateTimeField`, indexli | Satir acilis ani |
| `finished_at` | `DateTimeField(null=True)` | Bos + eski `started_at` = asili tur |
| `status` | `CharField(10)` | `running`, `success`, `failure` |
| `fetched_count` | `IntegerField(default=0)` | Kaynaklardan donen kayit sayisi |
| `saved_count` | `IntegerField(default=0)` | Veritabanina yazilan |
| `translation_failures` | `IntegerField(default=0)` | Basarisiz ceviri sayisi |
| `total_after` | `IntegerField(default=0)` | Tur sonunda bolumun toplam satir sayisi |
| `by_provider` | `JSONField(default=dict)` | `{"gemini": n, "libretranslate": n}` |
| `stopped_reason` | `CharField(30), blank` | retranslate icin `gemini_budget` / `no_provider` / bos |
| `error` | `TextField(blank)` | Hata ozeti (kisaltilmis, bkz. 5) |

`Meta.ordering = ['-started_at']`; `indexes = [Index(fields=['section', '-started_at'])]`.

Bu model **v1 delta akisina girmez**: `updated_at` alani yoktur, hicbir delta ucu onu dondurmez.

### 3.2 Durum semantigi

| Kosul | `status` |
|---|---|
| Satir acildi, henuz kapanmadi | `running` |
| Task istisna atti (`task_failure`) | `failure` + `error` |
| Task donusunde `error` anahtari var | `failure` + `error` |
| Bunlarin disinda (sayilar ne olursa olsun) | `success` |

**`saved_count = 0` basarisizlik degildir.** `fetched_count > 0, saved_count = 0` sagliklıdir ("yeni kayit yok"). `fetched_count = 0`'in birkac tur surmesi kaynak sorununa isarettir; bu **yorum panoya aittir**, satirin durumuna degil (1.3).

### 3.3 `news/fetch_runs.py` (yeni) — sinyal iskeleti

```python
TASK_BOLUMLERI = {
    'news.tasks.fetch_news_task': 'news',
    'news.tasks.fetch_cve_task': 'cve',
    'news.tasks.fetch_k8s_task': 'kubernetes',
    'news.tasks.fetch_sre_task': 'sre',
    'news.tasks.fetch_devtools_task': 'devtools',
    'news.tasks.fetch_ai_news_task': 'ai',
    'news.tasks.retranslate_pending_task': 'retranslate',
}
```

- **`task_prerun`:** task adi haritada degilse hicbir sey yapmaz. Aksi halde `FetchRun(section=..., trigger=..., status='running')` yazar ve `task_id`'yi bir alanla degil, surec ici bir sozlukle (`{task_id: fetchrun_id}`) esler — `FetchRun`'a `task_id` alani eklemeyiz, disari sizmasi gereken bir bilgi degil.
- **`task_postrun`:** `retval` bir sozlukse sayaclari okur, `total_after`'i bolum modelinden sayar, `status`'u 3.2'ye gore belirler, `finished_at`'i yazar.
- **`task_failure`:** `status='failure'`, `error` = istisnanin kisaltilmis metni, `finished_at` simdi.
- **Sinyal hicbir kosulda task'i dusurmez.** Tum govde `try/except Exception` icindedir ve hata yalnizca loglanir (`job_signals.py` ile ayni kalip: "kilit birakilamazsa is basarisiz sayilmaz").
- `NewsConfig.ready` icinde import edilir.

**`trigger` nasil belirlenir:** varsayilan `beat`. Manuel tetikleyen iki cagri noktasi Celery header'i gecer: `news/api_v1/refresh.py` (`trigger='api'`) ve `news/views.py`'deki fetch view'lari (`trigger='admin'`). Sinyal header'i `sender.request` uzerinden okur; yoksa `beat` kabul eder.

> **Selef spec'ten bilincli sapma:** ADR-0003 "`news/views.py` degismez" diyordu. Burada `views.py`'de degisen tek sey `.delay(...)` cagrilarina bir Celery header'i eklenmesidir; hicbir HTTP sozlesmesi, yanit govdesi veya URL degismez. Gerekce: 2026-09-18'deki tablo bosalmasi bu yoldan geldi ve `trigger` alani onu ayirt etmenin tek yolu.

### 3.4 `news/tasks.py` — zenginlestirilmis donus sozlesmesi

Alti `fetch_*` task'inin donusu:

```python
{'success': bool, 'count': saved_count,          # mevcut alanlar, degismez
 'fetched_count': int, 'translation_failures': int}
```

`success` alani **korunur** (frontend ve v1 refresh onu okuyor, ADR-0003 karar 6), ama `FetchRun.status` ondan turetilmez (3.2).

`retranslate_pending_task` bugun zaten `translated`, `failed`, `upgraded`, `stopped`, `stopped_reason`, `by_provider`, `sections` donduruyor — **degismez**; sinyal bunlari su sekilde esler:

| `FetchRun` alani | retranslate donusundeki karsiligi |
|---|---|
| `saved_count` | `translated + upgraded` (yazilan kayit sayisi) |
| `translation_failures` | `failed` |
| `fetched_count` | **0** — retranslate hicbir kaynaga gitmez, feed'e bakmadan calisir. Bu bolumde `fetched_count = 0` kaynak arizasi anlamina **gelmez**; 1.3'teki yorum yalnizca alti veri bolumu icin gecerlidir |
| `by_provider` | aynen |
| `stopped_reason` | aynen |
| `total_after` | 0 — retranslate tek bir bolume ait degildir, toplam satir sayisi anlamsizdir |

**Saklama:** 30 gunden eski `FetchRun` satirlari `retranslate_pending_task` sonunda silinir (selef spec 11.2).

### 3.5 `news/api_v1/views.py` — `StatusView`

`V1APIView` tabanindan turer: token zorunlu, `v1_read` throttle'ina tabi, tek bicim hata sozlesmesi gecerli. `news/api_v1/urls.py`'ye `path('status/', ...)` eklenir.

```json
{
  "generated_at": "2026-09-20T19:03:00Z",
  "sections": {
    "cve": {
      "last_success_at": "2026-09-20T18:10:00Z",
      "last_status": "success",
      "last_fetched_count": 268,
      "last_saved_count": 37,
      "pending_translation": 0,
      "total": 1015
    }
  }
}
```

- `sections` alti veri bolumunu icerir; `retranslate` **yer almaz** (operator verisi).
- Hic `FetchRun` satiri yoksa `last_*` alanlari `null`, `pending_translation` ve `total` yine de dogru doner.
- Gemini butcesi, rezerve, devre kesici, `by_provider`, `stopped_reason`, `trigger`, `error` **bu uca girmez**.
- **Selef spec'ten bilincli sapma:** 11.3'teki `translation: {circuit_open, cooldown_remaining_seconds}` alani cikarildi. Tuketici zaten kayit bazinda `needs_translation` goruyor; global devre durumu onun kararini degistirmiyor ve sozlesmeye kalici bir ic detay sokuyor (kullanici karari).

### 3.6 `news/admin.py`

| Degisiklik | Ayrinti |
|---|---|
| `FetchRun` kaydedilir | Tamamen salt okunur (`has_add_permission`/`has_change_permission` False). `list_display`: bolum, durum, tetikleyici, baslangic, sure, fetched/saved, `total_after`, `stopped_reason`. `list_filter`: bolum, durum, tetikleyici, baslangic tarihi |
| `DevToolsEntry` ve `AINewsEntry` kaydedilir | Su an admin'de hic gorunmuyorlar |
| Alti modelde `needs_translation` `list_filter`'a eklenir | "Ceviri bekleyenleri goster" tek tik |
| Alti modelde `translation_provider` `list_filter` ve `list_display`'e eklenir | Hangi kaydin hangi saglayicidan geldigi listede gorunur |
| **Detay sayfasinda orijinal/Turkce yan yana** | Salt okunur bir `karsilastirma` alani: iki sutunlu HTML tablo (solda orijinal, sagda Turkce), altinda mevcut duzenlenebilir Turkce alanlar. Duzenleme bugunku gibi acik kalir |
| Liste gorunumunde kisa onizleme | Turkce basligin ilk ~80 karakteri; tam metin listeye konmaz (uzun CVE aciklamalari listeyi okunmaz yapar) |

## 4. Veri Akisi

```
Beat / API / admin  ->  fetch_*_task
                          |
   task_prerun  -->  FetchRun(status='running', started_at=now, trigger=...)
                          |
                    task govdesi (degismez; donus zenginlesti)
                          |
   task_postrun -->  sayaclar retval'den, total_after modelden sayilir,
                     status 3.2'ye gore, finished_at=now
   task_failure -->  status='failure', error=<kisaltilmis>, finished_at=now

GET /api/v1/status/  ->  bolum basina son FetchRun + canli sayimlar
Django admin         ->  FetchRun listesi (salt okunur) + ceviri karsilastirmasi
```

## 5. Hata Durumlari

| Durum | Davranis |
|---|---|
| Sinyal `FetchRun` yazamadi (DB hatasi) | Loglanir, task etkilenmez. Gorunurluk katmani isin kendisini dusurmez |
| `task_prerun` satir acti ama surec oldu (worker kill) | Satir `running` + eski `started_at` olarak kalir; **aranan sinyal budur** (asili tur) |
| Worker alt sureci `prerun` ile `postrun` arasinda geri donusturuldu | Surec ici esleme kaybolur ve satir `running` kalir — yani gercekte basarili bir tur "asili" gorunur (yanlis pozitif). Bu, `worker_max_tasks_per_child` ayarlanirsa ortaya cikar; projede **ayarli degildir** (dogrulandi: `cybernews/celery.py` ve `settings.py`'de yok). Kabul edilen sinir: ayar ileride acilirsa esleme yerine `FetchRun`'a `task_id` alani eklenmelidir |
| `retval` sozluk degil veya beklenen anahtarlar yok | Sayaclar 0 kalir, `status='success'`; sinyal istisna atmaz |
| `error` metni cok uzun | Ilk 2000 karaktere kisaltilir |
| Ayni `task_id` icin iki kez `task_postrun` | Surec ici eslemeden `pop` edilir; ikinci cagri sessizce yok sayilir |
| Hic `FetchRun` yokken `/status/` cagrildi | `last_*` alanlari `null`; 200 doner, hata degil |

## 6. Test Plani

TDD. Hicbir test gercek Celery isi kuyruga atmaz, gercek aga cikmaz, `FLUSHDB` kullanmaz.

| Dosya | Kapsam |
|---|---|
| `test_fetchrun.py` (yeni) | Sinyal satir acar/kapatir; istisnada `status=failure` + `error`; `retval`'den sayaclar okunur; `total_after` dogru sayilir; **`fetched>0, saved=0` durumu `success` olur** (1.3 regresyonu); bozuk `retval` sinyali dusurmez; 30 gunden eski satirlar temizlenir; `trigger` header'dan okunur, yoksa `beat` |
| `test_status.py` (yeni) | Tokensiz 401; bolum basina son basarili cekim ve bekleyen ceviri sayisi dogru; hic `FetchRun` yokken `last_*` null ve 200; `retranslate` bolumu yanitta yer almaz; Gemini/devre alanlari yanitta **yok** |
| `test_admin.py` (yeni) | `FetchRun` salt okunur (ekleme/degistirme izni yok); alti model `needs_translation` ile filtrelenebilir; karsilastirma alani orijinal ve Turkce metni birlikte dondurur |

Mevcut 268 testin hicbiri kirilmamalidir.

## 7. Canli Dogrulama Hedefleri

1. Bir Beat turundan sonra alti bolum icin birer `FetchRun` satiri olusur; `trigger='beat'`.
2. Arayuzden "Getir" tetiklenince olusan satirin `trigger`'i `admin` olur.
3. SRE ve DevTools satirlari `status='success'` ve `fetched_count > 0, saved_count = 0` gosterir (1.3'un dogrulanmasi).
4. `/api/v1/status/` yanitindaki `total` degerleri veritabanindaki gercek sayilarla birebir uyusur.
5. Admin'de bir CVE kaydinin detayinda orijinal ve Turkce metin yan yana okunabilir.

## 8. Kapsam Disi ve Sonraki Isler

- **A5:** drf-spectacular semasi, `/api/v1/docs/`, ornek istemci, README. `id` yerine `cve_id`/`link` uzerinden upsert kurali orada yazili hale gelir (ADR-0005 8.1).
- **SRE/DevTools kaynak incelemesi:** 1.3'teki bulgu bu kaynaklarin gercekten yeni icerik uretip uretmedigini sormuyor; A4 sonrasi `FetchRun` verisiyle ayri bir is olarak ele alinir.
- **Alarm/bildirim:** `FetchRun` veriyi uretir; bir esik asildiginda bildirim gondermek ayri bir karardir.
- **Faz B:** PostgreSQL ve Helm; `FetchRun` tablosu tasinacak veriye eklenir.
