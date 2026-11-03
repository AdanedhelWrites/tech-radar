# Çeviri Kapasitesi: Gemini'yi Tam ve Doğru Yaymak — Tasarım

> Tarih: 2026-11-02. Kaynak: brainstorming oturumu (UI turu sonrası). Durum: PR-A ve PR-B uygulandi (dallar feat/ceviri-yayma-a, feat/ceviri-yayma-b); PR-C bekliyor.
> Önceki tasarımlar: `2026-09-14-ceviri-saglayici-zinciri`, `2026-09-15-gemini-yukseltme-design.md`,
> `2026-09-17-cve-saklama-ve-gemini-onceligi` (ADR-0005, CVE rezervi). Bu tasarım ADR-0005'teki CVE rezervinin
> yerine önem sınıfına dayalı bir öncelik koyar.

## 1. Amaç ve neden

Kullanıcı arayüzde okuduğu metinlerin büyük kısmının LibreTranslate kalitesinde kaldığını görüyor ("Gemini
hepsine yetişemiyor"). Gündem'de "QwenGPU ile tanışın: … Bu Run CUDA", "Ajanic web burada" gibi bozuk başlıklar
çıkıyor. İstek: **Gemini'nin ücretsiz kotasını tam ve gün içine doğru yayarak kullanmak**, önemli kayıtları
öncelemek, önemsiz kayıtlara kota harcamamak. Bu bir hobi projesi: **aylık maliyet sıfır kalmalı**; yalnız
ücretsiz katmanlar (Gemini, OpenRouter ücretsiz modelleri, DeepL API Free) kullanılabilir.

### 1.1 Ölçüm (2026-11-02, canlı)

| Ölçü | Değer |
|---|---|
| Gemini günlük bütçe / bugün kullanılan | 400 / 241 (159 boşta) |
| Son 24 saatte gelen yeni kayıt | ~200 (CVE 166, haber 22, SRE 7, AI 5) |
| Son 7 gün CVE/gün | ~265; bunun ~130'u kritik+yüksek (CVSS ≥ 7), ~136'sı orta/düşük |
| Son 7 gün haber/gün, ortalama uzunluk | 50,6 kayıt, başlık+açıklama ~3.600 karakter |
| Son 7 gün AI/gün | 24,4 kayıt, ~2.750 karakter |
| CVE açıklama uzunluğu | ortalama ~780, p90 ~1.840 karakter |
| API'nin son 100 kaydında Libre oranı | Siber Güvenlik %100, Yapay Zeka %100, CVE %85, SRE %6, DevTools %2 |
| Tüm tabloda Libre kayıt | haber 407, AI 372, CVE 151 (91'i CVSS ≥ 7), diğerleri ≤ 10 |

### 1.2 Kök neden

Sorun kapasiteden çok **dağıtım ve sıra**:

1. **Kayıt başına bir istek.** Günde ~210 Gemini adayı var; 400'lük bütçe kâğıt üstünde yetiyor ama CVE
   tek başına günün ilk saatlerinde bütçenin yarısını geçiyor.
2. **CVE rezervi (`GEMINI_CVE_RESERVE=0.5`).** Paylaşılan sayaç 200'ü geçince CVE dışındaki bölümler o gün
   Gemini alamıyor. CVE turda ilk sırada olduğu için bu eşik her gün erken aşılıyor; haberler boş kalıyor.
3. **Yükseltme eskiden yeniye gidiyor.** `_yukselt` sorgusu `order_by('updated_at', 'id')`: kalan az bütçe,
   kullanıcının hiç bakmadığı eski Libre kayıtlara gidiyor; yeni haber sırasını hiç görmüyor.
4. **Orta/düşük CVE'ler de kota yiyor.** CVE'nin yarısı orta/düşük; kullanıcı bunları önemsemiyor.

## 2. Hedefler

### G1. Önem sınıfı: kim Gemini alır (kullanıcının kararı)

- **CVE:** yalnız **CVSS ≥ 7.0 ya da CISA KEV'de olan** kayıtlar Gemini adayıdır.
  - CVSS < 7.0 olanlar Gemini'ye **hiç** gitmez, ne bekleyen aşamada ne yükseltmede. LibreTranslate çevirisiyle kalır.
  - Skoru henüz olmayan (`cvss_score` boş) ve KEV'de olmayan CVE de aday değildir. NVD skoru sonradan
    ≥ 7 gelirse, kayıt sonraki yükseltme turunda kendiliğinden aday olur (sorgu güncel skora bakar).
- **Diğer bölümler** (haber, AI, SRE, DevTools, Kubernetes): bütün kayıtlar adaydır.
- Kullanıcının gerekçesi: "low ve medium olanlar çok önemsenmiyor, onlara token vermek mantıksız harcama olur."

### G2. Yeni kayıt önce

Yükseltme (Libre → Gemini) **en yeni kayıttan başlar** (`created_at` azalan). Kullanıcı yeni gelene bakar;
eski Libre birikimi bütçe kaldıkça geriye doğru erir. Bekleyen (`needs_translation=True`) aşaması bugünkü
imleç sırasını korur (bekleyen kayıt nadirdir, sıra etkisizdir).

### G3. Bölümler arası öncelik sırası (kullanıcının kararı: "öncelikli CVE'ler, ondan sonra devam et")

1. Gemini adayı CVE'ler (G1)
2. Siber Güvenlik haberleri
3. Yapay Zeka
4. SRE
5. DevTools
6. Kubernetes

`GEMINI_CVE_RESERVE` ve `butce_tavani(bolum)` rezerv mantığı kalkar. Yerine bu sıra ve G4'teki tur payı gelir.
Sıra yalnız bütçe dar olduğunda belirleyicidir; G5'teki toplu çeviriyle çoğu gün tüm adaylar çevrilir.

### G4. Gün içine yayma (kullanıcının kararı: "Gemini'yi full kullanalım, doğru şekilde yayarak")

- Günlük bütçe **450 istek**. Google'ın ücretsiz sınırı model başına 500/gün; arada 50 güvenlik payı kalır.
  Gün Pasifik gece yarısında başlar, mevcut `butce_anahtari` ile aynı.
- **Tur payı.** Bir tur en fazla `ceil(kalan_bütçe / günün_kalan_tur_sayısı)` istek harcar. Böylece sabah
  gelen yoğunluk bütçeyi öğlene kadar bitirmez; akşam gelen haber de pay alır.
- Tur payının içinde harcama G3 sırasıyla yapılır.
- Bir turun kullanmadığı pay sonraki turlara kalır. Payın tanımı bunu zaten sağlar, çünkü kalan bütçe her
  turda yeniden hesaplanır.
- **Retranslate sıklığı** 2 saatten **saatliğe** iner (benim kararım). Bir haber en geç ~1–2 saatte Gemini
  çevirisine kavuşur, tur başına pay da daha düzgün yayılır.
  - **Çekim saatleri atlanır.** Çekimler 00/06/12/18'de :00–:50 arasında koşuyor; CVE çekimi tek başına 751 sn'ye
    kadar sürmüş, worker eşzamanlılığı 2 ve 10-21'de böyle bir yığılma LibreTranslate'i boğmuştu. Bu yüzden tur
    bu dört saatte koşmaz: `hour` = 00/06/12/18 dışındaki saatler, :05, yani günde 20 tur.
  - "Günün kalan tur sayısı" bu takvimden hesaplanır.
  - Ayrıca `retranslate_pending_task`'a tekil çalışma kilidi (Redis) eklenir. Önceki tur bitmeden yenisi
    başlamaz, başlayan yeni tur sessizce çıkar.
- **Öncelik katıdır, taban yok** (benim kararım; kullanıcı "önce öncelikli CVE'ler" dedi).
  - PR-A'da hâlâ kayıt başına tek istek gider. İlk turlarda 91 kayıtlık CVSS ≥ 7 CVE birikimi tur payını önce
    yer; bu birikim birkaç turda erir.
  - Sonrasında yeni aday CVE saatte ~6 kayıt, tur payı ise ~20 istek. Kalan pay her turda haber ve AI'ya gider.
  - Haber ve AI birikimi (779 kayıt) PR-A'da birkaç güne yayılarak, PR-B'de 1–3 günde erir.

### G5. Toplu çeviri (bir istekte birden çok kayıt)

- Bir Gemini isteği, aynı bölümden birden çok kaydı tek JSON'da taşır.
- Paket sınırları ortam değişkeniyle ayarlanır:
  - toplam karakter sınırı `GEMINI_BATCH_CHARS` (varsayılan 10.000)
  - kayıt sayısı sınırı `GEMINI_BATCH_MAX` (varsayılan 15)
  - Varsayılanlar benim kararım. Mevcut `GEMINI_MAX_CHARS=12000` sınırı 60 sn zaman aşımından dolayı konmuştu; paket bunun altında kalır.
- **Bütçe istek başına** sayılır (Google kotası istek sayar), kayıt başına değil.
- **Kayıt başına doğrulama.** Mevcut `_alan_sorunu` kuralları her kaydın her alanına uygulanır.
  - Bir kayıt geçerse yazılır, geçemezse yalnız o kayıt başarısız sayılır (`translation_attempts` +1).
  - Paketteki diğer kayıtlar etkilenmez.
  - Bir kaydın alanları kendi içinde "hepsi ya da hiçbiri" kuralını korur.
- Yanıt yapısı kayıt kimliğiyle eşlenir: modelin kayıtları karıştırması ya da düşürmesi o kaydın başarısızlığıdır.
- **Deneme sayacı** (benim kararım):
  - `translation_attempts` yalnız **içerik hatasında** artar: doğrulama geçmedi, kayıt yanıtta yok ya da
    kimlik eşleşmedi.
  - 429, 5xx, ağ hatası ve zaman aşımı gibi istek düzeyindeki hatalar paketteki hiçbir kaydın sayacını artırmaz.
    Bunlar devre kesiciyi açar, kayıtlar sonraki turda yeniden denenir.
  - `MAX_TOKENS` ya da yanıtın yarım gelmesi bir paket boyu sorunudur. Paket ikiye bölünüp aynı turda yeniden
    denenir. Tek kayda inildiğinde de bitmiyorsa o kaydın içerik hatası sayılır.
  - Kısmi başarısızlıkta başarısız kayıtlar aynı turda yeniden denenmez.
- **Yükseltme aşaması da sayaca uyar.** Yükseltme sorgusu `translation_attempts < RETRANSLATE_MAX_ATTEMPTS`
  süzgecini alır; içerik hatası orada da `_basarisiz_say` ile sayılır. Böylece "en yeni N aday" sorgusu sürekli
  reddedilen bir kaydı her saat yeniden denemez.
- Vazgeçilen yükseltme adayları `/api/saglik/` yanıtında ayrı bir sayaçla görünür (`upgrade_given_up`).
  Bugünkü `translation_given_up` alanı bekleyenleri saymaya devam eder.
- Başarılı yükseltmede sayaç sıfırlanır (bugünkü `_yaz` kuralı).
- **Kubernetes'in yapılandırılmış changelog'ları** (`===SECTION:` içeren GitHub Releases) paketlenmez.
  Bugünkü gibi tek kayıtla gider ve işaret sayısı denetimi aynen kalır. Diğer K8s kayıtları paketlenebilir.
- **Beklenen kullanım:**
  - CVE (~130 × 780 kr): ~11 istek/gün
  - Haber (~50 × 3.600 kr): ~18 istek/gün
  - AI ve diğerleri: ~10 istek/gün
  - Toplam ~40–60 istek/gün; kalan pay birikimi 1–3 günde eritir.

### G6. Yedek sağlayıcı zinciri (router)

Kayıt düzeyindeki çeviri (bekleyen ve yükseltme aşamaları) sırayla şu sağlayıcıları dener:

1. **Gemini birincil model** (`GEMINI_MODEL`, bugünkü `gemini-3.5-flash-lite`)
2. **Gemini ikinci model** (`GEMINI_FALLBACK_MODEL`): Google kotası model başınadır, aynı anahtarla ek kapasite verir
3. **OpenRouter ücretsiz model** (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`: adı `:free` ile bitmek zorunda;
   ücretli model adı reddedilir ki yanlışlıkla ücret çıkmasın)
4. **DeepL API Free** (`DEEPL_API_KEY`, `api-free.deepl.com`; ayda 500.000 karakter, bizim tavanımız 450.000)
5. **LibreTranslate**: bekleyen aşamasında son çare, yükseltmede kullanılmaz

Kurallar:

- Her sağlayıcının **kendi sayacı** olur (Gemini modelleri ve OpenRouter günlük istek, DeepL aylık karakter).
  Her birinin kendi aralık kapısı ve devre kesicisi de olur.
  Bunlar mevcut `_RedisGate` / `_RedisButce` yapılarıyla kurulur.
- **Anahtarı boş olan sağlayıcı atlanır.** OpenRouter ya da DeepL anahtarı girilmeden de sistem bugünkü gibi çalışır.
- **G4 yayma payı** Gemini birincil için geçerlidir. Yedekler yalnız Gemini'nin iki modeli de **gerçekten**
  kullanılamazken devreye girer: günlük bütçe bitmiş ya da devre kesici açık. **Tur payının bitmesi "hazır
  değil" sayılmaz** (benim kararım). Pay bittiyse kayıt bir sonraki turu bekler, yedeğe gitmez. Aksi halde
  yedekler her saat Gemini'nin sonra alacağı kayıtları kalıcı olarak kapardı.
- Bekleyen aşamasında yedek zincir her zaman açıktır, çünkü kayıt boş kalmasın. Yükseltme aşamasında yedekler
  yalnız yukarıdaki gerçek kullanılamazlık durumunda çalışır.
- **G1 dışı CVE'ler** (CVSS < 7, skorsuz, KEV değil) yedek zincire de girmez: yalnız LibreTranslate
  (kullanıcının "token verme" kararı her ücretsiz sağlayıcı için geçerli).
- **Doğrulama** her sağlayıcıya aynen uygulanır: Türkçe harf, yankı, oran, yabancı alfabe ve K8s işaret sayısı.
  Bir sağlayıcının çıktısı doğrulamadan geçmezse zincirde sıradaki denenir.
- LLM sağlayıcıları (Gemini, OpenRouter) aynı sistem talimatını ve paket biçimini kullanır.
- **DeepL bir LLM değildir.** Ürün adı, CVE numarası ve kod gibi terimler, DeepL'in etiket koruma özelliğiyle
  ya da mevcut XTRM yer tutucularıyla korunur. Hangisi olacağı uygulayıcının kararı (bkz. §7).
- `translation_provider` alanına sağlayıcının adı yazılır: `gemini`, `openrouter` ya da `deepl`.
  Gemini'nin iki modeli tek ad `gemini` altında tutulur; model ayrımı loglarda ve sayaçlarda görünür.
- **Şema ve sözleşme.** Altı modeldeki `translation_provider` alanının `choices` listesine `openrouter` ve
  `deepl` eklenir; bu bir migration gerektirir.
  - Değerler mevcut `max_length=20` sınırına sığar.
  - Bu repodaki şema değişikliği sırası izlenir: önce migration canlıya uygulanır, sonra kod.
  - `/api/v1/` tüketicisi için değişiklik **eklemelidir**: alan zaten serbest bir metin; drf-spectacular şeması
    yeni değerleri listeler. ADR-0004'e (sağlayıcı zinciri) bir not düşülür.
  - Frontend rozet eşlemesi bilinmeyen sağlayıcıda bugün ne gösteriyorsa onu korur, yeni iki ad eklenir.
- **Yeniden yükseltme yok.** `openrouter` ya da `deepl` ile çevrilmiş bir kayıt sonradan Gemini'ye yükseltilmez
  (benim kararım; kota israfı ve kayıt çalkantısı olmasın). Yükseltme adayı yalnız `libretranslate` kayıtlardır.
- **Hesaplar kullanıcıda.** OpenRouter ve DeepL Free hesaplarını kullanıcı kendisi açar, anahtarları `.env`
  dosyasına kendisi girer. Anahtarlar repoya girmez. Helm tarafında mevcut `secrets.geminiApiKey` deseni izlenir.

### G7. Görünürlük

- `/api/saglik/` yanıtına `translation_budget` eklenir. Her sağlayıcı için şunlar bulunur:
  `used`, `limit`, `period` (`day` ya da `month`), `available` ve `cooldown`.
- Genel Bakış'ın alt durum şeridinde bugünkü "Çeviri kuyruğu" satırının yanına Gemini kullanımı eklenir
  (örnek: "Gemini 57/450"). Yedek sağlayıcı o gün kullanıldıysa o da gösterilir.
- Okuma panelindeki ve listelerdeki çeviri rozetine yeni sağlayıcı adları eklenir: "Çeviri: OpenRouter",
  "Çeviri: DeepL". Orta/düşük CVE'lerin "Makine çevirisi: LibreTranslate" rozeti aynen kalır.

## 3. Hedef olmayanlar

- **Çekim anındaki çeviri değişmez.** Yeni kayıt LibreTranslate ile anında çevrilir ve hemen görünür, sonra
  yükseltilir (kullanıcı "fikir harika" dedi; boş ya da İngilizce kayıt görünmez).
- Ücretli API, ücretli model, kredi kartıyla faturalanan katman yok.
- Terim koruma kuralları ve sistem talimatı içerik olarak değişmez; yalnız paket biçimine uyarlanır.
- Eski `google` etiketli kayıtlar yükseltilmez (bugünkü kural).
- Filtre/sıralama/sayfalama, Gündem puanlaması, CVSS grafiği, ham Markdown özetler ve kesik GitHub Advisory
  başlıkları bu işin parçası değil; ayrı projeler.

## 4. Karşı hedefler (çalışsa bile başarısızlık sayılır)

- Ücretsiz kotanın aşılması: 429 fırtınası ya da hesabın kısıtlanması. Bütçe sayacı istekten önce artar (bugünkü kural korunur).
- Orta/düşük CVE'ye Gemini, OpenRouter ya da DeepL harcanması.
- Paketteki bir bozuk kaydın aynı paketteki doğru kayıtları düşürmesi ya da başka kayda yanlış çeviri yazması.
- Çeviri kalitesinin gerilemesi:
  - ASCII'ye kaymış Türkçe
  - uydurma alfabe
  - bozulan K8s changelog yapısı
  - Markdown, kod ya da sürüm numarasının bozulması
- Herhangi bir anahtarın repoya, loga ya da API yanıtına sızması.
- Yedek sağlayıcı anahtarları yokken sistemin bugünkünden kötü çalışması.

## 5. Kısıtlar

- Yalnız yerel çalışma: Docker Desktop compose ve docker-desktop K8s. Bulut kurulumu, registry ya da sürüm etiketi yok.
- `main` korumalı: dal, PR ve 5 zorunlu kontrol. Merge kullanıcının açık onayıyla yapılır.
- **Ücretsiz katman sınırları kesin değil.** Gemini için model başına ~15 istek/dk ve ~500 istek/gün varsayılıyor.
  OpenRouter ücretsiz modellerinin günlük sınırı hesap durumuna göre değişiyor; DeepL Free aylık 500.000 karakter.
  Hepsi uygulama anında sağlayıcının güncel belgesinden doğrulanır ve ortam değişkeniyle ayarlanabilir kalır.
- Celery tur süresi: `RETRANSLATE_TIME_BUDGET`, yumuşak sınırdan 300 sn önce temiz bitiş. Paketleme tur süresini
  kısaltır; saatlik turlar birbirine binmemeli. Bugünkü tekil görev kilidi ya da süre bütçesi bunu korur;
  uygulayıcı doğrular.
- Mevcut testler (Django testleri, Vitest) yeşil kalır; yeni davranışlar teste bağlanır.
- Kod ve yorumlar mevcut üslupta yazılır (ASCII Türkçe adlar). Modele giden talimat düzgün Türkçe karakterlerle kalır.

## 6. Teslim sırası (her biri ayrı PR)

1. **PR-A, sıra ve yayma.** G1 (önem sınıfı), G2 (yeniden eskiye), G3 (öncelik, CVE rezervi kalkar),
   G4 (450 bütçe, tur payı, saatlik tur) ve G7'nin Gemini kullanımı kısmı. Hâlâ kayıt başına tek istek.
   Yeni haberin açlığını bitirir; eski birikim birkaç güne yayılarak erir.
2. **PR-B, toplu çeviri.** G5.
3. **PR-C, yedek zincir.** G6 ve G7'nin yedek sağlayıcı kısmı.
   Anahtarlar olmadan da merge edilebilir; kullanıcı anahtarları sonra ekler.

**Başarı ölçütü** (PR-A ve PR-B canlıda 24 saat çalıştıktan sonra ölçülür):

- Siber Güvenlik ve Yapay Zeka'da API'nin son 100 kaydının en az %95'i `gemini`.
- CVSS ≥ 7 ya da KEV olan son 100 CVE'nin en az %95'i `gemini`.
- CVSS < 7 CVE'lerde o günden sonra yeni `gemini` sıfır.
- Gemini kullanımı ≤ 450/gün; kota kaynaklı (429) devre kesici açılmıyor.
- Haber ve AI'daki Libre birikimi (407 + 372) en geç 3 günde 50'nin altına iniyor.

## 7. Uygulayıcıya kalanlar

- Toplu istek ve yanıt JSON şemasının biçimi (kimlik anahtarlı nesne ya da dizi). Koşul: her çeviri kendi
  kaydına kimlikle eşlenmeli.
- İmleç mekanizmasının yeniden eskiye sırada nasıl çalışacağı. Mevcut `apply_cursor` sıra yönüne uyarlanabilir
  ya da imleç yerine "en yeni N aday" sorgusu kullanılabilir. Koşul: aynı kayıt bir turda iki kez denenmez ve
  sürekli reddedilen kayıt `RETRANSLATE_MAX_ATTEMPTS` kuralıyla kuyruktan düşer.
- Tur payı hesabında günün kalan tur sayısının nasıl bulunacağı (Beat takviminden ya da sabit saatlik varsayımla).
- `GEMINI_FALLBACK_MODEL` için hangi Gemini modelinin seçileceği. Ücretsiz katmanda olan ve Türkçe kalitesi
  denenmiş bir model olmalı. Uygulama anında ölçülür; boş bırakılırsa bu adım atlanır.
- OpenRouter'da varsayılan ücretsiz model. Uygulama anında birkaç ücretsiz model gerçek CVE ve haber metniyle
  denenir. Doğrulamadan en çok geçen model seçilir ve neden seçildiği PR'da yazılır.
- DeepL'de terim korumanın yolu: etiket koruma ya da XTRM yer tutucusu.
- `/api/saglik/` alan adlarının ayrıntısı ve şeritteki metnin tam biçimi.
- Helm `values.yaml` ve ConfigMap'e yeni ayarların eklenmesi, mevcut `gemini*` desenine uygun olarak.

## 8. Benim verdiğim kararlar (kullanıcı onayında kontrol etsin)

- Günlük bütçe 450 (500 sınırına 50 pay).
- Retranslate turu saatliğe çıkıyor; çekim saatleri (00/06/12/18) atlanıyor, günde 20 tur. Ayrıca tekil çalışma kilidi.
- Öncelik katı, bölüm başına taban pay yok.
- Tur payının bitmesi yedek sağlayıcıları tetiklemiyor; yalnız Gemini'nin gerçekten kullanılamaması tetikliyor.
- Deneme sayacı yalnız içerik hatasında artıyor; `MAX_TOKENS` paketi ikiye bölüyor.
- Skorsuz ve KEV dışı CVE Gemini adayı değil; skor gelince aday olur.
- Paket varsayılanları: 10.000 karakter ve 15 kayıt.
- K8s yapılandırılmış changelog'ları paketlenmiyor.
- OpenRouter ve DeepL çevirileri sonradan Gemini'ye yükseltilmiyor.
- OpenRouter model adı `:free` ile bitmezse reddediliyor (ücret çıkmasın diye).
