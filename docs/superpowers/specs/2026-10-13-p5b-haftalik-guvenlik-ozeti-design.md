# P5-b: Haftalık Güvenlik Özeti — Tasarım

> Tarih: 2026-10-13. Kaynak: `docs/GUVENLIK-PLANI.md` §4 P5 ("Haftalık güvenlik özeti: araç × severity
> tablosuyla GitHub Issue açan bir workflow"). Durum: onaylandı (Issue birikimi A seçildi).

## 1. Amaç

GUVENLIK-PLANI §2'deki ~10 dakikalık elle haftalık rutini (Actions → Dependabot → Code scanning → ZAP)
tek bir GitHub Issue'ya indirmek. Issue her hafta yeniden açılır; GitHub bildirimi olarak gelir.

**Başarı ölçütü:** Cuma sabahı açılan Issue, Security ve Actions sekmelerine girmeden şu soruları
yanıtlar: son 7 günde kırmızı koşu var mı, hangi araçta hangi severity'de kaç açık uyarı var, bu hafta ne
açıldı / ne kapandı, Dependabot'ta açık uyarı var mı.

**Başlangıç verisi (2026-10-13):** açık code scanning 15 (hepsi OWASP ZAP: 4 medium, 11 low),
Dependabot 0, secret scanning 0.

## 2. Bileşenler

| Dosya | Sorumluluk |
|---|---|
| `scripts/guvenlik_ozeti.py` | Yalnız standart kütüphane, ağ yok. Dört JSON girdisinden Issue gövdesini (Markdown) dosyaya yazar, başlığı stdout'a basar. `--simdi` ile zaman sabitlenir (test). `zap_sarif.py` ile aynı kalıp. |
| `news/tests/test_guvenlik_ozeti.py` | `SimpleTestCase`; betik `importlib` ile dosya yolundan yüklenir (`test_zap_sarif.py` kalıbı). CI Backend kapısından geçer. |
| `.github/workflows/guvenlik-ozeti.yml` | Cuma 06:00 UTC (`0 6 * * 5`) + `workflow_dispatch`. Veriyi `gh api` ile çeker, betiği çalıştırır, Issue açar, öncekini kapatır. |
| `docs/GUVENLIK-PLANI.md` | §1 tabloya satır, §2 rutini Issue'ya yönlendirir, P5-b işaretlenir, §5 geçmiş. |

Cuma seçildi: haftalık taramaların sonuncusu zizmor (Perşembe 04:05 UTC); Cuma 06:00 UTC'de hepsi bitmiştir.

## 3. Betik arayüzü

```
python3 scripts/guvenlik_ozeti.py \
  --acik code_acik.json --kapanan code_kapanan.json \
  --dependabot dependabot.json --kosular kosular.json \
  --repo OWNER/NAME --cikti ozet.md [--simdi 2026-10-16T06:00:00Z]
```

- Stdout: tek satır başlık, `Haftalık güvenlik özeti — 2026-W42 (2026-10-16)` (ISO hafta, `simdi`'nin UTC tarihi).
- Girdiler `gh api --paginate --slurp` çıktısıdır: sayfa listesi. Betik iç içe listeleri düzleştirir;
  koşular sayfa başına `{"workflow_runs": [...]}` nesnesidir. Düz liste / tek nesne de kabul edilir.
- `dependabot.json` okunamadıysa workflow `{"okunamadi": true}` yazar.
- Pencere: `simdi - 7 gün <= zaman <= simdi` (alt sınır dahil).

## 4. Issue gövdesi

1. **Durum satırı:** `⚠️ Dikkat` — son 7 günde kırmızı koşu, açık critical/high code scanning uyarısı, bu hafta
   yeni açılmış uyarı ya da Dependabot critical/high varsa; aksi halde `✅ Temiz`. Nedenler madde madde yazılır.
   Dependabot okunamaması durumu değiştirmez (yalnız not).
2. **Kırmızı koşular (son 7 gün):** workflow adı | olay | dal | tarih | bağlantı. Yoksa "Kırmızı koşu yok."
3. **Code scanning — açık uyarılar:** araç × severity tablosu. Sabit sütunlar
   `critical, high, medium, low, error, warning, note, Toplam`; araçlar ada göre sıralı; son satır `Toplam`.
   Severity: `rule.security_severity_level` varsa o, yoksa `rule.severity`; `none`/boş → `note`.
4. **Bu hafta:** yeni açılan (hâlâ açık, `created_at` pencerede), düzeltilen (`state=fixed`, `fixed_at`
   pencerede) ve dismiss edilen (`state=dismissed`, `dismissed_at` pencerede) uyarıların toplamları ve
   araç bazında `Araç | Yeni | Düzeltilen | Dismiss` tablosu; ayrıntı için Security → Code scanning bağlantısı.
   **Uyarı ayrıntısı (kural, dosya yolu, uyarı numarası/bağlantısı) yazılmaz** — bkz. §4a.
5. **Dependabot — açık uyarılar:** `critical/high/medium/low` sayıları (`security_advisory.severity`);
   okunamadıysa "okunamadı (token izni)".
6. **Ne yapmalı:** kırmızı koşu varsa önce onu çöz; critical/high → GUVENLIK-PLANI P4 listesi; ZAP bulguları
   Security'de dismiss ya da düzeltme. Plan bağlantısı.

Hücre kaçışı (güvenilmeyen metin: fork PR'ının dal adı ve workflow adı saldırgan seçimidir): satır sonu →
boşluk; ``\ ` * _ { } [ ] ( ) < > # + ! ~ |`` ters bölüyle kaçırılır (HTML/bağlantı olarak işlenmez);
`@` → `&#64;` (kullanıcı anma olmasın).

### 4a. Güvenlik düzeltmesi (2026-10-13, uygulama sırasında)

Otomatik güvenlik incelemesi iki bulgu verdi; repo **herkese açık** (`visibility=public`):

1. **Bilgi ifşası:** İlk tasarımdaki "yeni uyarılar" tablosu kural, dosya yolu ve uyarı bağlantısını herkese
   açık Issue'ya yazıyordu. Security → Code scanning'i yalnız yazma yetkisi olanlar görür; düzeltilmemiş bir
   CodeQL bulgusunun yeri böylece yayınlanmış olurdu. Karar: Issue yalnız toplu sayı taşır. Adım özeti ve
   artefakt da herkese açık repoda herkese görünür, bu yüzden ayrıntı başka bir yere de taşınmaz.
2. **Markdown enjeksiyonu:** Yalnız `|` ve `@` kaçırılıyordu; yukarıdaki kaçış kümesine genişletildi.

Kırmızı koşular tablosu kalır: Actions koşuları herkese açık repoda zaten herkese görünür.

Haftalık değişim için durum saklanmaz: `created_at` / `fixed_at` / `dismissed_at` ile hesaplanır, önceki
Issue gövdesi ayrıştırılmaz.

## 5. Workflow

- `permissions: {}` üst düzeyde; iş düzeyinde `contents: read`, `issues: write`, `security-events: read`,
  `actions: read`.
- Adımlar: harden-runner (audit) → checkout (`persist-credentials: false`) → veri çekme → betik →
  `gh label create guvenlik-ozeti --force` → `gh issue create --label guvenlik-ozeti` → önceki açık
  `guvenlik-ozeti` Issue'larını "Yerine #N açıldı." yorumuyla kapat → `GITHUB_STEP_SUMMARY`'e bağlantı.
- Action'lar mevcut workflow'lardaki SHA'lara sabit; `${{ }}` ifadeleri `run` içine gömülmez, `env` ile geçer
  (zizmor template-injection). `concurrency` ile tek koşu. `timeout-minutes: 10`.
- Python: runner'daki `python3` (yalnız stdlib; `setup-python` gerekmez).

## 6. Hata davranışı

Mevcut "rapor modu" anlamı: hat yalnız rapor üretilemezse kırmızı.

| Durum | Davranış |
|---|---|
| Code scanning ya da koşular okunamadı | Adım başarısız → hat kırmızı (rapor eksik olurdu) |
| Dependabot API 403/404 | Hat yeşil; Issue'da "okunamadı (token izni)" |
| Issue açılamadı | Hat kırmızı |
| Önceki Issue kapatılamadı | Hat kırmızı (bir sonraki hafta yığılma olmasın; elle bakılır) |

`GITHUB_TOKEN`'ın Dependabot uyarılarını okuyup okuyamadığı ilk `workflow_dispatch` koşusunda doğrulanır
ve sonuç GUVENLIK-PLANI'ya yazılır.

## 7. Test

TDD, `news/tests/test_guvenlik_ozeti.py`:
boş veri (✅, sıfır tablo); araç × severity sayımı ve `security_severity_level` önceliği, `none` → note;
pencere sınırı (tam 7 gün dahil, 7 gün + 1 sn hariç); düzeltilen/dismiss sayımı ve araç bazında değişim tablosu; uyarı ayrıntısının yayınlanmaması;
Dependabot okunamadı (durum etkilenmez) ve critical (⚠️); kırmızı koşu satırı ve ⚠️; hücre kaçışı;
ISO hafta başlığı; sayfalı girdi düzleştirme; CLI (`main`) dosya yazar, başlığı basar.

Yayına alma: PR + 5 zorunlu check → merge → `gh workflow run guvenlik-ozeti.yml` → açılan Issue elle kontrol.

## 8. Kapsam dışı

Scorecard skor geçmişi, secret scanning (`GITHUB_TOKEN` ile okunamaz; gitleaks code scanning'de zaten var),
e-posta/Slack bildirimi, PAT.
