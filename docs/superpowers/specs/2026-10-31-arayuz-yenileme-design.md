# Arayüz Yenileme: Zafiyet Odaklı Genel Bakış ve Okuma Paneli — Tasarım

> Tarih: 2026-10-31. Kaynak: brainstorming oturumu (görsel taslaklar `CyberNews/.superpowers/brainstorm/192-1793462254/content/`:
> `c-profesyonel-v2.html` ana sayfa, `okuma-gorunumu.html` okuma paneli; repo dışı). Durum: uygulandı (2026-10-31, dal feat/arayuz-yenileme).

## 1. Amaç ve neden

Kullanıcı uygulamayı açınca **önce CVE'lere**, özellikle **kritik zafiyetlere** bakıyor. Zamanı kalırsa diğer
haberlere göz gezdiriyor. Kullanıcının istediği, "kullanışlı ve gösterişli" bir arayüz ve **bakarken içini
rahatlatması**. Rahatlık hissini, sayfa açılır açılmaz durumu tek bakışta özetleyen bir cümle vermeli:
"kaç kritik var, son baktığımdan beri ne değişti".

İkinci ihtiyaç **okuma**: kullanıcı detayda çeviri metnini okuyor, satırların düzgün kırılıp kırılmadığına
ve okumanın akıp akmadığına bakıyor. Bugün açıklama metni dar bir yan kartta **iki yana yaslı**
(`textAlign: 'justify'`) gösteriliyor. Bu kelime aralarını açıyor ve okurken takılmaya yol açıyor.
Çevrilmemiş metinler de onu rahatsız ediyor.

**Başarı ölçütü:** (1) Ana sayfa açıldığında kritik zafiyet durumu ilk ekranda tek cümle ve dört sayı olarak
okunuyor. (2) Altı bölümün hepsinde detay aynı okuma panelinde açılıyor; metin sola hizalı, rahat satır
uzunluğunda ve akıcı. (3) Çevrilmemiş kayıt hiçbir zaman boş görünmüyor; orijinal metin uyarıyla
gösteriliyor. (4) Mevcut işlevlerin hiçbiri kaybolmuyor (bkz. §4).

## 2. Hedefler

- **G1. Görsel dil (kullanıcının seçimi: "C, Radar" yönü, profesyonel metinle).** Koyu lacivertten mora geçen
  radyal gradyan zemin (`#1d2b5a` → `#0a0e1f`), yarı saydam "cam" kartlar (`rgba(255,255,255,.045)` zemin,
  `.085` kenar), mavi-mor vurgu (`#7aa2ff` → `#b98bff`). Kritik skor pembe-turuncu gradyan (`#ff5d8f` → `#ff8a5d`),
  yüksek turuncu-sarı (`#ffb35d` → `#ffd36b`), olumlu/sağlıklı durum yeşil-turkuaz (`#7ee0c3`). Gösterişli ama
  **metinler kurumsal**: "Radarda sinyal" gibi oyunsu ifadeler yok. "Zafiyet Durumu", "Öncelikli Zafiyetler",
  "değerlendirme bekliyor", "Gündem" gibi ifadeler kullanılıyor. Kullanıcı bu kararı açıkça verdi.
- **G2. Yalnız koyu tema.** Kullanıcı aydınlık modu hiç kullanmıyor. Tema düğmesi ve `darkMode` localStorage
  durumu kaldırılıyor; aydınlık stiller silinebilir.
