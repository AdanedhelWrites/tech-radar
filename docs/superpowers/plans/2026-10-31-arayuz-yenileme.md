# Arayüz Yenileme Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ana sayfayı zafiyet odaklı bir "Genel Bakış" paneline, altı bölümün detayını ortak ve akıcı bir okuma paneline çevirmek. Sayılar için yeni `/api/ozet/` ucunu eklemek.

**Architecture:** Backend'e bir alan (`CVEEntry.kev_added_date`), bir hesap modülü (`news/ozet.py`) ve anonim bir uç (`GET /api/ozet/`) ekleniyor. Frontend'de koyu tema token'ları tek CSS dosyasında toplanıyor. Saf yardımcılar (`utils/okuma.js`, `utils/okumaKaydi.js`, `utils/sonZiyaret.js`, `utils/gundem.js`) test ediliyor. `OkumaPaneli` react-bootstrap `Offcanvas` üzerine kuruluyor ve altı sayfa bunu `?kayit=<id>` ile açıyor. `GenelBakis` sayfası özet ucunu ve mevcut liste uçlarını kullanıyor.

**Tech Stack:** Django 5.2 + DRF, PostgreSQL 16, Redis cache. React 18, Vite 6, react-bootstrap 2 / Bootstrap 5.3, react-router 7, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-31-arayuz-yenileme-design.md`

## Global Constraints

- Yeni npm/pip bağımlılığı yok. Yazı tipleri sistem yığını: gövde `'Segoe UI', system-ui, -apple-system, sans-serif`, ID'ler `Consolas, 'Cascadia Mono', monospace`. CSP (`frontend/guvenlik_basliklari.conf`) değişmiyor; harici font/CDN yok.
- Yalnızca koyu tema. `<html data-bs-theme="dark">`. Tema düğmesi ve `darkMode` localStorage anahtarı kaldırılıyor.
- Renk token'ları (spec §2 G1): zemin `radial-gradient(1200px 520px at 12% -12%, #1d2b5a 0%, #0a0e1f 58%)`, cam kart `rgba(255,255,255,.045)` / kenar `rgba(255,255,255,.085)`, vurgu `#7aa2ff` → `#b98bff`, kritik `#ff5d8f` → `#ff8a5d`, yüksek `#ffb35d` → `#ffd36b`, sağlıklı `#7ee0c3`, ikincil metin `#a9c0ff`.
- Metinler kurumsal. Kullanılacak ifadeler: "Genel Bakış", "Zafiyetler", "Siber Güvenlik", "Kubernetes", "SRE", "DevTools", "Yapay Zeka", "Zafiyet Durumu · Son 24 Saat", "Öncelikli Zafiyetler", "Gündem", "Tümünü görüntüle →", "Orijinali göster" / "Orijinali gizle", "Çevrilmedi: orijinal metin", "Bu paragraf çevrilemedi". "Radar", "sinyal" gibi oyunsu ifadeler yasak (logo adı "Teknoloji Radar" hariç).
- Okuma metni: `text-align: left` (justify yasak), `lang="tr"` + `hyphens: auto`, `max-width: 62ch`, `font-size: 15.5px`, `line-height: 1.75`.
- `prefers-reduced-motion: reduce` iken bütün animasyonlar duruyor.
- Pencereler (spec §6): kritik = `cvss_score >= 9.0` ve `created_at` son 24 sa; yüksek = `7.0 <= cvss_score < 9.0` ve `created_at` son 7 gün; KEV = `kev_added_date` son 7 gün.
- Var olan bütün testler geçmeli (Django `manage.py test news`, Vitest 28 test). `npm run lint` hatasız.
- Teslim: `feat/arayuz-yenileme` dalı, PR, 5 zorunlu check. `main`'e doğrudan push yok.
- Komutlar: Django `docker compose exec teknoloji-api python manage.py test <etiket> --noinput`, frontend `docker compose exec teknoloji-frontend npm test -- <dosya>` (lint: `... npm run lint`, build: `... npm run build`). Komutlar repo kökünden (`cybersecurity_news/`) çalışır.

## Review Focus

1. NVD yolu bir KEV kaydını yeniden yazdığında `kev_added_date` korunmalı, `None` ile ezilmemeli. → Task 1, `test_nvd_yeniden_yazimi_kev_tarihini_ezmez`.
2. Boş veritabanı: `/api/ozet/` sıfırlar ve boş listeler dönmeli, ana sayfa sakin boş durum cümlesini göstermeli. → Task 2 `test_bos_veritabani`, Task 6 `kritik yoksa sakin cumle`.
3. localStorage hata fırlatırsa (gizli pencere) ana sayfa açılmalı, "son ziyaret" cümlesi gösterilmemeli. → Task 3 `localStorage hata firlatirsa null doner`.
4. `?kayit=` bilinmeyen bir id gösteriyorsa (saklama süresiyle silinmiş kayıt ya da elle yazılmış adres) panel kapalı kalmalı. Periyodik yenileme yeni nesneler getirse bile açık panel kapanmamalı. → Task 7 testleri.
5. Türkçe ve orijinal metnin ikisi de boşsa panel "İçerik bulunmuyor." demeli. Kısa teknik paragraflar (ürün adı, sürüm) yanlışlıkla "çevrilemedi" diye işaretlenmemeli. → Task 3 `kisa paragraf isaretlenmez`, Task 5 `icerik yoksa bilgi verir`.

---

### Task 1: `CVEEntry.kev_added_date` alanı, migration ve scraper

**Files:**
- Create: `news/kev.py`
- Modify: `news/models.py` (CVEEntry), `news/cve_scraper.py` (`CISAKEVScraper`, ~satır 760-780), `news/tasks.py` (`fetch_cve_task` defaults, ~satır 135)
- Create: `news/migrations/0016_cveentry_kev_added_date.py`
- Test: `news/tests/test_kev.py`

**Interfaces:**
- Produces: `kev_oneki_ayir(metin: str) -> tuple[date | None, date | None, str]`, sırasıyla eklenme tarihi, son işlem tarihi ve önek atılmış gövde. `CVEEntry.kev_added_date = models.DateField(null=True, blank=True, db_index=True, verbose_name='KEV Eklenme Tarihi')`. Serializer `__all__` olduğu için alan `/api/cve/` yanıtında otomatik görünür.

- [ ] **Step 1: Write the failing tests** (`news/tests/test_kev.py`, `TestCase`)

```python
def test_onek_ayrilir(self):
    t, son, govde = kev_oneki_ayir('Added to the CISA KEV catalog on 2026-10-20; required action due 2026-11-10. Bir hata.')
    self.assertEqual((t, son, govde), (date(2026, 10, 20), date(2026, 11, 10), 'Bir hata.'))

def test_son_tarihsiz_onek(self):
    self.assertEqual(kev_oneki_ayir('Added to the CISA KEV catalog on 2026-10-20. X'), (date(2026, 10, 20), None, 'X'))

def test_onek_yoksa_dokunmaz(self):
    self.assertEqual(kev_oneki_ayir('Plain text.'), (None, None, 'Plain text.'))
    self.assertEqual(kev_oneki_ayir(''), (None, None, ''))

def test_migration_geri_doldurur(self):
    # MigrationExecutor ile 0015'e dön, öneki olan bir CVEEntry yaz, 0016'ya ilerle;
    # kev_added_date == date(2026, 10, 20), öneksiz kayıt None kalır. Desen: news/tests/test_migrations_0009.py
    ...

def test_nvd_yeniden_yazimi_kev_tarihini_ezmez(self):
    # fetch_cve_task'ın yazma yolu: KEV kaydı (kev_added_date=2026-10-20) varken aynı cve_id NVD
    # sözlüğüyle (kev_added_date anahtarı yok) yazılınca alan 2026-10-20 kalır.
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec teknoloji-api python manage.py test news.tests.test_kev --noinput`
Expected: FAIL (`ImportError: kev_oneki_ayir`).

- [ ] **Step 3: Implement**
  - `news/kev.py`: `kev_oneki_ayir`. Regex `^Added to the CISA KEV catalog on (\d{4}-\d{2}-\d{2})(?:; required action due (\d{4}-\d{2}-\d{2}))?\.\s*`. Önek yalnızca metnin başındaysa tanınır.
  - Model alanı ekle. Migration 0016'da `AddField` ve ardından `RunPython(geri_doldur, migrations.RunPython.noop)` var. `geri_doldur` yalnızca `original_description__startswith='Added to the CISA KEV catalog on '` olan kayıtları `kev_oneki_ayir` ile doldurur. `original_description` değişmez.
  - `CISAKEVScraper`: `kayit['kev_added_date'] = eklenme_tarihi`.
  - `fetch_cve_task`: `defaults` sözlüğüne `kev_added_date` **yalnızca** `cve.get('kev_added_date')` doluysa eklenir. Review Focus 1 bunu gerektiriyor.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec teknoloji-api python manage.py test news.tests.test_kev news.tests.test_migrations_0010 --noinput`
Expected: PASS (0010'daki `makemigrations --check` de dahil).

- [ ] **Step 5: Commit**

```bash
git add news/kev.py news/models.py news/cve_scraper.py news/tasks.py news/migrations/0016_cveentry_kev_added_date.py news/tests/test_kev.py
git commit -m "feat(cve): KEV eklenme tarihi alani ve geri doldurma"
```

### Task 2: `GET /api/ozet/` özet ucu

**Files:**
- Create: `news/ozet.py`
- Modify: `news/views.py` (`get_saglik`'in altına `get_ozet`), `news/urls.py`
- Test: `news/tests/test_ozet.py`

**Interfaces:**
- Consumes: `CVEEntry.kev_added_date` (Task 1), `fetch_runs.bolum_ozetleri()`, `kaynaklar.bolum_kaynaklari(bolum)`, `kaynaklar.BOLUMLER`, `settings.CELERY_BEAT_SCHEDULE['fetch-cve-every-6h']['schedule']`.
- Produces: `ozet_hesapla(simdi: datetime | None = None) -> dict` ve `yeni_kayit_sayisi(since: datetime) -> int`. Uç `GET /api/ozet/?since=<ISO>` şu yanıtı döner:

```json
{
  "generated_at": "ISO",
  "critical_count": 3, "high_count": 12, "kev_count": 2,
  "priority": [ /* CVEEntrySerializer, en fazla 5 */ ],
  "chart": [{"cve_id": "CVE-…", "cvss_score": 9.8}],
  "unscored_count": 4,
  "sources": {"total": 47, "silent": 1},
  "fetch": {"last_success_at": "ISO|null", "next_at": "ISO"},
  "new_since_count": 1
}
```

  - `priority`: `created_at` son 7 gün, `cvss_score >= 7.0`, sıralama `-cvss_score, -created_at`, en fazla 5 kayıt. KEV olup (`kev_added_date` son 7 gün) skoru 7'nin altında kalan kayıtlar da aday; KEV kayıtları eşit skorda önce gelir.
  - `chart`: `created_at` son 7 gün, `cvss_score >= 4.0`, `-cvss_score`, en fazla 40. `unscored_count` = aynı penceredeki skorsuz ya da 4.0 altı kayıtların sayısı.
  - `sources.total` = `sum(len(bolum_kaynaklari(b)) for b in BOLUMLER)`, `sources.silent` = `bolum_ozetleri()`'ndeki `silent_sources` uzunluklarının toplamı.
  - `fetch.next_at` = `schedule.remaining_estimate(simdi) + simdi` (celery `crontab`). `last_success_at` = `bolum_ozetleri()['cve']['last_success_at']`.
  - `new_since_count` yalnızca geçerli `since` gelirse var, `created_at > since` sayısıdır. Geçersiz ya da eksik `since` → alan yok, yanıt yine 200.
  - Önbellek: `since` dışındaki gövde `cache` anahtarı `ozet_govdesi`, 60 sn. `new_since_count` her istekte ayrı bir `count()` ile hesaplanır.
  - `@api_view(['GET'])`, `@permission_classes([AllowAny])`; throttle ayarları `get_saglik` ile aynı.

- [ ] **Step 1: Write the failing tests** (`news/tests/test_ozet.py`, `V1TestCase` tabanı, `setUp`'ta `cache.delete('ozet_govdesi')`)

```python
def test_bos_veritabani(self):
    g = self.client.get('/api/ozet/').json()
    self.assertEqual((g['critical_count'], g['high_count'], g['kev_count']), (0, 0, 0))
    self.assertEqual((g['priority'], g['chart'], g['unscored_count']), ([], [], 0))
    self.assertGreater(g['sources']['total'], 0)
    self.assertIn('next_at', g['fetch'])
    self.assertNotIn('new_since_count', g)

def test_pencereler(self):
    # created_at'ı update() ile geri çek: 9.8 (2 sa önce) → kritik; 9.1 (30 sa önce) → kritik DEĞİL, yüksek de değil;
    # 8.6 (3 gün önce) → yüksek; 7.5 (8 gün önce) → hiçbiri
    # kev_added_date = bugün-3 olan 6.5 skorlu kayıt → kev_count=1 ve priority'de var
    ...  # assertEqual(critical_count, 1); high_count == 1; kev_count == 1

def test_priority_sirasi_ve_limit(self):
    # 7 adet ≥7 kayıt → len(priority) == 5, skorlar azalan
    ...

def test_chart_skorsuzlari_ayirir(self):
    # skor None ve 3.1 olan iki kayıt → chart'ta yok, unscored_count == 2
    ...

def test_since_sayar_ve_gecersizi_yok_sayar(self):
    # since = 1 sa önce, 2 kayıt sonrası → new_since_count == 2; since='bozuk' → 200, alan yok
    ...

def test_tokensiz_erisim(self):
    self.assertEqual(self.client.get('/api/ozet/').status_code, 200)
```

- [ ] **Step 2: Run to verify fail**

Run: `docker compose exec teknoloji-api python manage.py test news.tests.test_ozet --noinput`
Expected: FAIL (404).

- [ ] **Step 3: Implement** `news/ozet.py` (`ozet_hesapla`, `yeni_kayit_sayisi`), `get_ozet` view and `path('api/ozet/', views.get_ozet, name='get_ozet')`. `since`'ı `django.utils.dateparse.parse_datetime` ile oku; tarih naive gelirse UTC kabul et.

- [ ] **Step 4: Run to verify pass**

Run: `docker compose exec teknoloji-api python manage.py test news.tests.test_ozet news.tests.test_saglik --noinput`
Expected: PASS.

- [ ] **Step 5: Commit** — `feat(api): /api/ozet/ zafiyet ozeti ucu`

### Task 3: Saf yardımcılar (okuma, son ziyaret, gündem, zaman)

**Files:**
- Create: `frontend/src/utils/okuma.js`, `frontend/src/utils/sonZiyaret.js`, `frontend/src/utils/gundem.js`
- Modify: `frontend/src/utils/zaman.js` ("dün")
- Test: `frontend/src/utils/okuma.test.js`, `sonZiyaret.test.js`, `gundem.test.js`, `zaman.test.js` (ekleme)

**Interfaces:**
- Produces:
  - `paragraflar(metin: string) -> string[]`: `\n\n` ile böler, `trim` eder, boşları atar.
  - `kevOnekiAyir(metin: string) -> { kevEklenme: string|null, sonTarih: string|null, govde: string }`. Python `kev_oneki_ayir` ile aynı regex'i kullanır; tarihler `YYYY-MM-DD` dizesi olarak döner.
  - `cevrilmemisMi(trParagraf: string, orijinalParagraflar: string[]) -> boolean`. Paragraf 40 karakterden kısaysa `false`. Herhangi bir orijinal paragrafla birebir aynıysa `true`. Paragrafta Türkçe harf (`çğıöşüÇĞİÖŞÜ`) yoksa ve şu İngilizce işaret kelimelerinden en az ikisi bütün kelime olarak geçiyorsa (`the, and, of, to, is, which, allows, attacker, vulnerability, could, with`) `true`. Diğer durumlarda `false`.
  - `okumaIcerigi({ govdeTr, govdeOrijinal }) -> { paragraflar: {metin, cevrilmedi}[], orijinal: string[], tamamenCevrilmedi: boolean }`. `govdeTr` boşsa `paragraflar` orijinalden üretilir, `tamamenCevrilmedi=true` olur ve tek tek paragraflar işaretlenmez.
  - `sonZiyaretOku() -> string|null` ve `sonZiyaretYaz(iso: string) -> void`. Anahtar `tr.sonZiyaret`. Erişim try/catch içinde; hata olursa `null` döner ya da sessizce geçer.
  - `gundemBirlestir(listeler: {bolum: string, kayitlar: object[]}[], adet = 6) -> {bolum, kayit}[]`: `created_at` azalan sırayla.
  - `goreliZaman`: 86400–172799 sn arası "dün" döner, daha eskiler `N gün önce`.

- [ ] **Step 1: Write the failing tests**

```js
// okuma.test.js
it('kev onekini ayirir', () => expect(kevOnekiAyir('Added to the CISA KEV catalog on 2026-10-20; required action due 2026-11-10. Gövde.'))
  .toEqual({ kevEklenme: '2026-10-20', sonTarih: '2026-11-10', govde: 'Gövde.' }))
it('orijinalle ayni paragraf isaretlenir', () => expect(cevrilmemisMi(EN_UZUN, [EN_UZUN])).toBe(true))
it('ingilizce paragraf isaretlenir', () => expect(cevrilmemisMi('An attacker could exploit the vulnerability with a crafted request.', [])).toBe(true))
it('turkce paragraf isaretlenmez', () => expect(cevrilmemisMi('Saldırgan özel hazırlanmış bir istekle zafiyeti istismar edebilir.', [])).toBe(false))
it('kisa paragraf isaretlenmez', () => expect(cevrilmemisMi('Apache HTTP Server 2.4.62', ['Apache HTTP Server 2.4.62'])).toBe(false))
it('ceviri yoksa orijinal gosterilir', () => {
  const s = okumaIcerigi({ govdeTr: '', govdeOrijinal: 'A.\n\nB.' })
  expect(s.tamamenCevrilmedi).toBe(true); expect(s.paragraflar.map(p => p.metin)).toEqual(['A.', 'B.'])
})
// sonZiyaret.test.js
it('yazilani okur', () => { sonZiyaretYaz('2026-10-31T08:00:00Z'); expect(sonZiyaretOku()).toBe('2026-10-31T08:00:00Z') })
it('localStorage hata firlatirsa null doner', () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('x') })
  expect(sonZiyaretOku()).toBeNull()
})
// gundem.test.js
it('created_at azalan ve adet sinirli', () => { /* 3 bölüm × 3 kayıt → 6 kayıt, ilk en yeni */ })
// zaman.test.js
it('24-48 saat dun', () => expect(goreliZaman(new Date(SIMDI - 30 * 3600e3).toISOString(), SIMDI)).toBe('dün'))
```

- [ ] **Step 2: Run to verify fail** — `docker compose exec teknoloji-frontend npm test -- src/utils` → FAIL (modüller yok).
- [ ] **Step 3: Implement** the four modules per Interfaces.
- [ ] **Step 4: Run to verify pass** — the same command → PASS (eski `zaman.test.js` testleri de geçmeli).
- [ ] **Step 5: Commit** — `feat(arayuz): okuma, son ziyaret ve gundem yardimcilari`

### Task 4: Koyu tema temeli ve gezinme

**Files:**
- Create: `frontend/src/styles/tema.css` (token'lar `:root` üzerinde; `.cam-kart`, `.skor-kutusu.kritik|yuksek|orta`, `.rozet.kev|yeni|ur|bilgi`, `.etiket-kucuk`, `.okuma-metni`, `@media (prefers-reduced-motion: reduce)`)
- Modify: `frontend/index.html` (`<html lang="tr" data-bs-theme="dark">`), `frontend/src/main.jsx` (`tema.css` Bootstrap'tan **sonra** import edilir), `frontend/src/App.jsx` (tema düğmesi ve `darkMode` kaldırılır; üst bant spec G3'teki gibi: logo kutusu, "Teknoloji Radar", alt başlık "Tehdit ve Teknoloji İzleme", tam menü adları, aktif sekmede alt çizgi), `frontend/src/App.css` (aydınlık mod ve `dark-mode` kuralları silinir; kalan kurallar token'lara bağlanır)
- Test: `frontend/src/App.test.jsx`

**Interfaces:**
- Produces: CSS sınıfları `cam-kart`, `skor-kutusu {kritik|yuksek|orta}`, `rozet {kev|yeni|ur|bilgi|uyari}`, `etiket-kucuk`, `okuma-metni`. Task 5-8 bunları kullanır. `skorSinifi(skor: number|null) -> 'kritik'|'yuksek'|'orta'|''` `utils/cve.js`'e eklenir (≥9 kritik, ≥7 yüksek, ≥4 orta).

- [ ] **Step 1: Write the failing test** — `App.test.jsx`: `MemoryRouter` ile render edilir. Yedi menü bağlantısı vardır ("Genel Bakış" … "Yapay Zeka"), tema düğmesi yoktur (`queryByLabelText(/Karanlık Mod|Aydınlık Mod/)` null döner). `skorSinifi(9.0)==='kritik'`, `skorSinifi(8.9)==='yuksek'`, `skorSinifi(null)===''`. Sayfa bileşenleri `vi.mock` ile boş bileşenlere çevrilir.
- [ ] **Step 2: Run to verify fail** — `docker compose exec teknoloji-frontend npm test -- src/App.test.jsx` → FAIL.
- [ ] **Step 3: Implement** the files above. Ana sayfa rotası bu taskta geçici olarak eski `HomePage`'i gösterir; Task 6 bunu değiştirir.
- [ ] **Step 4: Run to verify pass** — `npm test` (tüm testler) ve `npm run lint` → PASS.
- [ ] **Step 5: Commit** — `feat(arayuz): koyu tema token'lari ve yeni gezinme`

