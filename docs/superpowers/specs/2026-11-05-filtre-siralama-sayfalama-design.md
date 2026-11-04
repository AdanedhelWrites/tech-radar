# Bölüm Listeleri: Filtre, Sıralama ve Sayfalama — Tasarım

> Tarih: 2026-11-05. Kaynak: brainstorming oturumu, görsel taslak
> `CyberNews/.superpowers/brainstorm/940-1793828793/content/filtre-sayfalama.html` (repo dışı).
> Durum: taslak, onay bekliyor.

## 1. Amaç ve neden

Kullanıcının şikâyeti: "Filtreler çalışmıyor, günlük sıralayamıyorum. Sanki sınırsızmış hissi uyandırıyor.
Sayfa sınırları (paging) ayarlanabilir mi?"

2026-11-02 UI turunda ölçülen durum:

- Her bölüm listesi API'den **en yeni 100 kaydı** alıyor. Örneğin `news/views.py` içinde
  `order_by(...)[:100]`, `news/cache_utils.py` içinde `CACHE_LISTE_SINIRI = 100`. Zafiyetler'de 11.837 kaydın
  100'ü görünüyor.
- **Dönem seçimi** ("Son N gün") yalnız "Çek" düğmesine gidiyor; listeyi süzmüyor. 1 gün ile 15 gün aynı listeyi
  gösteriyor.
- **Önem / kategori filtreleri** tarayıcıda bu 100 kaydın içinde süzüyor. "Kritik" seçilince "22 / 100" çıkıyor,
  oysa veritabanında 1.559 kritik kayıt var.
- Liste `published_date` (haberde `date`) ile sıralı, satırdaki "6 sa önce" ise `created_at`'tan geliyor. Sıra
  ile görünen zaman tutarsız.

**Başarı ölçütü:**

- "Son 1 gün" seçilince listede yalnız son 24 saatin kayıtları kalır.
- Sayım gerçek toplamı söyler ("Son 1 günde 54 kayıt · 1–25 gösteriliyor").
- Kullanıcı sayfa sayfa bütün kayıtlara ulaşabilir.
- Liste tarihe göre (Zafiyetler'de CVSS'e göre de) sıralanabilir.

## 2. Hedefler

### G1. Altı bölümde aynı davranış

Siber Güvenlik (`/news`), Zafiyetler (`/cve`), Kubernetes (`/k8s`), SRE (`/sre`), DevTools (`/devtools`) ve
Yapay Zeka (`/ai`) aynı filtre, sıralama ve sayfalama davranışını paylaşır. Ortak parçalar bir kez yazılır
(`BolumSayfasi` ve bir yardımcı/hook). Bölüm bileşenleri yalnız bölüme özgü seçenekleri verir.

### G2. Süzme, sıralama ve sayfalama sunucuda

Mevcut arayüz uçları (`/api/news/`, `/api/cve/`, `/api/k8s/`, `/api/sre/`, `/api/devtools/`, `/api/ai/`) şu
sorgu parametrelerini alır:

| Parametre | Değer | Anlam |
|---|---|---|
| `gun` | 1, 3, 7, 14, 30 ya da yok (Tümü) | `created_at` son N gün içinde. Yoksa süzme yok; saklama zaten 90 gün |
| `sirala` | `yeni` (varsayılan), `eski`, `cvss` (yalnız cve) | `-created_at` / `created_at` / `-cvss_score` (skorsuzlar en sonda), eşitlikte `-created_at`, sonra `-id` |
| `sayfa` | 1… | 1 tabanlı |
| `boyut` | varsayılan 25, en fazla 100 | sayfa başına kayıt |
| `kaynak` | virgülle ayrılmış kaynak adları | `source` bu kümede. Yoksa tüm kaynaklar |
| `onem` | `kritik`, `yuksek`, `orta`, `dusuk` (yalnız cve) | CVSS aralığı. Bugünkü `severityOptions` sınırları: ≥9, 7–8.9, 4–6.9, 0–3.9. Skorsuz kayıt yalnız "Tümü"de görünür |
| `kategori` | k8s `category` değeri, devtools `entry_type` değeri | bölüme özgü mevcut ek filtrenin sunucu karşılığı |

