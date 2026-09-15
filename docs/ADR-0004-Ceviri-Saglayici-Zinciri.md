# ADR 0004: Ceviri Saglayici Zinciri (Google once, LibreTranslate yedek)

## Status
Accepted — 2026-09-14 (uygulandi; PR #27 `1d70f46`, migration `0009_translation_provider`, canlida dogrulandi). Degisiklik 2026-09-15: Google kaldirildi, Gemini yukseltme (bkz. asagida).

Tasarim: [`superpowers/specs/2026-09-14-ceviri-saglayici-zinciri-design.md`](superpowers/specs/2026-09-14-ceviri-saglayici-zinciri-design.md). Plan: `superpowers/plans/2026-09-14-ceviri-saglayici-zinciri.md` (spec ile celiskide planin "Spec'e Gore Netlestirmeler" bolumu gecerlidir). Ceviri dogrulamasi ve `retranslate_pending` icin bkz. [ADR-0003](ADR-0003-Entegrasyon-API-v1.md) karar 9.

## Context
Haberlerin Turkce gelmesi bu projenin temel vaadidir ve tek saglayici ucretsiz Google Translate ucuydu (`deep-translator`). 2026-09-12 ile 2026-09-14 arasinda bu uc fiilen kapandi: "too many requests", devre kesici 31 kez acildi, son iki gunde gelen 283 kaydin yalnizca 2'si cevrildi, bekleyen kayit 384 → 622 (1035 kaydin %60'i). A3'teki `retranslate_pending` dogru calisiyordu ama Google kapaliyken yapacak bir seyi yoktu.

2026-09-14'te `libretranslate/libretranslate:v1.9.6` (yalnizca `en`/`tr` modelleri) atilacak bir konteynerde denendi:

- **Kaynak/hiz:** bosta 237 MB, 8 paralel istekte en fazla 1.14 GB; tek istemci ~753 karakter/sn, 8 paralel ~3900 karakter/sn. 1M karakterlik birikim ~5–22 dk. Modeller imajda degil, ilk acilista iner (258 MB).
- **Yer tutucu kaybi:** `XTRM` kodlari bolmeden 60 metnin 10'unda kayip; metin <= 160 karakterlik parcalara bolununce 4'e dustu. Alt cizgili tanimlayicilar (`parse_array`) siliniyordu; korumaya alininca 0/3 → 3/3.
- **Kalite:** Google'dan belirgin dusuk ve hatalar **mekanik degil** — A3 dogrulamasi (yanki/kirpilma/yer tutucu) bunlari yakalayamaz. Ozel adlar uyduruluyor; guvenlik anlami bozuluyor ("unauthenticated attackers" → "terk edilmis saldirganlar", "executed remotely" → "uzaktan idam edilebilir"). Kisa ve basit metinler kabul edilebilir.

Bu kalite bulgusu ilk fikri ("LibreTranslate ana, Google yedek") degistirdi.

## Decision

1. **`translation_utils.translate_text` icinde sirali saglayici zinciri: Google → LibreTranslate → orijinal metin.** Her saglayici ayni arayuzu uygular (`name`, `available()`, `translate(protected) -> Optional[str]`); `news/translation_providers.py::SAGLAYICILAR` sirayi belirler. Her denemede A3 dogrulamasi calisir; dogrulanamayan sonuc bir sonraki saglayiciya duser. Bir saglayicinin beklenmeyen istisnasi zinciri kesmez. Hicbiri basarili olmazsa A3 sozlesmesi korunur: orijinal doner, basarisizlik sayaci artar, kayit `needs_translation=True` kalir.

2. **Google mantigi yerinde kalir;** `GoogleProvider` cagri aninda `translation_utils`'e basvuran ince bir sarmalayicidir. Tasinsaydi ~30 testin mock noktalari sessizce bosa duserdi.

