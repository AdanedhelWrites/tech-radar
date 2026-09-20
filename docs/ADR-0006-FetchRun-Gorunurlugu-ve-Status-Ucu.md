# ADR 0006: `FetchRun` Gorunurlugu, Durum Semantigi ve `GET /api/v1/status/`

## Status
Accepted — 2026-09-20. **Uygulandi ve `main`'de** (2026-09-21, merge commit `1268ac5`; migration `0011_fetchrun`). Canlida dogrulandi (bkz. asagida).

Tasarim: [`superpowers/specs/2026-09-20-a4-fetchrun-ve-status-design.md`](superpowers/specs/2026-09-20-a4-fetchrun-ve-status-design.md). Uygulama plani: [`superpowers/plans/2026-09-20-a4-fetchrun-ve-status.md`](superpowers/plans/2026-09-20-a4-fetchrun-ve-status.md).

**Bu karar [ADR-0003](ADR-0003-Entegrasyon-API-v1.md) bolum 11'in (A4) yerine gecer.** O bolum 2026-09-12'de yazilmisti; Gemini yukseltmesi, [ADR-0005](ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md) ve asagidaki dort vaka ondan sonra geldi.

## Context

Cekim ve ceviri hattinda tek gorunurluk worker loglarindaki `print()` satirlariydi: ucucu, aranabilir degil, konteyner yeniden baslayinca kaybolur. Bu kararin yazildigi haftada dort ayri olay yasandi ve **dordu de yalnizca log eselenerek** bulundu:

| Tarih | Olay | O gun nasil gorunuyordu |
|---|---|---|
| 2026-09-17 18:12 | `fetch_cve_task` `disk I/O error` ile dustu | Celery'ye `succeeded` doner; hata yalniz donus govdesinde |
| 2026-09-18 12:07 | CVE tablosu elle bosaltildi (710 → 282 satir) | Hicbir yerde iz yok; silme bir task'in icinde bile degil |
| 2026-09-18 15:05 | `retranslate_pending_task` `DatabaseError` ile comdu | Celery'de `raised`; o turda diger bolumler hic yukseltme almadi |
| 2026-09-18–20 | `fetch_sre_task` / `fetch_devtools_task` her turda `success: False` | Alarma benziyordu ama **saglikli** durumdu (bkz. asagida) |

### Tasarimi degistiren bulgu — `success: False` iki farkli seyi anlatiyordu

`fetch_sre_task` ve `fetch_devtools_task` gunlerce her turda `{'success': False, 'count': 0}` dondu. Loglar kaynaklarin aslinda kayit dondurdugunu gosteriyordu (Google Cloud SRE 6, Seq 5, PostgreSQL 5, Moodle 2...); `_drop_existing` hepsini eliyordu cunku kayitlar zaten veritabanindaydi. Yani durum sagliklidir: **bu turda yeni kayit yok.**

Mevcut donus sozlesmesi bunu hata ile ayni bayraga sikistirmisti:

```python
if entries:
    return {'success': True, 'count': saved_count}
return {'success': False, 'count': 0}      # "yeni kayit yok" da buraya dusuyordu
```

`FetchRun.status` bu bayraktan turetilseydi iki bolum sagliklı olduklari halde her turda `failure` gorunur, pano ilk gunden kirmizi olur ve alarm korlugu yaratirdi — bu kararin amacinin tam tersi. ADR-0003 bolum 11.2'nin `fetched_count` **ve** `saved_count`'u ayri alanlar olarak istemesinin sebebi buymus; bugunku donus sozlesmesi onu besleyecek kadar zengin degildi.

## Decision

1. **`FetchRun` modeli** (migration `0011_fetchrun`). Her cekim ve retranslate calistirmasi bir satir birakir: `section`, `trigger`, `started_at`, `finished_at`, `status`, `fetched_count`, `saved_count`, `translation_failures`, `total_after`, `by_provider`, `stopped_reason`, `error`.

   ADR-0003 bolum 11.2'nin listesine uc alan eklendi: **`total_after`** (tur sonunda bolumun satir sayisi — turlar arasi fark, task disinda olan silmeleri gorunur kilar; yukaridaki 2026-09-18 vakasini yakalardi), **`by_provider`** (ADR-0004'un acik isi) ve **`stopped_reason`** (ADR-0005 ile anlami genisledi). `deleted_count` elendi: `total_after` ayni bilgiyi veriyor.

   Model **v1 delta akisina girmez**: `updated_at` alani yoktur, hicbir delta ucu onu dondurmez. Operator teshisi icindir.