### Task 5: `OkumaPaneli` ve kayıt eşlemeleri

**Files:**
- Create: `frontend/src/components/okuma/OkumaPaneli.jsx`, `frontend/src/utils/okumaKaydi.js`
- Test: `frontend/src/components/okuma/OkumaPaneli.test.jsx`, `frontend/src/utils/okumaKaydi.test.js`

**Interfaces:**
- Consumes: `okumaIcerigi`, `kevOnekiAyir` (Task 3); `CeviriEtiketi` (mevcut); `skorSinifi`, `cveListeBasligi` (`utils/cve.js`).
- Produces:
  - `OkumaKaydi` nesnesi: `{ id: number, ustBaslik: string|null, baslik: string, skor: number|null, rozetler: {metin: string, tur: 'kev'|'yeni'|'ur'|'bilgi'}[], govdeTr: string, govdeOrijinal: string, kevMeta: {kevEklenme, sonTarih}|null, tarih: string, kaynak: string, link: string, ekAlanlar: {etiket: string, deger: string}[], referanslar: string[], ham: object }`.
  - `cveOkumaKaydi(cve) -> OkumaKaydi`. KEV öneki hem `govdeTr` hem `govdeOrijinal`'dan ayrılır. `kevMeta` önce `cve.kev_added_date`'ten, yoksa önekten gelir. CWE'ler `ur` rozeti olur. `ekAlanlar`: "Etkilenen ürünler". `referanslar`: tamamı, sınır yok.
  - `haberOkumaKaydi(kayit, bolum: 'news'|'kubernetes'|'sre'|'devtools'|'ai') -> OkumaKaydi`. `news` için `tarih = kayit.date`, `govdeTr = turkish_description || turkish_summary`. Diğer bölümlerde `tarih = published_date`. `category`, `version` ve `entry_type` varsa `bilgi` rozeti olur.
  - `<OkumaPaneli kayit={OkumaKaydi|null} onKapat={() => void} />`: react-bootstrap `Offcanvas`, `placement="end"`, `show={!!kayit}`, genişlik `min(860px, 100vw)`. Esc ve kapat düğmesi `onKapat`'ı çağırır. Gövde varsayılan olarak Türkçe gösterilir. "Orijinali göster" düğmesi orijinali Türkçe gövdenin altında ayrı bir blokta açar ve kapatır. `tamamenCevrilmedi` ise üstte "Çevrilmedi: orijinal metin" uyarısı çıkar ve orijinal düğmesi gizlenir. `cevrilmedi` paragraflar `.cevrilmedi` sınıfı ve "Bu paragraf çevrilemedi" notuyla gösterilir. `kevMeta` varsa "KEV'e eklenme: … · Son işlem tarihi: …" satırı çıkar. Gövde tamamen boşsa "İçerik bulunmuyor." yazar. Bağlantılar `guvenliHref` filtresinden geçer ve `target="_blank" rel="noopener noreferrer"` taşır.

