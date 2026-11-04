# Bolum Listeleri: Filtre, Siralama ve Sayfalama — Uygulama Plani

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alti bolum listesinde donem, siralama, kaynak ve onem/kategori secimlerini sunucuya tasimak, gercek toplami gostermek ve 25'lik numarali sayfalama eklemek.

**Architecture:**
- **Backend:** yeni `news/liste_sorgusu.py` modulu sorgu parametrelerini cozer, queryset'i suzer/siralar/sayfalar ve yanit zarfini kurar. Alti `get_*` liste gorunumu bu modulu cagirir; liste onbellegi okunmaz.
- **Frontend:** yeni `hooks/useListeSorgusu.js` adres parametreleriyle (react-router `useSearchParams`) durum tutar, listeyi ceker ve 5 sn'de bir yeniler. Yeni `components/bolum/SayfaCubugu.jsx` numarali sayfalari cizer. `BolumSayfasi` ve `CVEComponent` bunlari kullanir.

**Tech Stack:** Django 5.2 + DRF, PostgreSQL; React 18, react-router-dom 7, react-bootstrap, Vitest + Testing Library. Yeni bagimlilik yok.

**Spec:** `docs/superpowers/specs/2026-11-05-filtre-siralama-sayfalama-design.md` — once onu oku (§2 hedefler, §7 netlesenler, §8 kararlar).

## Global Constraints

- **Parametreler** (spec §2 G2, §7):
  - `gun` ∈ {1,3,7,14,30} ya da yok (Tumu)
  - `sirala` ∈ {`yeni`,`eski`,`cvss`}; `cvss` yalniz cve
  - `sayfa` >=1
  - `boyut` varsayilan 25, en fazla 100
  - `kaynak` virgullu, `source` ile birebir
  - `onem` ∈ {`kritik`,`yuksek`,`orta`,`dusuk`}, yalniz cve; CVSS >=9, 7–8.9, 4–6.9, 0–3.9; skorsuz yalniz Tumu
  - `kategori` yalniz kubernetes `category`. DevTools'ta bugun ek filtre yok, eklenmez (YAGNI; spec G2'deki "mevcut ek filtre" kurali).
- **Tarih alani:** donem suzmesi ve `yeni`/`eski` siralamasi `created_at` ile. Esitlikte `-created_at`, sonra `-id`; `cvss` siralamasinda skorsuzlar en sonda.
- **Yanit zarfi:** `{success, data, cached, count, toplam, sayfa, sayfa_sayisi, boyut}`.
  - `count` = sayfadaki kayit sayisi; `cached` her zaman False.
  - Gecersiz parametre varsayilana duser (400 yok). Asiri `sayfa` son sayfaya cekilir; bos sonucta `sayfa=1`, `sayfa_sayisi=1`.
- **Parametresiz istek:** gun suzmesi yok, `sirala=yeni`, ilk 25 kayit. Ana sayfanin Gundem karti buna dayaniyor.
- **Dokunulmayacaklar:** `/api/v1/`, `*/stats/`, `/api/ozet/`, cekim (fetch) uclari. Veri modeli degismez (indeks gerekmez; Task 1 olcer).
- **Arayuz metinleri** (birebir):
  - Donem secenekleri: "Son 1 gün", "Son 3 gün", "Son 7 gün" (varsayilan), "Son 14 gün", "Son 30 gün", "Tümü"
  - Sirala: "En yeni", "En eski", "En yüksek CVSS"
  - Sayim: gun secili ise "Son {g} günde {toplam} kayıt · {ilk}–{son} gösteriliyor", Tumu ise "{toplam} kayıt · {ilk}–{son} gösteriliyor". Sayilar `toLocaleString('tr-TR')`.
  - Bos sonuc: mevcut "Bu filtreyle eşleşen kayıt bulunamadı."
  - Sayfa cubugu: "‹ Önceki", "Sonraki ›"
  - Rapor notu: "İlk 500 kayıt (toplam {toplam})"