2. **Durum semantigi.** `failure` **yalnizca** task istisna attiginda veya donusunde `error` anahtari oldugunda. Bunun disinda, sayilar ne olursa olsun, `success`. **`saved_count = 0` basarisizlik degildir**; `fetched_count > 0, saved_count = 0` sagliklıdir ("yeni kayit yok"). `fetched_count = 0`'in birkac tur surmesi kaynak sorununa isarettir ama bu **yorum panoya aittir, satirin durumuna degil**.

   Bunun zorunlu sonucu: **`fetched_count` `_drop_existing` filtresinden ONCE sayilir.** Filtreden sonra sayilsaydi "kaynak bozuk" ile "yeni kayit yok" ayni degere cokerdi ve ayrim anlamsizlasirdi.

3. **Satirlari Celery sinyalleri yazar** (`news/fetch_runs.py`): `task_prerun` satiri `running` acar, `task_postrun` donus sozlesmesinden sayaclari okuyup kapatir, `task_failure` comen turu yakalar. **Task govdeleri degismedi**; yalnizca donus sozlesmeleri `fetched_count` ve `translation_failures` ile zenginlesti. Proje bu kalibi `news/api_v1/job_signals.py`'de zaten kullaniyordu.

   Sinyal hicbir kosulda task'i dusurmez: her govde `try/except Exception` icindedir ve hata yalnizca loglanir.

4. **`GET /api/v1/status/` bilincli olarak dardir.** Yalniz tuketicinin tazelik sorusunu yanitlar: bolum basina `last_success_at`, `last_status`, `last_fetched_count`, `last_saved_count`, `pending_translation`, `total`. Gemini butcesi, rezerve, devre kesici, `by_provider`, `stopped_reason`, `trigger`, `error` ve `retranslate` bolumu **bu uca girmez**; operator verisi `FetchRun`'da ve admin'de yasar.

   Gerekce sozlesme dayanikliligidir: bu ucun dondurdugu her alan, dis tuketicinin bagimli olabilecegi bir seye doner ve icsel detaylari sonradan geri almak pahalilasir. ADR-0003 bolum 11.3'teki `translation: {circuit_open, cooldown_remaining_seconds}` alani da bu yuzden cikarildi — tuketici zaten kayit bazinda `needs_translation` goruyor.

5. **`trigger` icin cagri bicimi degisti.** `.delay()` Celery header'i kabul etmedigi icin `news/views.py`'deki alti dagitim satiri `.apply_async(kwargs={...}, headers={'fetchrun_trigger': 'admin'})` bicimine gecti; `news/api_v1/refresh.py` `api` isaretler; Beat varsayilan `beat` kalir. **ADR-0003'un "`news/views.py` degismez" maddesinden bilincli sapma:** hicbir HTTP sozlesmesi, yanit govdesi, URL veya gorev imzasi degismedi, yalnizca cagri bicimi.

6. **Admin.** `FetchRun` tamamen salt okunur kaydedilir (ekleme, degistirme **ve silme** kapali — denetim kaydinin elle silinebilmesi 2026-09-18 vakasinin tekrari olurdu). `DevToolsEntry` ve `AINewsEntry` ilk kez kaydedildi. Alti modelde `needs_translation` ve `translation_provider` filtrelendi; detay sayfasina salt okunur orijinal/Turkce yan yana karsilastirma, listeye 80 karakterlik baslik onizlemesi eklendi. Karsilastirma `format_html_join` ile uretilir: kazinmis ucuncu taraf metni arguman olarak gider ve kacislanir.

### Elenen alternatifler