- [ ] **Step 1: Write the failing tests**

```jsx
it('varsayilan turkce, orijinal dugmeyle acilir', async () => {
  render(<OkumaPaneli kayit={kayit({ govdeTr: 'Türkçe gövde metni.', govdeOrijinal: 'English body.' })} onKapat={vi.fn()} />)
  expect(screen.getByText('Türkçe gövde metni.')).toBeInTheDocument()
  expect(screen.queryByText('English body.')).toBeNull()
  fireEvent.click(screen.getByRole('button', { name: 'Orijinali göster' }))
  expect(screen.getByText('English body.')).toBeInTheDocument()
})
it('ceviri yoksa orijinal ve uyari gosterilir', () => { /* govdeTr '' → 'Çevrilmedi: orijinal metin' + orijinal metin; 'Orijinali göster' yok */ })
it('ingilizce kalan paragraf isaretlenir', () => { /* 'Bu paragraf çevrilemedi' görünür */ })
it('kev meta satiri', () => { /* kevMeta → 'KEV\'e eklenme: 2026-10-20' metni */ })
it('icerik yoksa bilgi verir', () => { /* iki gövde boş → 'İçerik bulunmuyor.' */ })
it('Esc onKapat cagirir', () => { /* fireEvent.keyDown(document.activeElement, { key: 'Escape' }) → onKapat 1 kez */ })
// okumaKaydi.test.js
it('cve kev onekini govdeden ayirir ve tum referanslari alir', ...)
it('news tarihi date alanindan, govde summary yedegiyle', ...)
```

  `@testing-library/user-event` kurulu değil; `fireEvent` kullan, yeni bağımlılık ekleme.