- **Adres:** varsayilan degerler (gun=7, sirala=yeni, sayfa=1, bos kaynak/onem/kategori) adrese yazilmaz. Filtre ya da siralama degisince `sayfa` silinir (1'e doner).
- **Cek:** `days = gun ? Math.min(gun, 15) : 15`.
- **Testler:**
  - Django: `bash scripts/pg_test.sh test news --noinput` (tek kullanimlik PG+Redis; canli yigina dokunmaz).
  - Vitest: worktree `frontend/`'i `teknoloji-frontend` konteynerinin `/tmp/<dizin>`'ine kopyala (node_modules `/app`'ten), orada `npx vitest run` ve `npx eslint src`. Konteynerin `/app`'ine yazma.
  - ruff: CI gibi (`requirements-dev.txt` ile).
- **Kod ve commit:**
  - Kod ASCII Turkce ad ve yorumlarla; kullaniciya gorunen metin duzgun Turkce.
  - Commit mesaji Turkce, aksansiz; sonu `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  - Dal: `feat/filtre-sayfalama` (worktree `CyberNews/wt-filtre`).
  - Merge yalniz kullanicinin acik onayiyla.

## Review Focus

1. **Sayfa sinirinda kayit kaymasi:** ayni `created_at`'e sahip kayitlar sayfa sinirinda ne tekrar etmeli ne kaybolmali (`-id` ikincil anahtar). → Task 1 `test_ayni_zamanda_kayitlar_sayfa_sinirinda_tekrarlanmaz`.
2. **Otomatik yenileme sayfayi ve acik paneli korur:** sayfa 2'de panel acikken 5 sn yenilemesi sayfayi 1'e atmaz, panel kapanmaz; secili kayit sayfadan dusse bile panel acik kalir. → Task 2 `useSeciliKayit` testi `test_secili_kayit_listeden_dusunce_panel_acik_kalir` ve hook testi `yenileme_sayfayi_degistirmez`.
3. **Adresten gelen bozuk degerler:** `?gun=abc&sayfa=-3&sirala=x` sayfayi kirmaz, varsayilanlarla acilir. → Task 2 hook testi `gecersiz_adres_parametreleri_varsayilana_duser` (+ Task 1 backend karsiligi).
4. **Filtre degisiminde sayfa 1'e doner:** sayfa 5'te kaynak secimi degisince bos sayfa gorunmez. → Task 2 hook testi `filtre_degisince_sayfa_sifirlanir`.
5. **Ana sayfa Gundem karti bozulmaz:** parametresiz cagri en yeni kayitlari dondurmeye devam eder. → Task 1 `test_parametresiz_istek_en_yeni_25` ve Task 4'te GenelBakis testlerinin yesil kalmasi.

---

### Task 1: Backend liste sorgusu

**Files:**
- Create: `news/liste_sorgusu.py`
- Modify: `news/views.py` (`get_news`, `get_cves`, `get_k8s`, `get_sre`, `get_devtools`, `get_ai_news` govdeleri)
- Test: `news/tests/test_liste_sorgusu.py` (yeni); liste uclarinin eski davranisini (100 kayit, `cached` True) sabitleyen mevcut testler guncellenir (`grep -rn "cybersecurity_news\|cve_entries\|'cached'" news/tests`)

**Interfaces:**
- Produces:
  - `liste_yaniti(request, bolum: str) -> rest_framework.response.Response`; `bolum` ∈ {'news','cve','kubernetes','sre','devtools','ai'}
  - `LISTE_BOLUMLERI: Dict[str, Tuple[model, serializer_class]]`
  - Uclar: `GET /api/<bolum>/?gun=&sirala=&sayfa=&boyut=&kaynak=&onem=&kategori=` (Global Constraints'teki zarf)

- [ ] **Step 1: Failing testler** (`news/tests/test_liste_sorgusu.py`, `TestCase` + `APIClient`, kayitlar `created_at`'i `update()` ile ayarlanarak):

```python
def test_parametresiz_istek_en_yeni_25(self):         # 30 kayit -> count 25, toplam 30, sayfa 1, sayfa_sayisi 2, data[0] en yeni created_at
def test_gun_suzmesi_created_at_ile(self):            # 2 sa once ve 3 gun once -> gun=1 toplam 1
def test_tumu_gun_yoksa_hepsi(self):
def test_sirala_eski(self):
def test_sirala_cvss_skorsuzlar_sonda(self):          # cve: 9.8, None, 5.0 -> [9.8, 5.0, None]
def test_cvss_siralamasi_cve_disinda_yok_sayilir(self):  # /api/news/?sirala=cvss -> yeni sirasi
def test_onem_kritik_cvss_araligi(self):              # 9.0 dahil, 8.9 haric; skorsuz haric
def test_kaynak_birebir_ve_bilinmeyen_bos(self):      # kaynak=NVD -> yalniz NVD; kaynak=Yok -> toplam 0
def test_kategori_kubernetes(self):
def test_sayfa_ve_boyut(self):                        # 60 kayit, boyut=25, sayfa=3 -> count 10, sayfa_sayisi 3
def test_boyut_ust_siniri_100(self):                  # boyut=500 -> boyut 100
def test_gecersiz_parametreler_varsayilana_duser(self):  # gun=abc&sayfa=-3&sirala=x&boyut=0 -> 200, gun yok, sayfa 1, boyut 25
def test_asiri_sayfa_son_sayfaya_cekilir(self):       # 30 kayit, sayfa=99 -> sayfa 2
def test_bos_sonuc(self):                             # toplam 0, sayfa 1, sayfa_sayisi 1, data []
def test_ayni_zamanda_kayitlar_sayfa_sinirinda_tekrarlanmaz(self):  # 30 kayit ayni created_at; sayfa 1+2 id kumesi = 30 benzersiz
def test_alti_bolumun_hepsi_calisir(self):            # her bolum ucu 200 ve zarf anahtarlari
```

- [ ] **Step 2:** Kos: `bash scripts/pg_test.sh test news.tests.test_liste_sorgusu --noinput` → FAIL.
- [ ] **Step 3: Uygula** `news/liste_sorgusu.py` ve gorunumlerdeki cache okuma + `[:100]` yerine `return liste_yaniti(request, '<bolum>')`.
  - Liste onbellegi okunmaz.
  - `cache_utils.cache_yenile` ve temizleme uclarindaki `cache.delete` cagrilari kalir (zararsiz; baska yerler cagiriyor).
  - `count()` + dilimleme ya da Django `Paginator` uygulayicinin secimi.
- [ ] **Step 4:** Eski testleri guncelle; tum `news` suiti → PASS. ruff temiz.
- [ ] **Step 5: Olcum** (canli DB'ye yalniz okuma; canli kod degismez):
  - Worktree kodunu `teknoloji-api` konteynerinin `/tmp/<dizin>`'ine kopyala.
  - `python manage.py shell` icinde `/api/cve/?gun=30&sirala=cvss&onem=kritik&sayfa=3` sorgusunun suresini olc.
  - 50 ms ustuyse `created_at` indeksi icin dur ve controller'a bildir.
  - Sonucu commit mesajina yaz.
- [ ] **Step 6: Commit:** `feat(api): bolum listelerinde sunucu tarafi filtre, siralama ve sayfalama`

### Task 2: Frontend ortak parcalar

**Files:**
- Create: `frontend/src/hooks/useListeSorgusu.js`, `frontend/src/hooks/useListeSorgusu.test.jsx`
- Create: `frontend/src/components/bolum/SayfaCubugu.jsx`, `frontend/src/components/bolum/SayfaCubugu.test.jsx`
- Modify: `frontend/src/hooks/useSeciliKayit.js` (+ test), `frontend/src/services/api.js`, `frontend/src/styles/tema.css`

**Interfaces:**
- Consumes: Task 1 uc ve zarf.
- Produces:
  - `api.js`: `newsApi.getNews(params)`, `cveApi.getCVEs(params)`, `k8sApi.getK8s(params)`, `sreApi.getSRE(params)`, `devtoolsApi.getDevTools(params)`, `aiApi.getAINews(params)`. `params` yoksa bugunku parametresiz istek.
  - `useListeSorgusu({ getir, ekAnahtarlar = [] }) -> { kayitlar, toplam, sayfa, sayfaSayisi, boyut, yukleniyor, hata, sorgu, degistir, sayfayaGit, yenile }`
    - `sorgu` = `{ gun: number|null, sirala: string, kaynak: string[], ...ekAnahtarlar degerleri }`, adresten okunur.
    - `degistir(kismi)` adresi gunceller ve `sayfa`'yi siler.
    - `sayfayaGit(n)` yalniz `sayfa`'yi yazar.
    - Liste 5 sn'de bir `useAraliklaYenile` ile sessizce yenilenir (yukleniyor degismez).
    - `getir(params)` API cagrisidir; `params` = `{gun?, sirala?, sayfa?, boyut: 25, kaynak?: 'A,B', <ek>?}`, varsayilanlar dahil bos olmayanlar gonderilir, `gun` her zaman gonderilir.
  - `SayfaCubugu({ sayfa, sayfaSayisi, onSayfa })`: tek sayfada `null`; ilk, son, gecerli ±2, araliklar "…"; `aria-label="Sayfalar"`, gecerli sayfa `aria-current="page"`.
  - `useSeciliKayit(kayitlar)`: secili kayit listeden duserse son bilinen nesneyle acik kalir. Imza degismez; `kapat()` ile kapanir.

- [ ] **Step 1: Failing testler:**
  - `useListeSorgusu.test.jsx` (MemoryRouter + sahte `getir`):
    - `adres_parametrelerini_okur`
    - `varsayilanlar_adrese_yazilmaz`
    - `filtre_degisince_sayfa_sifirlanir`
    - `sayfayaGit_yalniz_sayfayi_yazar`
    - `gecersiz_adres_parametreleri_varsayilana_duser` (`?gun=abc&sayfa=-3&sirala=x` -> gun 7, sayfa 1, yeni)
    - `yenileme_sayfayi_degistirmez`
    - `getire_dogru_parametreler_gider` (gun=7 her zaman, kaynak virgullu)
  - `SayfaCubugu.test.jsx`:
    - `tek_sayfada_gizlenir`
    - `uzun_listede_uc_nokta` (sayfa 6/20 -> 1 … 4 5 6 7 8 … 20)
    - `onceki_ilk_sayfada_pasif`
    - `tiklama_onSayfa_cagirir`
  - `useSeciliKayit.test.jsx`: `secili_kayit_listeden_dusunce_panel_acik_kalir`.
- [ ] **Step 2:** Vitest → FAIL. **Step 3:** Uygula; sayfa cubugu stili mevcut `cubuk-dugme` gorunumunde, gecerli sayfa vurgu renginde. **Step 4:** Vitest + eslint → PASS.
- [ ] **Step 5: Commit:** `feat(arayuz): liste sorgusu hook'u ve sayfa cubugu`

### Task 3: Bes bolumu (BolumSayfasi kullananlar) gecir

**Files:**
- Modify:
  - `frontend/src/components/bolum/BolumSayfasi.jsx` (BolumCubugu'ya Sirala; sayim satiri; SayfaCubugu; `filtre` prop'u kalkar)
  - `NewsComponent.jsx`, `KubernetesComponent.jsx`, `SREComponent.jsx`, `DevToolsComponent.jsx`, `AINewsComponent.jsx`
  - ilgili testler: `bolum/BolumSayfasi.test.jsx`, `bolum/BolumSayfalari.test.jsx`

**Interfaces:**
- Consumes: Task 2 `useListeSorgusu`, `SayfaCubugu`, api `params`.
- Produces: `BolumCubugu` yeni prop'lari:
  - `sirala`, `siralaSecenekleri: Array<{deger, etiket}>`, `onSiralaDegis`
  - `gun: number|null`, `gunSecenekleri` (Global Constraints'teki altili; Tumu = null)
  - `BolumSayfasi({ ..., toplam, sayfa, sayfaSayisi, boyut, gun, onSayfa })`

- [ ] **Step 1: Failing testler** (mevcut test dosyalarinda, api mock'lariyla):
  - `donem_secimi_listeyi_sunucuda_suzer`: Son 1 gun secilince `getNews` `{gun: 1, sayfa yok}` ile cagrilir.
  - `sayim_gercek_toplami_gosterir`: "Son 7 günde 1.234 kayıt · 26–50 gösteriliyor".
  - `kaynak_secimi_listeyi_suzer_ve_ceker`: kaynak kaldirilinca `kaynak=` parametresi ve Cek `sources`'u ayni kume.
  - `k8s_kategori_sunucuya_gider`
  - `cek_en_fazla_15_gun`: Tumu secili iken fetch `days: 15`; Son 30 gun iken `days: 15`; Son 7 gun iken `days: 7`.
  - `rapor_gecerli_filtreyle_en_fazla_500`: `toplam: 730` -> 5 cagri (`boyut: 100, sayfa: 1..5`), rapor HTML'inde "İlk 500 kayıt (toplam 730)".
- [ ] **Step 2:** Vitest → FAIL.
- [ ] **Step 3:** Uygula.
  - Bes bilesen veri yuklemesini `useListeSorgusu`'na birakir; kendi `useAraliklaYenile` / `loadX` kodu silinir.
  - Kaynak secimi ve kategori adres durumuna baglanir.
  - Istatistik (`getStats`) bugunku gibi kalir.
- [ ] **Step 4:** Vitest + eslint → PASS. **Step 5: Commit:** `feat(arayuz): bes bolumde sunucu tarafi filtre ve sayfalama`

### Task 4: Zafiyetler sayfasi ve ana sayfa baglantisi

**Files:**
- Modify: `frontend/src/components/CVEComponent.jsx` (+ `CVEComponent.test.jsx`), `frontend/src/components/genel/OncelikliListe.jsx` (+ `GenelBakis.test.jsx`)

**Interfaces:**
- Consumes: Task 2/3 parcalari (`BolumCubugu`'nun Sirala/Donem prop'lari `CVEComponent`'in kendi cubugunda ayni bicimde).

- [ ] **Step 1: Failing testler:**
  - `onem_sunucuya_gider`: Kritik dugmesi -> `getCVEs({onem: 'kritik', ...})`; sayim "Son 7 günde 1.559 kayıt · 1–25 gösteriliyor".
  - `cvss_siralamasi_yalniz_zafiyetlerde`: Sirala secenekleri "En yeni", "En eski", "En yüksek CVSS".
  - `adresten_acilis`: `/cve?sirala=cvss&sayfa=2` -> `getCVEs({sirala: 'cvss', sayfa: 2, gun: 7, ...})`.
  - `tumunu_goruntule_cvss_siralamasina_gider`: link `href` = `/cve?sirala=cvss`.
  - Mevcut GenelBakis/Gundem testleri degismeden yesil.
- [ ] **Step 2:** Vitest → FAIL. **Step 3:** Uygula (CVE'nin istemci tarafi `filteredCVEs` suzmesi kalkar; rapor Task 3 kuraliyla). **Step 4:** Vitest + eslint → PASS.
- [ ] **Step 5: Commit:** `feat(arayuz): zafiyetlerde onem ve CVSS siralamasi sunucuda`

### Task 5: Belgeler, son kontrol, PR

- [ ] README:
  - "API Endpoints" bolumune liste parametreleri ve zarf.
  - Frontend ozelliklerinde filtre, siralama ve sayfalama.
  - Test sayilari (Django ve Vitest; `grep -n "795\|186" README.md`).
- [ ] Spec "Durum" satiri: "uygulandi (dal feat/filtre-sayfalama)".
- [ ] Tum Django suiti, Vitest, eslint, ruff yesil.
- [ ] Push, PR (govdede olcum sonucu ve karar listesi). CI bekle. **Merge icin kullanici onayi.**
- [ ] Merge sonrasi:
  - Canli checkout `git pull --ff-only`, `teknoloji-api` yeniden baslat; frontend HMR ile gelir.
  - Tarayicida dogrula: `/cve` Son 1 gun + Kritik + En yuksek CVSS, sayfa 2'ye gec, geri tusu; `/news` kaynak sec, rapor; ana sayfa Gundem karti dolu.
