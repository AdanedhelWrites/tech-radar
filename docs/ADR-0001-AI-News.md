# ADR 0001: Addition of AI News & Benchmark Component

## Status
Accepted — 2026-09-11 (uygulandı; benchmark kısmı kapsamdan çıkarılıp [ADR-0002](ADR-0002-AI-Benchmark.md)'ye taşındı)

## Context
Kullanıcı, CyberNews (Teknoloji Radar) uygulamasına yapay zeka (AI) dünyasındaki gelişmeleri ve benchmark skorlarını (model karşılaştırmaları vb.) takip edebileceği yeni bir bileşen (component) eklenmesini talep etmiştir. Uygulamanın halihazırda kullandığı yapıyla (otomatik crawling, rate limitlere uygunluk, teknik terimlerin çeviri koruması ve karanlık mod arayüzü) tamamen entegre çalışması gerekmektedir.

## Decision
Uygulamaya yeni bir modül olarak `AI News` entegrasyonu yapılacaktır:
1. **Veri Modeli:** Django ORM üzerinden hali hazırdaki SREEntry/NewsArticle modellerine simetrik bir API model yaratılacak (`AINewsEntry`).
2. **Veri Kaynağı (Scraping):** Seçilen AI haberleri ve benchmark sayfaları için `news/ai_scraper.py` altında bağımsız scraper/ayrıştırıcı görevleri oluşturulacaktır. Bunlar mevcut Celery Worker asenkron mimarisine dahil edilecektir.
3. **Korunan Terimler:** Yapay zekaya özel ifadelerin (LLM, Parameter, Transformer, RAG, vs.) Türkçe'ye hatalı çevrilmemesi için `translation_utils.py` dosyasına "AI Context" terim korumaları maskelenecektir.
4. **Kullanıcı Arayüzü:** Frontend React uygulaması içerisinde `/ai` URL'inde gösterilecek `AINewsComponent` adında yeni bir sayfa (Component) inşa edilecek.

## Değişiklik (2026-09-11)
- **Kapsam:** Benchmark/leaderboard skorları bu ADR'nin kapsamından çıkarıldı. Veri modeli, kaynak ve arayüz açısından haberden farklı olduğu için ayrı karar olarak [ADR-0002](ADR-0002-AI-Benchmark.md)'de ele alınacak. Bu ADR yalnızca AI haberlerini kapsar.
- **Terim koruması:** "Parameter" bilinçli olarak korunmadı; Türkçe karşılığı "parametre" doğru ve yaygın olduğu için çeviriye bırakıldı. "Transformer" (tekil) listeye eklendi.

## Uygulama Notları
| Karar | Uygulama |
|-------|----------|
| 1. Veri modeli | `news/models.py` → `AINewsEntry`, migration `0006_ainewsentry` |
| 2. Scraping + Celery | `news/ai_scraper.py` (8 RSS kaynağı, ortak `news/base_scraper.py::BaseRSSScraper`), `news/tasks.py::fetch_ai_news_task`, Celery Beat ile 6 saatte bir (`skip_existing=True`) |
| 3. Korunan terimler | `news/translation_utils.py` → "AI / Yapay Zeka" bloğu (LLM, AGI, RAG, LoRA, Transformer(s), MMLU, HumanEval, ...) |
| 4. Arayüz | `frontend/src/components/AINewsComponent.jsx`, `/ai` route'u, navbar ve ana sayfa kartı |

**Kaynaklar:** Hugging Face, MIT Tech Review AI, MarkTechPost, AWS ML Blog, TechCrunch AI, Google DeepMind, KDnuggets, OpenAI Blog. İlk sürümdeki `artificialintelligence-news.com` RSS'i 403 döndüğü için (hiç kayıt üretmedi) 2026-09-11'de MIT Technology Review AI ile değiştirildi.

## Consequences
- **Positive:** Kullanıcı; siber güvenlik, SRE ve altyapı haberleriyle birlikte hızla gelişen AI ekosistemini tek bir panelden okuyabilecek. (Benchmark takibi ADR-0002'ye bağlı.)
- **Negative (Risks):** Sisteme kazandırılacak ilave dış kaynaklar, Google Translate API kullanım hacmini (rate-limiting) artıracaktır — periyodik çekimlerde yalnızca yeni kayıtların çevrilmesi (`skip_existing`) bu riski azaltır. Benchmark sitelerine ilişkin dinamik içerik (Selenium/Playwright) riski ADR-0002'ye devredildi.