- [ ] **Step 2: Run to verify fail** — `npm test -- src/components/okuma src/utils/okumaKaydi.test.js` → FAIL.
- [ ] **Step 3: Implement** per Interfaces. Panel CSS'i `tema.css`'te durur (`.okuma-paneli`, `.okuma-metni`, `.cevrilmedi`).
- [ ] **Step 4: Run to verify pass** → PASS.
- [ ] **Step 5: Commit** — `feat(arayuz): ortak okuma paneli`

### Task 6: Genel Bakış sayfası

**Files:**
- Create: `frontend/src/components/genel/GenelBakis.jsx`, `DurumOzeti.jsx`, `CvssGrafigi.jsx`, `OncelikliListe.jsx`, `Gundem.jsx` (hepsi `components/genel/` altında)
- Modify: `frontend/src/services/api.js` (`ozetApi.getOzet(since?: string)` → `api.get('/ozet/', { params: since ? { since } : {} })`), `frontend/src/App.jsx` (`/` → `GenelBakis`; `HomePage` silinir), `frontend/src/components/SaglikSeridi.jsx` (yalnızca görsel: Bootstrap rozetleri yeni `rozet` sınıflarına geçer, metinler ve `data-testid` aynı kalır, mevcut testleri geçmeli)
- Test: `frontend/src/components/genel/GenelBakis.test.jsx`

