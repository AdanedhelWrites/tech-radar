from typing import List, Dict
from news.base_scraper import BaseRSSScraper
from news.translation_utils import translate_text, translate_long_text
import logging

log = logging.getLogger(__name__)

class AINewsScraper(BaseRSSScraper):
    def __init__(self, feed_url, source_name):
        super().__init__()
        self.feed_url = feed_url
        self.source_name = source_name

    def fetch_entries(self, days: int = 30) -> List[Dict]:
        return self.fetch_standard_rss_entries(self.feed_url, self.source_name, days)

class MultiAINewsScraper:
    def __init__(self):
        self.scrapers = {
            'Hugging Face': AINewsScraper('https://huggingface.co/blog/feed.xml', 'Hugging Face'),
            'MIT Tech Review AI': AINewsScraper('https://www.technologyreview.com/topic/artificial-intelligence/feed', 'MIT Tech Review AI'),
            'MarkTechPost': AINewsScraper('https://www.marktechpost.com/feed/', 'MarkTechPost'),
            'AWS ML Blog': AINewsScraper('https://aws.amazon.com/blogs/machine-learning/feed/', 'AWS ML Blog'),
            'TechCrunch AI': AINewsScraper('https://techcrunch.com/category/artificial-intelligence/feed/', 'TechCrunch AI'),
            'Google DeepMind': AINewsScraper('https://deepmind.google/blog/rss.xml', 'Google DeepMind'),
            'KDnuggets': AINewsScraper('https://www.kdnuggets.com/feed', 'KDnuggets'),
            'OpenAI Blog': AINewsScraper('https://openai.com/blog/rss.xml', 'OpenAI Blog'),
        }

    def fetch_all(self, days=30, selected_sources=None):
        all_entries = []
        sources_to_use = selected_sources if selected_sources else self.scrapers.keys()
        
        log.info('='*80)
        log.info(f'TUM AI HABER KAYNAKLARINDAN VERI CEKILIYOR ({days} gun)')
        log.info('='*80)
        
        for name in sources_to_use:
            if name in self.scrapers:
                entries = self.scrapers[name].fetch_entries(days=days)
                all_entries.extend(entries)
                log.info(f'  -> {name}: {len(entries)} haber')
                
        log.info('='*80)
        log.info(f'TOPLAM {len(all_entries)} AI HABERI CEKILDI')
        log.info('='*80)
        return sorted(all_entries, key=lambda x: x.get('date', ''), reverse=True)

    def process_entries(self, entries: List[Dict]):
        log.info(f'\nAI Haberleri isleniyor ve Turkceye cevriliyor ({len(entries)} adet)...')
        for i, entry in enumerate(entries):
            log.info(f'[{i+1}/{len(entries)}] {entry["source"]} - {entry["title"]}')
            try:
                turkish_title = translate_text(entry['title'])
                turkish_desc = translate_long_text(entry['description'])
                
                yield {
                    'source': entry['source'],
                    'original_title': entry['title'],
                    'turkish_title': turkish_title,
                    'original_description': entry['description'],
                    'turkish_description': turkish_desc,
                    'link': entry['link'],
                    'date': entry['date']
                }
            except Exception as e:
                log.warning(f'Ceviri hatasi ({entry["source"]}) : {e}')
                yield {
                    'source': entry['source'],
                    'original_title': entry['title'],
                    'turkish_title': entry['title'],
                    'original_description': entry['description'],
                    'turkish_description': entry['description'],
                    'link': entry['link'],
                    'date': entry['date']
                }