- **Yanıt** bugünkü zarfı korur ve genişletir: `{success, data, cached, count, toplam, sayfa, sayfa_sayisi, boyut}`.
  `count` sayfadaki kayıt sayısı olarak kalır (geriye uyum). `toplam` filtreye uyan bütün kayıtların sayısıdır.
- **Geçersiz parametre** (bilinmeyen `sirala`, sayı olmayan `sayfa` gibi) 400 değil, varsayılana düşer. Sayfa
  sayısını aşan `sayfa` son sayfayı döndürür.
- **Parametresiz istek** bugünkü yanıtın eşdeğerini döner: en yeni 25 kayıt ve yeni alanlar. Böylece eski arayüz
  sekmeleri kırılmaz.

### G3. "Son N gün" radara giriş zamanına göre (benim kararım)

- Süzme ve "En yeni / En eski" sıralaması `created_at`'a göre yapılır. Satırda gösterilen göreli zaman da bu.
- **Bedel:** NVD'nin bugün güncellediği eski bir CVE de "son 1 gün"e girer. Okuma panelindeki yayın tarihi
  değişmez. Kullanıcı bu kararı onayladı.

### G4. Arayüz (kullanıcının seçimi: numaralı sayfalar, taslakta A)

- **Filtre çubuğu:** Dönem, **yeni** "Sırala", Kaynaklar, bölüme özgü düğmeler (Zafiyetler'de önem, Kubernetes'te
  kategori, DevTools'ta tür), Yenile, HTML rapor, Önbelleği temizle, Çek.
- **Sırala seçenekleri:** "En yeni", "En eski". Zafiyetler'de ayrıca "En yüksek CVSS".
- **Dönem seçenekleri:** "Son 1 gün", "Son 3 gün", "Son 7 gün" (varsayılan), "Son 14 gün", "Son 30 gün", "Tümü"
  (benim kararım; bugün 1–15 arası her gün seçilebiliyor).
- **Sayım satırı:** "Son 1 günde 54 kayıt · 1–25 gösteriliyor". Tümü seçiliyse "5.432 kayıt · 26–50 gösteriliyor".
  Sonuç yoksa bugünkü "Bu filtreyle eşleşen kayıt bulunamadı." metni.
- **Sayfa çubuğu** listenin altında: "‹ Önceki", numaralar ve "Sonraki ›".
  - Çok sayfada ilk, son ve geçerli sayfanın iki komşusu görünür, aradakiler "…" olur.
  - Tek sayfada çubuk gizlenir.
- **Adres:** filtre, sıralama ve sayfa adreste tutulur (örnek `/cve?gun=1&sirala=cvss&sayfa=2&onem=kritik`).
  - Geri tuşu ve yenileme aynı görünüme döner.
  - Filtre ya da sıralama değişince sayfa 1'e döner.
  - Varsayılan değerler adrese yazılmaz.
- **Kaynaklar menüsü** listeyi de süzer ve hangi kaynaklardan çekileceğini de belirler (benim kararım). Bugün
  yalnız çekmeyi belirliyor. Dönem de artık hem listeyi hem çekmeyi belirleyecek; ikisi aynı mantıkla çalışsın.
- **"Çek" düğmesi** seçili dönemi kullanır, ama kaynaklardan en fazla 15 gün çeker (`min(gun, 15)`; Tümü → 15).
  Kaynak tarafının sınırı değişmez.
- **Otomatik yenileme** (5 sn, `useAraliklaYenile`) geçerli adresi yeniden ister.
  - Sayfa ve filtre değişmez.
  - Açık okuma paneli kapanmaz: seçili kayıt sayfadan düşse bile panel açık kalır, bugünkü `useSeciliKayit`
    davranışı korunur.
- **HTML rapor** geçerli filtre ve sıralamayla çalışır, sayfadan bağımsızdır. Sunucudan `boyut=100` ile ilk 5
  sayfa, yani en fazla 500 kayıt alınır (benim kararım). Bugün yalnız ekrandaki 100 kaydı içeriyor.
- **Ana sayfa:** Öncelikli Zafiyetler'deki "Tümünü görüntüle" bağlantısı `/cve?sirala=cvss` adresine gider.
  Dönem varsayılanı zaten 7 gün olduğu için ana sayfadaki "son 7 gün" penceresiyle örtüşür.

### G5. Önbellek

- Bugünkü tek anahtarlı liste önbelleği (`cybersecurity_news`, `cve_entries` …; `cache_yenile` ile çekim
  sırasında kurulur) yalnız **parametresiz/varsayılan** istek için kalabilir ya da kaldırılabilir. Uygulayıcının
  kararı.
- Koşul: filtreli istekler bayat ya da yanlış filtreli veri döndürmez.
- Yeni kayıt geldiğinde en geç bir yenileme turunda (5 sn) listede görünür. Bugün çekim sırasında yeni kayıtların
  akması bu önbellek yenilemesine dayanıyor; bu davranış korunur.

## 3. Hedef olmayanlar

- `/api/v1/` (dış tüketici, imleçli delta) değişmez.
- Gündem puanlaması ve haberlerde "önem" sıralaması sonraki projeye kalır.
- Arama kutusu (metin araması) yok.
- Sonsuz kaydırma ya da "daha fazla yükle" yok (kullanıcı A'yı seçti).
- Veri modeli değişmez. Tek istisna `created_at` için bir indeks olabilir (bkz. §6).
- Çekim (fetch) mantığı, kaynak listeleri, çeviri işleri değişmez.

## 4. Karşı hedefler (çalışsa bile başarısızlık sayılır)

- Filtre değişince ya da otomatik yenilemede okuma panelinin kapanması, sayfanın 1'e atlaması ya da listenin
  zıplaması (filtre değişimi dışında).
- Sayımın gerçek toplamla tutarsız olması, ya da sayfa sınırında kaydın iki sayfada görünmesi veya hiç
  görünmemesi. Bu yüzden sıralama her zaman benzersiz bir anahtarla (`id`) biter.
- Parametresiz istekle çalışan bir istemcinin (eski sekme, rapor, testler) kırılması.
- Filtreli isteğin önbellekten başka filtrenin sonucunu alması.
- Liste isteklerinin belirgin yavaşlaması. Hedef: 12 bin CVE üzerinde tek sayfa sorgusu ~50 ms altında.

## 5. Kısıtlar

- Yalnız yerel çalışma: Docker Desktop compose ve docker-desktop K8s. `main` korumalı: dal, PR ve zorunlu
  kontroller. Merge kullanıcının açık onayıyla.
- Testler:
  - Django: `scripts/pg_test.sh` ile tek kullanımlık PG ve Redis.
  - Vitest: frontend'i `teknoloji-frontend` konteynerinin `/tmp`'sine kopyalayıp orada koşmak. Windows `npx` ve
    bind mount çalışmıyor.
- Kod ASCII Türkçe adlar ve yorumlarla, mevcut üslupta. Kullanıcıya görünen metin düzgün Türkçe.
- React 18 + react-router-dom 7 (`useSearchParams`), react-bootstrap.
- Arayüz uçları anonim (`AllowAny`); yeni parametreler yetki modelini değiştirmez.

## 6. Uygulayıcıya kalanlar

- Liste sorgusunun ortak bir yardımcıda toplanması: altı görünüm tek fonksiyonu bölüm tanımıyla çağırır. Bugün
  görünümler kopya.
- Sayfalama yöntemi (Django `Paginator`, ya da `count()` + dilim). Koşul: G2'deki yanıt alanları ve geçersiz
  girdi kuralları.
- `created_at` indeksi: ölçüme göre (CVE ~12 bin, haber ~1,5 bin kayıt). Gerekirse tek migration; repo kuralı
  gereği önce migration canlıya uygulanır.
- Önbellek stratejisi (G5).
- Sayfa çubuğunun tam görünümü ve tema uyumu (mevcut `cam-kart` / `cubuk-dugme` stilleri).
- Adres parametrelerinin bileşen durumuyla eşlenmesi (tek hook önerilir, ör. `useListeSorgusu`).
- README'deki API bölümünde yeni parametrelerin belgelenmesi.

## 7. Uygulayıcı kontrolünden sonra netleşenler

- **`created_at` güvenilir mi?** 2026-11-05'te ölçüldü: günlük dağılım düzgün.
  - CVE günde 166–411 kayıt (11-04: 248), haber günde 12–73 kayıt. Toplu damga ya da sıçrama yok.
  - Yeniden çekim `update_or_create` ile mevcut kaydı günceller; `created_at` değişmez.
  - Yalnız 90 günlük saklama dışına düşüp kaynakta yeniden görünen kayıt yeni `id` ve yeni `created_at` alır
    (ADR-0005). Bu nadirdir ve kabul edildi; geri dönüş yolu gerekmez.
- **Tümü:** veritabanındaki her şey. Saklama zaten 90 gün.
  - Ana sayfanın "son 7 gün" penceresi de `created_at` kullanıyor (`news/ozet.py` `son_hafta`), yani
    `/cve?sirala=cvss` ile Dönem 7 gün tam örtüşür.
- **`onem`:** `cvss_score` aralıklarıyla çalışır, saklanan `severity` alanıyla değil. Arayüz ve ana sayfa özeti de
  skoru kullanıyor.
  - İkisinin uyuşmadığı yalnız 6 kayıt var (ölçüldü); istatistik rozetleri `severity` ile saymaya devam eder,
    küçük fark kabul.
  - Skorsuz kayıt yalnız "Tümü"de görünür.
- **`kaynak`:** `source` alanıyla birebir (büyük/küçük harf duyarlı) eşleşir. Kaynak adlarında virgül yok
  (ölçüldü).
  - Bilinmeyen ad hiçbir kayıtla eşleşmez.
  - Yalnız bilinmeyen adlar verilirse sonuç boş döner; sessizce "tümü"ye dönülmez.
  - Arayüz yalnız seçenek listesindeki adları gönderir.
- **Parametresiz istek:** gün süzmesi yok, `sirala=yeni`, ilk 25 kayıt.
  - Arayüz her istekte `gun`'u açıkça gönderir; varsayılanı 7.
  - "Varsayılan değerler adrese yazılmaz" kuralı yalnız tarayıcı adres çubuğu içindir, API isteği için değil.
- **HTML rapor:** bütün geçerli seçimleri kullanır: dönem, sıralama, kaynak, önem/kategori.
  - Sayfaları sırayla en fazla 5 kez `boyut=100` ile çeker.
  - `toplam > 500` ise raporun başına "İlk 500 kayıt (toplam N)" notu konur.
- **Diğer kullanıcılar:** `/api/v1/`, `*/stats/` uçları ve ana sayfa özeti (`/api/ozet/`, Öncelikli Liste)
  etkilenmez.
  - Ana sayfanın Gündem kartı liste uçlarını **parametresiz** çağırıyor (`GenelBakis.jsx`,
    `gundemBirlestir` en yeni 6 kaydı `created_at` ile seçer).
  - Parametresiz yanıt artık `created_at`'a göre en yeni 25 kayıt döndürüyor, bu yüzden Gündem değişmeden
    çalışır. Bir Vitest testi bunu sabitler.
  - Liste uçlarının eski davranışını (100 kayıt) sabitleyen mevcut testler yeni sözleşmeye göre güncellenir.
  - `success`, `data`, `cached` ve `count` alanlarının varlığı korunur.

## 8. Benim verdiğim kararlar (kullanıcı onayında kontrol etsin)

- Dönem seçenekleri 1/3/7/14/30/Tümü, varsayılan 7. Çek en fazla 15 gün çeker.
- Kaynaklar menüsü listeyi de süzer.
- HTML rapor geçerli filtreyle en fazla 500 kayıt içerir.
- Sayfa boyutu 25, sayfa çubuğunda sayfa boyutu seçimi yok.
- "Tümünü görüntüle" bağlantısı `/cve?sirala=cvss` adresine gider.