**Interfaces:**
- Consumes: `ozetApi` (öncelikli liste `priority`'den gelir, `cveApi` çağrılmaz), `newsApi/k8sApi/sreApi/devtoolsApi/aiApi` liste uçları, `gundemBirlestir`, `sonZiyaretOku/Yaz`, `goreliZaman`, `cveOkumaKaydi`, `haberOkumaKaydi`, `OkumaPaneli`, `SaglikSeridi`, `useAraliklaYenile` (5 dk).
- Produces: `GenelBakis` (varsayılan export).
- Davranış:
  - Başlık metinleri: `critical_count > 0` ise "**{n} kritik zafiyet** değerlendirme bekliyor", 0 ise "Son 24 saatte kritik zafiyet yok". Alt cümle: `kev_count > 0` ise "{k} tanesi son 7 günde CISA KEV kataloğuna eklendi, aktif istismar doğrulanmış." `new_since_count` varsa sona "Son ziyaretinizden bu yana {m} yeni kayıt eklendi." eklenir. Kritik 0 olduğunda alt cümle "Son 7 günde {h} yüksek önem dereceli zafiyet kaydedildi." olur.
  - Dört kutu: Kritik (CVSS ≥ 9.0) · Yüksek, son 7 gün · Aktif istismar (KEV) · Kaynaklar "{total − silent}/{total}" (`silent > 0` ise kutu `uyari` renginde ve altında "{silent} kaynak sessiz" yazar).
  - `CvssGrafigi`: `chart` noktaları halkalara yerleşir (≥9 iç, 7–8.9 orta, 4–6.9 dış). Açı `cve_id` karmasından deterministik hesaplanır. `conic-gradient` tarama animasyonu 7 sn sürer. Lejantta "Kritik · Yüksek · Orta" ve `unscored_count > 0` ise "{n} skorsuz" yazar. SVG ya da mutlak konumlu `span` seçimi uygulayıcıya kalmış.
  - `OncelikliListe`: `priority` kayıtları gösterilir. Rozetler: KEV (`kev_added_date` dolu), "Yeni" (`created_at > sonZiyaret`; ilk ziyarette yok), CWE. "Tümünü görüntüle →" `/cve`'ye gider. Satır tıklanınca panel açılır.
  - `Gundem`: beş liste ucu paralel çağrılır, `gundemBirlestir(…, 6)` uygulanır. Bölüm renk noktaları: news `#ff8fae`, kubernetes `#7aa2ff`, devtools `#ffc27a`, sre `#7ee0c3`, ai `#c9a0ff`. Tıklanınca panel açılır.
  - Son ziyaret: `sonZiyaretOku()` ilk yüklemede okunur ve `getOzet(since)`'e verilir. `visibilitychange`→hidden ya da `pagehide` olduğunda `sonZiyaretYaz(en yeni created_at)` çağrılır; değer `priority` ile gündemin en yeni `created_at`'idir.
  - Alt bant: `SaglikSeridi` ve "Son güncelleme {goreliZaman(fetch.last_success_at)} · Sonraki çekim {HH:MM}".
  - Özet ucu hata verirse: "Özet bilgisi alınamadı." yazar; Gündem ve sağlık şeridi yine çalışır.

- [ ] **Step 1: Write the failing tests** (api modülü `vi.mock` ile)

```jsx
it('kritik varsa baslik ve kev cumlesi', async () => { /* critical_count 3, kev_count 2 → '3 kritik zafiyet', '2 tanesi son 7 günde CISA KEV' */ })
it('kritik yoksa sakin cumle', async () => { /* 0 → 'Son 24 saatte kritik zafiyet yok' ve yüksek cümlesi */ })
it('ilk ziyarette son ziyaret cumlesi ve Yeni rozeti yok', async () => { /* localStorage boş → getOzet since'siz çağrılır, 'Son ziyaretinizden' yok, 'Yeni' yok */ })
it('kaynak sessizse kutu uyari gosterir', async () => { /* sources {total:47, silent:2} → '45/47', '2 kaynak sessiz' */ })
it('oncelikli satir paneli acar', async () => { /* satıra tıkla → panelde CVE ID görünür */ })
it('ozet hatasinda gundem calisir', async () => { /* getOzet reject → 'Özet bilgisi alınamadı.' + gündem başlığı görünür */ })
```

- [ ] **Step 2: Run to verify fail** — `npm test -- src/components/genel` → FAIL.
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4: Run to verify pass** — `npm test` (tümü, `SaglikSeridi` dahil) ve `npm run lint` → PASS.
- [ ] **Step 5: Commit** — `feat(arayuz): zafiyet odakli genel bakis sayfasi`

### Task 7: Zafiyetler (CVE) sayfası yeni düzene

**Files:**
- Create: `frontend/src/hooks/useSeciliKayit.js`
- Modify: `frontend/src/components/CVEComponent.jsx`
- Test: `frontend/src/hooks/useSeciliKayit.test.jsx`, `frontend/src/components/CVEComponent.test.jsx`

**Interfaces:**
- Consumes: `OkumaPaneli`, `cveOkumaKaydi`, `skorSinifi`, `cveListeBasligi`, tema sınıfları.
- Produces: `useSeciliKayit(kayitlar: {id:number}[]) -> { secili: object|null, sec: (id:number) => void, kapat: () => void }`. Seçim `useSearchParams` üzerinden `kayit` parametresinde tutulur. `secili` her render'da `kayitlar.find(k => k.id === Number(param))` ile çözülür; bu yüzden yenileme seçimi düşürmez, bilinmeyen id `null` döner. `sec` geçmişe kayıt ekler (geri tuşu paneli kapatır). `kapat` parametreyi siler.
- Sayfa düzeni: üstte kompakt filtre ve eylem çubuğu, altında tam genişlikte liste, detay `OkumaPaneli`'nde. Bugünkü bütün kontroller kalıyor: gün aralığı, kaynak seçimi (açılır menü içinde checkbox'lar), CVSS şiddet filtresi, "X / Y CVE gösteriliyor", Çek, önbelleği temizle, HTML rapor. Liste satırı Genel Bakış'taki öncelikli satırla aynı görünümde. Eski sağ "detay kartı" kaldırılıyor. HTML rapor üretimi ve `kacis` / `guvenliHref` kullanımı aynen kalıyor.