- **G3. Genel Bakış (ana sayfa, `/`).** Yerleşim `c-profesyonel-v2.html` taslağındaki gibi:
  - Üst bant: logo, "Teknoloji Radar", alt başlık "Tehdit ve Teknoloji İzleme". Menü adları tam yazılıyor:
    Genel Bakış, Zafiyetler, Siber Güvenlik, Kubernetes, SRE, DevTools, Yapay Zeka. Rotalar değişmiyor.
  - **Durum özeti:** Etiket "Zafiyet Durumu · Son 24 Saat". Başlık "N kritik zafiyet değerlendirme bekliyor".
    Alt cümle KEV sayısını ve "son ziyaretinizden bu yana M yeni kayıt" bilgisini veriyor. Kritik yoksa sakin
    bir cümle çıkıyor ("Son 24 saatte kritik zafiyet yok"); boş durum da rahatlatıcı olmalı.
  - **Dört özet kutusu:** Kritik (CVSS ≥ 9.0), Yüksek (son 7 gün), Aktif istismar (KEV), Kaynak erişilebilirliği.
  - **CVSS dağılım grafiği:** Taslaktaki radar. Merkeze yakın olan daha kritik (iç halka ≥9, orta 7–8.9,
    dış 4–6.9), lejantı var. Animasyon yavaş ve sakin bir tarama (~7 sn tur). `prefers-reduced-motion` açıksa
    animasyon durur.
  - **Öncelikli Zafiyetler listesi:** En yüksek skorlu son CVE'ler (taslakta 3; sayı uygulayıcıya kalmış, 3–5).
    Her satırda skor kutusu (sayı + KRİTİK/YÜKSEK), eşit aralıklı yazı tipinde CVE ID, Türkçe başlık, kısa
    açıklama, KEV / CWE / Yeni rozetleri, kaynak ve göreli zaman var. "Tümünü görüntüle →" `/cve`'ye gidiyor.
    Satıra tıklayınca okuma paneli açılıyor (G5).
  - **Gündem sütunu:** Diğer beş bölümden son haberler, bölüm rengiyle bir nokta, kaynak ve göreli zaman.
    Tıklayınca okuma paneli açılıyor.
  - **Alt bant:** Kaynak sağlığı ve son/sonraki çekim. Bugünkü `SaglikSeridi` bilgisi (bölüm başına son başarı,
    sessiz kaynak, çeviri kuyruğu) korunuyor, yeni görsel dile taşınıyor. Sorun varsa görünür kalmalı;
    bulgu 6 dersi: sorun "ok" gibi görünmemeli.
- **G4. Bölüm sayfaları (6 sayfa).** Aynı görsel dile geçiyor. Liste ve detay düzeni şöyle: solda ya da üstte
  liste, detay sağdan açılan **okuma paneli** (G5). Bugünkü sabit yan "detay kartı" yerine bu panel geliyor.
- **G5. Okuma paneli (tek ortak bileşen, altı bölümde aynı).** Taslak `okuma-gorunumu.html`:
  - Sağdan kayan, geniş panel; liste görünür kalıyor. Esc ve kapat düğmesiyle kapanıyor.
  - Başlık alanında ID (CVE için), Türkçe başlık, skor (CVE için) ve rozetler var. Bugünkü `CeviriEtiketi`
    çeviri sağlayıcı rozeti korunuyor.
  - **Varsayılan Türkçe.** Başlığın altında "Orijinali göster" düğmesi var; basınca İngilizce metin açılıyor,
    tekrar basınca kapanıyor. **Yan yana mod yok** (kullanıcı kararı).
  - **Çeviri yoksa orijinal göster.** Kayıt hiç çevrilmemişse İngilizce metin doğrudan gösteriliyor, üstte
    "Çevrilmedi: orijinal metin" uyarısı var. Boş ekran hiçbir zaman olmuyor (kullanıcı kararı).
  - **Paragraf düzeyi işaret (sezgisel).** Türkçe metindeki bir paragraf orijinaldeki bir paragrafla aynıysa
    ya da belirgin şekilde İngilizce görünüyorsa turuncu sol çizgiyle ve "Bu paragraf çevrilemedi" notuyla
    işaretleniyor; metin olduğu gibi okunuyor. Veritabanı çeviriyi paragraf bazında tutmadığı için bu bir
    **tahmin**; yanlış pozitif kabul edilebilir ama ana metni gizlememeli.
  - **Tipografi:** Sola hizalı (justify yok), `lang="tr"` + `hyphens: auto`, satır başına ~60–65 karakter
    (`max-width: 62ch`), 15.5px civarı punto, satır aralığı ~1.75, paragraflar arası boşluk.
  - Alt kısımda CVE için etkilenen ürünler, CWE ve referanslar var; referansların hepsi gösteriliyor, bugünkü
    3 limiti kaldırılıyor. Her kayıtta "Orijinal kaynağa git" bağlantısı var.