3. **`LibreTranslateProvider`:** `LIBRETRANSLATE_URL` bossa hic denenmez (LibreTranslate'siz kurulum ve testler bugunku gibi calisir). Metin en fazla `LIBRETRANSLATE_CHUNK_CHARS` (160) karakterlik parcalara bolunur (satir → cumle → virgul/bosluk; bosluksuz metinde kesim `XTRM` kodunu bolmez) ve tek `POST /translate` isteginde liste olarak gider; satir yapisi birlestirmede korunur. Zaman asimi `LIBRETRANSLATE_TIMEOUT` (60 sn). Baglanti hatasi/zaman asimi/5xx `None` dondurur ve kendi Redis devre kesicisini `LIBRETRANSLATE_COOLDOWN` (60 sn) acar; **4xx devre kesiciyi acmaz** (istek sorunu, servis ayakta). Yeniden deneme ve hiz siniri yoktur; eszamanlilik compose CPU siniriyla dogal olarak sinirlanir.

4. **Kayit duzeyinde `translation_provider` alani** (alti modelde `CharField`, `''` / `'google'` / `'libretranslate'`). En dusuk kaliteli parca belirleyicidir: herhangi bir parca LibreTranslate ile cevrildiyse kayit `libretranslate`. Task'lar ve retranslate bunu `consume_translation_providers()` ile hesaplar. Migration `0009` iki adimlidir: alan ekleme + veri migration'i (`needs_translation=False` kayitlar `QuerySet.update()` ile sessizce `google` — `updated_at` ilerlemez, tuketicinin delta akisina 1035 kayit birden dusmez).

5. **`retranslate_pending` iki asamali olur.**
   - *Asama 1 — bekleyenler:* tam zincirle; bolum basina `RETRANSLATE_BATCH` 8 → **100**. Durma kosulu artik Google devre kesicisi degil, **hicbir saglayicinin `available()` olmamasi**.
   - *Asama 2 — yukseltme:* yalnizca Google acikken, `translation_provider='libretranslate'` kayitlar `yalnizca_saglayicilar('google')` baglaminda yeniden cevrilir; bolum basina `RETRANSLATE_UPGRADE_BATCH` (**5**, ucretsiz kotayi korumak icin). Kural **hepsi-ya-da-hicbiri:** kaydin tum parcalari Google ile cevrilebildiyse yazilir (`google`, `updated_at` ilerler → tuketici daha iyi ceviriyi delta'dan alir); tek parca bile basarisizsa kayda hic yazilmaz. Kendi imleci vardir. Beat takvimi degismez.

6. **Gorunurluk:** v1 API kayitlarinda `translation_provider` alani (`null` / `google` / `libretranslate`), frontend cache surumu 3, arayuzde LibreTranslate cevirilerinde ortak `MakineCevirisiEtiketi` bileseniyle "Makine çevirisi" rozeti.

7. **Dagitim:** compose'a `teknoloji-translate` servisi (`cpus: 4`, `mem_limit: 2g`, isimli volume ile modeller bir kez iner, healthcheck). `LIBRETRANSLATE_URL` yalnizca api ve worker'a verilir; scheduler ceviri yapmaz. Migration `NOT NULL` sutun ekledigi icin worker/scheduler migration **oncesi** durdurulur; ortam degiskeni degistigi icin `restart` degil `up -d --force-recreate` kullanilir.

8. **Test izolasyonu:** proje test calistiricisi (`news/test_runner.py::GuvenliTestRunner`) testlerde `LIBRETRANSLATE_URL`'i bosaltir ve devre kesicileri surec ici tutar. Dagitimdan sonra API konteynerinde URL tanimli olacagi icin bu olmadan mevcut testler sahte Google basarisiz olunca gercek LibreTranslate'e ve canli devre kesicisine dokunurdu.

### Elenen alternatifler

| Alternatif | Neden elendi |
|---|---|
| LibreTranslate ana, Google yedek | Kalite bulgusu (anlam hatalari dogrulamayla yakalanamiyor) |
| Ayri ceviri servisi ve kuyrugu | Yeni hareketli parca; Celery gorevleri zaten kuyruk |
| Okuma aninda ceviri | API gecikmesi artar; v1'in "kayit degisince `updated_at` ilerler" sozlesmesi bozulur |
| HTML `translate="no"` / `<code>` ile terim koruma | Terimler korunuyor ama cumle parcalaniyor, kelime tekrari |
| Ucretli ceviri API'leri, Opus-MT | Kapsam disi; Opus-MT ayni arayuzle ucuncu saglayici olarak eklenebilir |
| Yukseltmede kismi yazma | Bir kayitta iki kalite seviyesi karisir; hepsi-ya-da-hicbiri secildi (kullanici karari) |

## Degisiklik (2026-09-15) — Google kaldirildi, Gemini yukseltme

Google Translate'in resmi olmayan uclari bu IP'den TLS parmak izi ve hacimle bloklandi (`/sorry/` CAPTCHA); `curl_cffi` ile acilan kapi hacimde yeniden kapandi. Kalici cozum: cekim aninda yalniz LibreTranslate; `retranslate` bekleyen ve LibreTranslate kayitlarini **Gemini API** (`gemini-3.5-flash-lite`, ucretsiz katman 500 RPD / 15 RPM) ile kayit basina tek istekle yukseltir; gunluk 400 istek butcesi + 5 sn aralik + devre kesici. `GoogleProvider`, `_translate_via_google`, `curl_cffi` silindi; `google` kayitlari etiketli kalir, yukseltilmez. Her kayit saglayici rozeti tasir. Tasarim: `superpowers/specs/2026-09-15-gemini-yukseltme-design.md`. Bu ADR'nin 3.1, 5 ve 7 numarali kararlari buna gore guncellenmistir; yerel LibreTranslate yedek olarak kalir.

## Consequences

- **Positive:** Google kapaliyken haberler yerel servisle aninda Turkceye cevrilir; retranslate durmaz. Canli dogrulamada (2026-09-14) ilk calismada 204/642 bekleyen kayit LibreTranslate ile cevrildi. Kullanici dusuk kaliteli ceviriyi rozetten ayirt eder; Google acilinca kayitlar kendiliginden yukselir. Alt cizgili tanimlayici korumasi Google cevirilerini de iyilestirdi. Dis bagimlilik yok; imaj 600 MB, bellek < 1.2 GB.
- **Negative / kabul edilen sinirlar:**
  - LibreTranslate cevirilerinde ozel ad ve guvenlik terimi hatalari olabilir; otomatik dogrulama yakalamaz. Rozet ve yukseltme bunun icindir, admin'de elle duzeltme yolu acik kalir.
  - Aciklamasi 30 karakterden kisa oldugu icin hic cevrilmemis CVE'ler veri migration'inda `google` gorunur; cevrilecek metin olmadigi icin zararsizdir.
  - Yukseltme bolum basina 5 kayit/tur oldugu icin buyuk bir LibreTranslate birikimi Google acilsa bile gunler icinde erir.
  - `turkish_post_process` cumle basini buyuttugu icin `kubectl` → `Kubectl` (A3'ten kalan, dokunulmadi).
- **Acik isler:** A4'te `FetchRun`'a `translation_failures` yaninda `by_provider` dagilimi; Faz B'de Helm'e LibreTranslate Deployment/Service/PVC + `LIBRETRANSLATE_URL`; A5'te README'ye `LIBRETRANSLATE_URL/TIMEOUT/COOLDOWN/CHUNK_CHARS`.