- [ ] **Step 1: Write the failing tests**

```jsx
// useSeciliKayit.test.jsx (MemoryRouter initialEntries=['/cve?kayit=7'])
it('parametredeki id ile cozer', ...)            // secili.id === 7
it('bilinmeyen id null', ...)                      // ?kayit=999 → null
it('liste yenilenince secim korunur', ...)         // rerender ile yeni nesne dizisi, aynı id → secili hâlâ id 7
// CVEComponent.test.jsx (cveApi mock)
it('satira tiklayinca panel acilir ve adres degisir', ...)
it('siddet filtresi sayaci gunceller', ...)        // 'Kritik' seçilince '1 / 3 CVE gösteriliyor'
```

- [ ] **Step 2: Run to verify fail** → FAIL.
- [ ] **Step 3: Implement** `useSeciliKayit` and the CVE page.
- [ ] **Step 4: Run to verify pass** — `npm test` ve `npm run lint` → PASS.
- [ ] **Step 5: Commit** — `feat(arayuz): zafiyetler sayfasi okuma paneline gecti`

### Task 8: Beş haber sayfası yeni düzene

**Files:**
- Create: `frontend/src/components/bolum/BolumSayfasi.jsx` (ortak iskelet: filtre/eylem çubuğu yuvası, liste, `OkumaPaneli`)
- Modify: `NewsComponent.jsx`, `KubernetesComponent.jsx`, `SREComponent.jsx`, `DevToolsComponent.jsx`, `AINewsComponent.jsx`
- Test: `frontend/src/components/bolum/BolumSayfasi.test.jsx`