## 3. Hedef dışı

- **Çeviri kalitesini iyileştirmek.** Çeviri hattı (LibreTranslate → Gemini, retranslate) bu işin konusu
  değil. Arayüz yalnızca sorunu görünür kılar.
- §8'deki özet ucu dışında backend değişikliği yok. Kullanıcı hesabı ve sunucu tarafında "okundu" takibi yok.
- Aydınlık tema.
- Mobil öncelikli yeniden tasarım. Arayüz dar ekranda bozulmamalı (tek sütuna düşmeli), ama hedef masaüstü.
- `/api/v1/` entegrasyon API'si, Django admin.

**Başarısızlık sayılacak durumlar (teknik olarak çalışsa bile):** sayfa "oyuncak" ya da oyunsu görünüyor;
kritik bir CVE ilk ekranda görünmüyor; çevrilmemiş bir kayıt boş ya da gizli kalıyor; sağlık sorunu (sessiz
kaynak, takılı çeviri kuyruğu) yeni tasarımda kayboluyor; animasyon okumayı rahatsız ediyor.

## 4. Korunacak mevcut işlevler

Her bölüm sayfasındaki şu kontroller kalıyor; yalnızca yerleşimleri değişiyor. Uygulayıcının önerisi, solda
uzun form yerine sayfa üstünde kompakt bir filtre/eylem çubuğu:
- Gün sayısı seçimi, kaynak seçimi (checkbox'lar), "Çek" düğmesi (sunucunun 429 soğuma mesajı gösterilir,
  `istekHataMesaji`), önbelleği temizleme, HTML rapor indirme (`kacis` / `guvenliHref` ile; XSS korumaları
  aynen kalır).
- CVE sayfasında CVSS şiddet filtresi ve "X / Y CVE gösteriliyor" sayacı.
- Kubernetes kategori, DevTools tür ayrımları; her bileşende şu an ne varsa.
- `useAraliklaYenile` ile arka planda istek atmayan periyodik yenileme.
- Toast bildirimleri (`react-hot-toast`).

## 5. Kısıtlar

- **Yığın aynı kalıyor:** React 18, Vite 6, react-bootstrap 2 / Bootstrap 5, react-icons, react-router 7. Yeni
  bağımlılık gerekirse az ve gerekçeli olmalı; repo pip/npm sabitlemesi ve Dependabot/Scorecard hattı var.
- **CSP (nginx `guvenlik_basliklari.conf`):** `font-src 'self' data:`, `style-src 'self' 'unsafe-inline'`,
  `script-src 'self'`. Google Fonts gibi **harici font/CDN yüklenemez**. Inter / JetBrains Mono isteniyorsa
  pakete gömülmeli (ör. `@fontsource/*`); yoksa sistem yazı tipi yığını (`'Segoe UI', system-ui`) ve
  `Consolas` kullanılıyor. Karar uygulayıcıya kalmış, CSP değiştirilmeyecek.
- **Veri, mevcut uçlardan:** `/api/cve/` son 100 kaydı `-published_date` ile döndürüyor; alanlar `cve_id, source,
  severity, cvss_score, published_date, cwe_ids, references, affected_products, turkish_* / original_*,
  needs_translation, translation_provider, created_at`. **KEV** = `source === 'CISA KEV'` (CISA KEV kaynağı NVD
  `hasKev` ile çekiliyor; `cve_id` tekil olduğu için aynı CVE NVD'den önce geldiyse KEV olarak işaretlenmemiş
  olabilir, kabul edilen sınır). Gündem diğer beş bölümün liste uçlarından geliyor; sağlık bilgisi `/api/saglik/`'ten.
