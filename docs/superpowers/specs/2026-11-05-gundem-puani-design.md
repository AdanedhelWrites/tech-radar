# Gündem: Büyük Olayları Çok Kaynak Ölçüsüyle Öne Çıkarmak — Tasarım

> Tarih: 2026-11-05. Kaynak: brainstorming oturumu (UI isteklerinin üçüncüsü). Durum: taslak, onay bekliyor.

## 1. Amaç ve neden

Kullanıcının isteği: "Gündem kısmında sansasyonel olarak etkileyici haberleri konu alalım… Örneğin
'Binance hacklendi' gibi bir haber gündemde yer kaplasın. Bunu matematiksel olarak, çok fazla yerde en üst
düzeyde okunan haberse koyabiliriz."

**Bugün:** Ana sayfadaki Gündem kartı beş bölümün (Siber Güvenlik, Kubernetes, SRE, DevTools, Yapay Zeka)
en yeni 6 kaydını gösteriyor (`frontend/src/utils/gundem.js` `gundemBirlestir`, `created_at` sırası).
Büyüklük ölçüsü yok. Kart çoğunlukla sıradan Yapay Zeka ve SRE yazılarıyla doluyor; aynı anda büyük bir
güvenlik olayı Gündem'e girmiyor.

**Kullanıcının örnekleri ve verideki karşılıkları** (canlı veritabanı, 2026-11-05):

| Olay | Tarih | Kapsam |
|---|---|---|
| Binance 6,3 milyar dolarlık hack | 30 Ekim | İlk 8 saatte 5 farklı kaynak (The Hacker News, Bleeping Computer, SecurityWeek, Help Net Security, Infosecurity). 3 gün içinde 12 makale; 1–2 Kasım'da FBI / Kuzey Kore haberleriyle devam |
| PHP2Shell (iki kritik PHP RCE açığı, acil yama) | 21 Ekim | Tek günde 7 farklı kaynakta 11 makale |
| "Argon 4" (Gemini 4 Argon model çıkışı) | 1 Ekim | Aynı gün 4 kaynak: Google DeepMind, MarkTechPost, TechCrunch AI (Yapay Zeka bölümü) ve The Hacker News (Siber Güvenlik bölümü) |

**Ölçü:** Okunma sayısı bilinmiyor. Onun yerine **aynı olayı yazan farklı kaynak sayısı** kullanılır.
Bu ölçüyü kullanıcı onayladı. Örnek olayların hepsi bu ölçüde sıradan haberlerden açıkça ayrışıyor;
sıradan haberi çoğunlukla tek bir kaynak yazıyor.

**Başarı ölçütü:** Yukarıdaki üç olay, olduğu günlerde Gündem'in ilk sıralarında görünür. Aynı olayın altı
ayrı makalesi değil, tek satır ve "6 kaynak" rozeti görünür.

## 2. Hedefler

### G1. Kapsam (kullanıcının kararı)

- Gündem beş bölümün hepsinden beslenir: Siber Güvenlik, Kubernetes, SRE, DevTools, Yapay Zeka.
- Büyük her şey girer: hack ve sızıntılar, kritik açık ve acil yamalar, büyük ürün ya da model çıkışları,
  geniş kesintiler.
- **Zafiyetler (CVE) bölümü Gündem'e girmez.** Bugün de girmiyor; ana sayfada ayrı bir Öncelikli
  Zafiyetler listesi var. CVE kayıtlarının hepsi tek kaynaklı ve günde yaklaşık 250 kayıt geliyor.
- Büyük açıklar (PHP2Shell gibi) zaten haber olarak Siber Güvenlik bölümünden girer.

### G2. Olay gruplama

- Son **72 saatte** radara giren (`created_at`) beş bölüm kayıtları olaylara gruplanır. Gruplama bölümler
  arasında da yapılır; Gemini 4 Argon örneğinde Yapay Zeka ve Siber Güvenlik kayıtları aynı olaydır.