**Interfaces:**
- Consumes: `useSeciliKayit`, `OkumaPaneli`, `haberOkumaKaydi`, `CeviriEtiketi`.
- Produces: `<BolumSayfasi bolum={'news'|…} baslik={string} kayitlar={object[]} yukleniyor={boolean} cubuk={ReactNode} />`. Satırda Türkçe başlık (yoksa orijinal başlık ve `CeviriEtiketi`), kaynak, göreli zaman (`created_at`) ve bölüme özgü `bilgi` rozetleri gösterilir.
- Her bileşen veri yüklemeyi, `useAraliklaYenile`'yi, çekme/temizleme/rapor eylemlerini ve kendi filtrelerini (Kubernetes kategori, DevTools tür vb.) korur; yalnızca görünümü `BolumSayfasi`'na devreder. Bütün `textAlign: 'justify'` kullanımları kalkar.

- [ ] **Step 1: Write the failing tests** — `BolumSayfasi`: kayıtlar listelenir; tıklanınca panel açılır ve `?kayit=` değişir; çevrilmemiş kayıtta (`needs_translation: true`, `translation_provider: null`, `turkish_title: ''`) orijinal başlık ve "Çevrilmedi: orijinal metin" rozeti görünür; `news` bölümünde tarih `date` alanından okunur.
- [ ] **Step 2: Run to verify fail** → FAIL.
- [ ] **Step 3: Implement** `BolumSayfasi`, then migrate the five components one by one.
- [ ] **Step 4: Run to verify pass** — `npm test`, `npm run lint`, `npm run build` → PASS; `grep -rn "justify" frontend/src` boş.
- [ ] **Step 5: Commit** — `feat(arayuz): bes bolum sayfasi ortak duzene gecti`

