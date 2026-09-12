# ADR 0002: AI Benchmark / Leaderboard Component

## Status
Proposed (Ertelendi — 2026-09-11)

## Context
ADR-0001 kapsaminda AI haberleri ile birlikte model benchmark skorlarinin (leaderboard, model karsilastirmalari) da gosterilmesi planlanmisti. AI News bileseni tamamlandi, ancak benchmark kismi uygulanmadi. 2026-09-11 tarihli durum kontrolunde benchmark, ADR-0001 kapsamindan cikarilarak bu ayri karara tasindi.

Benchmark verisi haber verisinden yapisal olarak farklidir:
- Kayit birimi "makale" degil "model + metrik + skor"dur; `AINewsEntry` modeline sigmaz, ayri bir veri modeli gerekir.
- Leaderboard sayfalarinin bircogu JS ile render edilir; mevcut `Requests/BeautifulSoup` yaklasimi yetmeyebilir (ADR-0001'de risk olarak belirtilen Selenium/Playwright ihtiyaci).
- Skorlar cevrilmez, sayisaldir; ceviri hattina (Google Translate) yuk bindirmez.

## Decision
Henuz verilmedi. Karar verilirken degerlendirilecek sorular:
1. **Veri kaynagi:** Resmi API veya indirilebilir dataset sunan leaderboard'lar mi (tercih edilen), yoksa HTML/JS scraping mi?
2. **Veri modeli:** Ornegin `AIBenchmarkEntry(model_name, benchmark, score, source, measured_at)` ve gecmis skorlarin saklanip saklanmayacagi.
3. **Arayuz:** `/ai` sayfasina sekme olarak mi eklenecek, yoksa ayri `/ai/benchmarks` sayfasi mi?
4. **Guncelleme sikligi:** Celery Beat takvimine (su an bolumler 6 saatte bir) eklenip eklenmeyecegi.

## Consequences
- **Positive:** AI haber bileseni benchmark bagimliligi olmadan tamamlanmis sayilir; ADR-0001 "Accepted" olarak kapatilabilir.
- **Negative:** Kullanici benchmark skorlarini bu karar uygulanana kadar uygulama icinden takip edemez.