- **Gruplama ölçütü:**
  - İngilizce **orijinal** başlık kullanılır. Çeviriler farklı sağlayıcılardan gelebilir ve tutarsızdır.
  - **Ortak ayırt edici özel ad** sayılır: Binance, PHP2Shell, TraderTraitor, Gemini 4 Argon gibi pencerede
    nadir geçen büyük harfli ya da harf-rakam karışık sözcükler.
  - Bunun yanında **başlık sözcük benzerliği** kullanılır: durak sözcükleri atılmış Jaccard ya da eşdeğeri.
  - İki kayıt tek başına yüksek benzerlikle ya da ortak nadir özel ad ile birlikte orta benzerlikle aynı
    olay sayılır. Gruplama geçişlidir (union-find).
- **Ayrım ölçütü:** sık geçen genel adlar tek başına gruplamaz. Örneğin aynı gün "Microsoft" ya da "Google"
  geçen ilgisiz iki haber birleşmemeli.
- Kesin eşikler ve sözcük kümeleri uygulayıcının kararıdır (§6). Ancak §5'teki gerçek veri örneklerini
  doğru gruplamak zorunludur.

### G3. Puan (benim önerim, kullanıcı "tam aklımdaki şey" dedi)

Her olay için:

```
puan = (farkli_kaynak + 0,5 × (makale_sayisi − farkli_kaynak) + etki) × 0,5 ^ (yas_saat / 24)
```

- `farkli_kaynak`: olaydaki farklı `source` sayısı. Asıl ölçü budur.
- `makale_sayisi − farkli_kaynak`: aynı kaynağın aynı olayı yeniden yazması. Az ağırlıklı.
- `etki`: başlıklardan birinde etki sözcüğü varsa 1,5, yoksa 0. Örnek sözcükler: hack, hacked, heist,
  breach, stolen, ransomware, zero-day, 0-day, exploited, emergency, critical, outage, billion, record.
  Liste uygulayıcıda.