### Task 9: Belgeler ve uçtan uca doğrulama

**Files:**
- Modify: `README.md` (Özellikler'de arayüz bölümü, API Endpoints'e `/api/ozet/`, Vitest test sayısı gerçek değerle, "Teknoloji Yığını"nda tema notu), `docs/superpowers/specs/2026-10-31-arayuz-yenileme-design.md` (Durum: uygulandı)

- [ ] **Step 1:** `docker compose exec teknoloji-api python manage.py migrate` → `0016` uygulanır. Ardından `docker compose exec teknoloji-api python manage.py shell -c "from news.models import CVEEntry; print(CVEEntry.objects.exclude(kev_added_date=None).count())"` > 0 olmalı (canlıda KEV kaydı varsa).
- [ ] **Step 2:** `docker compose exec teknoloji-api python manage.py test news --noinput` → tümü PASS.
- [ ] **Step 3:** `docker compose exec teknoloji-frontend npm run lint && docker compose exec teknoloji-frontend npm test && docker compose exec teknoloji-frontend npm run build` → PASS.
- [ ] **Step 4:** Tarayıcıda `http://localhost:3000` adresini aç ve şunları kontrol et:
  - Genel Bakış başlığı ve dört kutu `/api/ozet/` yanıtıyla tutarlı.
  - Öncelikli bir CVE'ye tıklayınca panel açılıyor, "Orijinali göster" çalışıyor, KEV satırı görünüyor.
  - `/news` sayfasında bir habere tıklayınca adres `?kayit=` alıyor, geri tuşu paneli kapatıyor.
  - Çevrilmemiş bir kayıt orijinal metinle ve uyarıyla açılıyor.
  - Konsolda hata ve CSP ihlali yok.
  - Pencere 768 px'e daraltılınca yerleşim tek sütuna iniyor.
- [ ] **Step 5: Commit** — `docs: arayuz yenileme README ve spec durumu`. Ardından dalı push et ve PR aç (kullanıcı onayıyla).