- **Sorun (builder check, doğrulandı):** `/api/cve/` yalnız 100 kayıt dönüyor, `-published_date` sırasıyla.
  KEV kayıtlarında `published_date` NVD yayın tarihi, KEV'e eklenme tarihi değil (`news/cve_scraper.py`
  `CISAKEVScraper`). Bu yüzden yeni KEV'e eklenmiş eski bir CVE ilk 100'e girmeyebilir. Ayrıca `/api/cve/stats/`
  zaman penceresi ve skor eşiği taşımıyor; `/api/saglik/` toplam kaynak sayısı ve sonraki çekim zamanı vermiyor.
  Liste örneklemiyle hesaplanan özet sayılar sessizce eksik çıkar. **Çözüm:** §8'deki özet ucu. Ana sayfa
  özet sayılarını yalnız ondan alıyor; listeler yine mevcut uçlardan geliyor.
- **"Son ziyaretinizden bu yana yeni":** Tarayıcıda tutuluyor (localStorage'da son görülen `created_at`).
  localStorage erişimi try/catch içinde olmalı; okunamazsa cümle bu kısmı atlıyor.
- **Testler:** Mevcut tüm Vitest testleri (2026-10-31: 6 dosyada 28 test) (`CeviriEtiketi`, `SaglikSeridi`, `useAraliklaYenile`, `utils/*`) geçmeye
  devam etmeli ya da bileşen değişince güncellenmeli. Okuma panelinin çeviri durumları (çevrilmiş / hiç
  çevrilmemiş / paragraf sezgisi / orijinal aç-kapa) ve ana sayfa özet hesapları için yeni test eklenmeli.
  CI'da `npm run lint` + `npm test` + build koşuyor.
- **Teslim:** `main` korumalı; dal + PR + 5 zorunlu check (strict). Canlı ortam Docker Compose (Vite dev server
  :3000); imaj/K8s tarafı Nginx ile aynı `dist`'i sunuyor.
- Erişilebilirlik: Renk tek başına anlam taşımıyor (skor kutusunda "KRİTİK" yazısı var). Koyu zeminde metin
  kontrastı okunur olmalı, panel klavyeyle kapanmalı, `prefers-reduced-motion` desteklenmeli.

## 6. Tasarımcının kararları (builder check sonrası, kullanıcı onaylamadı, itiraz edilebilir)

- **Pencereler:** Başlıktaki sayı = `created_at` son 24 saat içinde olan CVSS ≥ 9.0 kayıtlar. Kutular: Kritik
  (24 sa), Yüksek 7.0–8.9 (7 gün), Aktif istismar KEV (7 gün, KEV'e eklenme tarihiyle), Kaynak sağlığı.
  "Değerlendirme bekliyor" ifadesi okundu takibi anlamına gelmiyor; "son 24 saatte geldi" demek.
  24 saatte kritik yoksa başlık "Son 24 saatte kritik zafiyet yok" oluyor; altında 7 günlük yüksek sayısı sakin
  bir dille veriliyor.
- **Son ziyaret / "Yeni" rozeti:** `lastSeen` (localStorage), sayfa gizlenince (`visibilitychange` → hidden) ya da
  kapanırken (`pagehide`) en yeni `created_at` ile yazılıyor; sayfa yenilemesi rozetleri silmiyor. "Yeni" =
  `created_at > lastSeen`. İlk ziyarette (değer yok) "son ziyaretinizden bu yana" cümlesi ve "Yeni" rozeti
  gösterilmiyor.
- **Okuma paneli alanları:** Ortak arayüz `{baslik, govdeTr, govdeOrijinal, tarih, kaynak, link, rozetler, ekAlanlar}`;
  her bölüm kendi eşlemesini yapıyor. Siber Güvenlik: `turkish_description`, boşsa `turkish_summary`; tarih alanı
  `date`. Kubernetes `category`/`version`, DevTools `entry_type`/`version` rozet olarak. CVE başlığı için mevcut
  `cveListeBasligi` yardımcı fonksiyonu kullanılıyor.
- **KEV öneki:** `original_description` başındaki "Added to the CISA KEV catalog on …; required action due …"
  öneki gövdeden ayrılıyor ve panelde meta satırı olarak gösteriliyor ("KEV'e eklenme: tarih · Son işlem tarihi:
  tarih"). Paragraf sezgisi bu öneki hiç değerlendirmiyor; aksi halde her KEV kaydı yanlış işaretlenirdi.
- **Panel durumu URL'de:** Bölüm sayfalarında seçili kayıt `?kayit=<id>` sorgu parametresinde tutuluyor
  (paylaşılabilir, geri tuşu paneli kapatıyor). Ana sayfada panel yerinde açılıyor, kendi durumunu tutuyor.
  Periyodik yenileme seçimi düşürmemeli: seçim nesne kimliğiyle değil `id` ile eşleştiriliyor.
- **Gündem sütunu:** Beş bölümün listesi birleştirilip `created_at` azalan sırayla diziliyor; 6 kayıt. "Her
  bölümden bir" kuralı yok. Göreli zaman `goreliZaman` ile gösteriliyor; 24–48 saat için "dün" eklenebilir.
- **CVSS grafiği:** Son 7 günde gelen ve skoru olan CVE'ler, en fazla 40 nokta (yüksek skor öncelikli). Halkalar
  ≥9 / 7–8.9 / 4–6.9; skorsuz ve 4.0 altı kayıtlar çizilmiyor, lejantta "N skorsuz" notu var.

## 7. Uygulayıcıya bırakılanlar

- Bileşen ayrımı (ör. ortak `OkumaPaneli`, `SkorKutusu`, `Rozet`, `CamKart`) ve altı bölüm bileşenindeki
  tekrarın ne kadar ortaklaştırılacağı.
- CSS düzeni: `App.css`'i yeniden yazmak, CSS değişkenleriyle tema token'ları, Bootstrap'in koyu temasını
  (`data-bs-theme="dark"`) taban almak.
- CVSS grafiğinde noktaların açısal yerleşimi (kaynağa göre mi, deterministik karma mı). Anlam yalnızca
  merkeze uzaklıkta.
- Paragraf sezgisinin tam kuralı (eşitlik + basit İngilizce işaret kelimeleri vb.); yanlış pozitif olursa
  zararsız kalmalı.
- Öncelikli listede kaç kayıt gösterileceği (3–5).

## 8. Backend özet ucu (kullanıcı kararı, 2026-10-31: "Evet, ekle")

- Yeni, salt okunur, anonim bir uç: `GET /api/ozet/`. Mevcut arayüz uçları gibi Redis'te kısa süreli önbellekleniyor
  (`/api/saglik/` gibi ~60 sn). Rate limit ve güvenlik başlıkları mevcut uçlarla aynı. Django testleri
  (`news/tests/`) birlikte geliyor.
- Döndürdüğü değerler (§6'daki pencerelerle): kritik sayısı (24 sa), yüksek sayısı (7 gün), KEV sayısı (7 gün,
  **KEV'e eklenme tarihine göre**), öncelikli CVE listesi, CVSS grafiği noktaları (`cve_id`, skor), toplam ve
  sessiz kaynak sayısı, son ve sonraki çekim zamanı (Celery beat takviminden; sabit kodlanmış "6 sa" değil).
- KEV eklenme tarihi bugün yalnızca `original_description` önekinde duruyor. Uygulayıcı ya bu öneki ayrıştırır
  ya da `CVEEntry`'ye alan ekler (migration ve mevcut kayıtlar için önekten geri doldurma). Alan eklemek tercih
  edilir. Hangisi seçilirse seçilsin, okuma panelindeki KEV meta satırı (§6) aynı kaynaktan beslenir.
- Toplam kaynak sayısı kaynak kayıt defterinden (`news/kaynaklar.py`) gelir, arayüzde sabit sayı yazılmaz.
- `/api/v1/` entegrasyon API'si değişmiyor.