- `yas_saat`: olaydaki **en yeni** makaleden bu yana geçen saat. Yarılanma süresi 24 saat.
  - **Benim kararım:** süren haberler olayı canlı tutar. Kullanıcının sorusu ("2 Kasım'da Binance hâlâ
    tepede mi?") yanıtsız kaldı. Binance'in 2 Kasım'da 4 yeni makalesi vardı, bu yüzden 2 Kasım'da da
    üst sıralarda kalır.
  - Haber kesilince bir günde yarıya düşer.
- Katsayılar uygulayıcının ayarına açıktır. Ancak §5'teki sıralama örnekleri sağlanmalıdır.

### G4. Seçim ve gösterim

- Gündem **6 öğe** gösterir (bugünkü `GUNDEM_ADEDI`).
- **Önce çok kaynaklı olaylar:** en az 2 farklı kaynağı olan olaylar puan sırasıyla gelir.
- **Boşluk doldurma:** çok kaynaklı olay 6'dan azsa kalan yerler tek kaynaklı en yeni kayıtlarla dolar.
  Bugünkü davranış budur; büyük olay yokken kart boş kalmaz (benim kararım). Bunlarda rozet yoktur.
- **Olay satırı:**
  - Başlık: temsilci kaydın Türkçe başlığı, yoksa orijinali.
  - Bölüm noktası ve bölüm adı.
  - **"N kaynak" rozeti** (yalnız N ≥ 2). Rozetin ipucunda kaynak adları listelenir.
  - Göreli zaman: olayın en yeni makalesi.
- **Temsilci kayıt:** olaydaki en iyi çevrilmiş kayıt (Gemini > Google > LibreTranslate > çevrilmemiş).
  Eşitlikte en erken giren kayıt, yani haberi ilk veren (benim kararım).
- **Tıklama:** temsilci kayıt bugünkü gibi okuma panelinde açılır. Olayın diğer makalelerinin listesi bu
  sürümde yoktur (bkz. §3).

### G5. Sunucu tarafı

- Yeni anonim uç: `GET /api/gundem/` (`AllowAny`).
- **Yanıt:** `{success, olaylar: [...], hesaplandi}`. Her olay:
  - `bolum`, `kayit`: temsilci; bölümün mevcut serileştiricisiyle.
  - `kaynak_sayisi`, `kaynaklar: [ad]`, `makale_sayisi`, `bolumler: [bolum]`
  - `puan`, `ilk`, `son`: ISO zaman.
- **Önbellek:** 120 saniye, anahtar `gundem_ozeti` (`/api/saglik/` ve `/api/ozet/` desenine uygun).
- **Hesap yeri:** sunucu. Bölümler arası gruplama beş tablonun 72 saatlik kaydını birlikte ister; tarayıcıya
  yüzlerce kayıt taşınmaz. Hacim günde yaklaşık 90 kayıt, 72 saatte yaklaşık 270; ikili karşılaştırma bile
  ucuzdur.
- **Frontend:**
  - `GenelBakis.jsx`, Gündem için beş liste ucu yerine `/api/gundem/` çağırır.
  - `utils/gundem.js` `gundemBirlestir` kalkar ya da yalnız eski yanıt için kalır; uygulayıcının kararı.
  - Ana sayfanın "son ziyaret" hesabı Gündem kayıtlarından en yeni zamanı almaya devam eder; artık
    `son` alanından okur.

## 3. Hedef olmayanlar

- Gerçek okunma, tıklanma ya da sosyal medya verisi yok; dış kaynağa istek yok.
- Olay sayfası ya da "bu olayın tüm haberleri" listesi yok. Sonraki iş olabilir.
- Gruplama için LLM ya da Gemini kullanılmaz: kota harcanmaz, sonuç tekrarlanabilir.
- Bölüm listelerinde (PR #106) olay gruplaması ya da önem sıralaması yok. Haberlerde "önem" sıralaması
  sonraki iş.
- CVE bölümü Gündem'e girmez (G1).

## 4. Karşı hedefler (çalışsa bile başarısızlık sayılır)

- **Yanlış birleştirme:** iki ilgisiz haberin aynı olay sayılması, örneğin "Microsoft"un geçtiği iki
  bağımsız haber. Bu, ayrı kalmasından daha kötüdür; şüphede ayrı tutulur.
- **Aynı olayın Gündem'de iki ayrı satırda görünmesi.** Örneğin Binance'in ilk günkü haberleri ile FBI
  haberleri. İkisi de "Binance" adını taşıyorsa birleşmeli.
- **Tek kaynaklı sıradan bir blog yazısının** çok kaynaklı büyük bir olayın önüne geçmesi.
- **Ana sayfanın yavaşlaması ya da Gündem hesabı hata verince ana sayfanın bozulması.** Gündem hatası
  yalnız kartta "Gündem bilgisi alınamadı." gösterir; bugünkü davranış budur.
- **Puanın ya da grupların her yenilemede zıplaması.** Aynı veriyle aynı sonuç çıkmalı (deterministik).

## 5. Kabul örnekleri (gerçek veriyle)

Uygulayıcı canlı veritabanından ilgili günlerin beş bölüm başlıklarını (yalnız
`id, bolum, source, original_title, created_at`) bir test fikstürüne aktarır. Kişisel veri yok, yalnız
haber başlıkları. Testler `simdi` verilerek şunları sağlar:

| `simdi` | Beklenen |
|---|---|
| 2026-10-30 20:00 (İstanbul) | 1. sıra Binance olayı; en az 5 farklı kaynak; tek satır |
| 2026-11-02 12:00 | Binance olayı hâlâ ilk 3'te. FBI / Kuzey Kore haberleri aynı olayda; ayrı satır yok |
| 2026-10-21 20:00 | 1. sıra PHP2Shell; en az 6 farklı kaynak |
| 2026-10-01 20:00 | Gemini 4 Argon olayı ilk 3'te; Yapay Zeka ve Siber Güvenlik kayıtları aynı olayda |
| Herhangi bir gün | "Microsoft" ya da "Google" geçen, olayca ilgisiz iki başlık ayrı kalır; fikstürden en az bir somut çift seçilir |
| Çok kaynaklı olay yokken | 6 öğe en yeni tek kaynaklı kayıtlarla dolar |

## 6. Uygulayıcıya kalanlar

- Başlık normalleştirme, durak sözcükleri, özel ad çıkarımı, benzerlik ölçüsü ve eşikler. §5 örnekleri
  sağlanmalı.
- Etki sözcükleri listesi ve G3 katsayılarının ince ayarı. §5 sıralamaları korunmalı.
- Kodun yeri; öneri: `news/gundem.py` (saf fonksiyonlar, test edilebilir) ve `views.get_gundem`.
- Fikstürün biçimi ve konumu (`news/tests/fixtures/…`).
- Frontend rozetinin görünümü (mevcut `rozet` stilleri) ve ipucu metni.

## 7. Uygulayıcı kontrolünden sonra netleşenler

- **`created_at` güvenilir mi?** 2026-11-05'te ölçüldü: günlük dağılım düzgün, toplu damga yok. Yeniden
  çekim `update_or_create` ile `created_at`'i değiştirmez.
  - Ek koruma (benim kararım): kayıt, `created_at` 72 saat içinde **ve** yayın tarihi (`published_date`;
    haberde `date`) son 4 takvim günü içindeyse pencereye girer.
  - Yayın tarihi boşsa yalnız `created_at` yeter.
  - Böylece yeni eklenen bir kaynağın eski yazıları "yeni büyük olay" gibi görünmez.
- **Fikstür:** uygulayıcı canlı veritabanından **yalnız okuyarak** aktarır. Çalışan `teknoloji-api`
  konteynerinde `manage.py shell` ile yalnız `id, bolum, source, original_title, created_at` ve yayın tarihi
  alınır; yazma yok. Fikstürdeki `created_at` değerleri gerçek giriş zamanlarıdır (yukarıdaki ölçüm).
- **"Farklı kaynak":** `source` dizesi büyük/küçük harf ve boşluk normalleştirilerek karşılaştırılır.
  - Canlıdaki adlar temiz ve bölümler arasında çakışmıyor; örneğin haberde "The Hacker News", Yapay
    Zeka'da "TechCrunch AI".
  - Beş modelin hepsinde `source` alanı var. Kubernetes için `GitHub Releases`, `K8s Blog`, `CNCF Blog`;
    DevTools için ürün adı (Redis, PostgreSQL…).
- **Birleştirme mi bölme mi:** gruplama geçişlidir (union-find). Uzun süren bir olayın başlıkları ortak
  nadir adı taşıdıkça tek olay kalır.
  - Binance'in FBI ve Kuzey Kore haberlerinin hepsinde "Binance" geçiyor (veriyle kontrol edildi).
  - Ortak ad hiç taşımayan başlıklar ayrı olay kalabilir; bu kabul edilir. Şüphede ayrı tut kuralı geçerli.
- **Sürüm akışları:** aynı satıcının ardışık sürüm notları tek kaynaktır (`farkli_kaynak = 1`), bu yüzden
  çok kaynaklı sayılmaz; ayrıca bir dışlama gerekmez. Bir sürümü birden çok kaynak birlikte yazarsa
  (örneğin K8s Blog, CNCF ve bir haber sitesi), bu gerçek bir büyük olaydır ve Gündem'e girer.
- **Temsilci kayıt sırası:**
  - `translation_provider`: gemini > openrouter = deepl > google > libretranslate > boş.
  - `turkish_title` boşsa kayıt çevrilmemiş sayılır ve en sona düşer.
- **Yanıt sözleşmesi:**
  - `kayit`, bölümün mevcut serileştiricisiyle aynen döner, böylece `haberOkumaKaydi(kayit, bolum)` değişmeden
    çalışır.
  - Ana sayfanın "son ziyaret" hesabı Gündem'den olayların `son` zamanını alır.

## 8. Benim verdiğim kararlar (kullanıcı onayında kontrol etsin)

- Zaman penceresi 72 saat; yarılanma süresi 24 saat; tazelik olayın en yeni makalesine göre ölçülür
  (süren haber olayı canlı tutar).
- CVE bölümü Gündem dışında kalır.
- Çok kaynaklı olay yoksa boşluk en yeni haberlerle dolar.
- Temsilci kayıt: en iyi çevrilmiş olan, eşitlikte haberi ilk veren.
- Gruplama yalnız kurallarla yapılır (LLM yok).