| Alternatif | Neden elendi |
|---|---|
| Her task govdesinde acikca ac/kapat (ADR-0003 11.2'nin yolu) | Yedi task'ta tekrar eden `try/finally`; comen turu yakalamak dogru kurulmus `finally`'ye bagli kalir, sinyalde bedava gelir |
| Yalniz sinyaller, donus sozlesmesi degismeden | `fetched_count`, `translation_failures` ve `by_provider` donus govdesinde yok; sinyal onlara erisemez |
| Operator verisini de `/status/`'a koymak | Dis sozlesme sisər; icsel alanlar tuketicinin bagimli olabilecegi seylere doner |
| Ayri `/api/v1/diagnostics/` ucu | Iki uc, iki yetkilendirme kurali, iki test yuzeyi; admin zaten operator icin dogru yer |
| `deleted_count` alani | `total_after` ile ortusuyor; turlar arasi fark ayni bilgiyi veriyor |
| `status`'u task'in `success` bayragindan turetmek | SRE ve DevTools sagliklı olduklari halde surekli `failure` gorunurdu (bkz. Context) |

## Canli Dogrulama

Kuyruktan gecen ilk tur (2026-09-21):

```
bolum  durum    tetik   fetched  saved  total  sure
sre    success  admin        14      0     35  150sn
```

Uc seyi birden dogruluyor: kaynak 14 kayit dondurdu ama hicbiri yeni degildi ve satir **`success`** yazildi (karar 2); tetikleyici `admin` olarak kaydedildi (karar 5); `total_after` tur sonu satir sayisini tuttu (karar 1).

303 test gecti.

## Consequences

- **Positive:** Comen, asili kalan veya hata donduren bir tur log okumadan gorulebilir. "Kaynak bozuk" ile "yeni kayit yok" ayirt edilebilir hale geldi. Task disinda olan bir silme turlar arasi `total_after` farkindan anlasilir. Tuketici veri tazeligini tek uctan sorgulayabilir. Ceviri kalitesinin gidisati (`by_provider`) kayit altina alinir. Task govdeleri degismedigi icin cekim mantigi risk almadi.
- **Negative / kabul edilen sinirlar:**
  - **Sinyal baglanti testi kendi kendini dogruluyor.** `news/tests/test_fetchrun.py` icindeki testler `news.fetch_runs`'u kendileri import ediyor ve bu import `@task_prerun.connect` dekoratorlerini calistiriyor; dolayisiyla `news/apps.py`'deki `from . import fetch_runs` satiri silinse bile testler yesil kalir ve uretim sessizce hicbir sey kaydetmez. Uretim kablolamasi bagimsiz dogrulandi (canli worker surecinde `django.setup()` tek basina modulu yukluyor ve alicilar bagli), ama **testin verdigi garanti adinin vaat ettiginden zayiftir**. Dogru sekli: alt surecte `django.setup()` sonrasi `sys.modules` kontrolu.
  - `_acik_turlar` (task_id → satir eslemesi) surec ici tutulur. Worker alt sureci `prerun` ile `postrun` arasinda olurse satir `running` kalir — bu istenen davranistir (asili tur sinyali). Ancak `worker_max_tasks_per_child` ileride acilirsa surec geri donusumu yanlis "asili tur" uretir; o zaman esleme yerine `FetchRun`'a `task_id` alani eklenmelidir. Ayar su an tanimli degildir.
  - Saklama temizligi (`eski_kayitlari_temizle`) `try/except` + `print` ile sarilidir: kalici bir hata yalnizca worker logunda kalir. Gorunurluk katmaninin isin kendisini dusurmemesi ilkesi gerektirdigi icin boyle birakildi; hata kendini duyurur, cunku `FetchRun` tablosu 30 gunun otesine buyur ve bu admin'den gorulur.
  - `FetchRun.section` hem `db_index=True` hem bilesik `(section, -started_at)` index tasir; ikincisi birincisini kapsar. Kaldirmak yeni migration ister, ileriki bir sema degisikligine birakildi.
  - `/api/v1/status/` cagri basina bolum basina birkac sorgu calistirir (6 bolum). Bu olcekte sorun degil.
- **Acik isler:** A5 — drf-spectacular semasi, `/api/v1/docs/`, ornek istemci, README; `id` yerine `cve_id`/`link` uzerinden upsert kurali orada yazili hale gelir (ADR-0005 8.1). SRE/DevTools kaynaklarinin gercekten yeni icerik uretip uretmedigi, artik `FetchRun` verisiyle ayri bir is olarak incelenebilir. Alarm/bildirim: `FetchRun` veriyi uretir, esik asildiginda bildirim gondermek ayri bir karardir. Faz B — PostgreSQL ve Helm; `FetchRun` tablosu tasinacak veriye eklenir.
