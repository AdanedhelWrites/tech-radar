"""
SRE (Site Reliability Engineering) Scraper Module
5 kaynak:
  - SRE Weekly (RSS) — sreweekly.com/feed/
  - InfoQ SRE (HTML) — infoq.com/sre/news/
  - PagerDuty Engineering Blog (RSS) — pagerduty.com/eng/feed/
  - Google Cloud Blog (RSS + SRE filtre) — cloud.google.com/blog/rss
  - DZone DevOps (RSS) — feeds.dzone.com/devops
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
from typing import List, Dict, Optional
import time
from email.utils import parsedate_to_datetime

from news.translation_utils import translate_text, translate_long_text
from news.base_scraper import BaseRSSScraper


class SREScraper(BaseRSSScraper):
    """SRE Scraper temel sinifi"""

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })


class SREWeeklyScraper(SREScraper):
    """SRE Weekly RSS scraper"""

    FEED_URL = "https://sreweekly.com/feed/"

    def fetch_entries(self, days: int = 30) -> List[Dict]:
        """SRE Weekly RSS'ten bireysel makaleleri ceker"""
        print(f"[SRE Weekly] Son {days} gunun haberleri cekiliyor (RSS)...")

        entries = []
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            response = self.session.get(self.FEED_URL, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'xml')
            items = soup.find_all('item')
            print(f"  [SRE Weekly] RSS'te {len(items)} sayi bulundu")

            for item in items:
                try:
                    # Sayi tarihi
                    pub_date_str = item.find('pubDate')
                    if pub_date_str:
                        issue_date = self._parse_rss_date(pub_date_str.get_text(strip=True))
                    else:
                        continue

                    if issue_date and issue_date.replace(tzinfo=None) < cutoff_date:
                        continue

                    # Her sayinin icindeki content:encoded alaninda bireysel makaleler var
                    content_tag = item.find('content:encoded') or item.find('encoded')
                    if not content_tag:
                        continue

                    content_html = content_tag.get_text()
                    content_soup = BeautifulSoup(content_html, 'html.parser')

                    # Bireysel makaleleri cek
                    article_entries = content_soup.select('div.sreweekly-entry')
                    date_str = issue_date.strftime('%Y-%m-%d') if issue_date else datetime.now().strftime('%Y-%m-%d')

                    for entry in article_entries:
                        try:
                            # Sponsorlu icerikleri atla
                            if entry.select_one('.sreweekly-sponsor-message'):
                                continue
                            # email_only sinifini atla
                            if 'email_only' in entry.get('class', []):
                                continue

                            title_tag = entry.select_one('div.sreweekly-title a')
                            if not title_tag:
                                continue

                            title = title_tag.get_text(strip=True)
                            link = title_tag.get('href', '')

                            if not title or not link:
                                continue

                            # Aciklama
                            desc_div = entry.select_one('div.sreweekly-description')
                            description = ''
                            if desc_div:
                                for small in desc_div.find_all('small'):
                                    small.decompose()
                                description = desc_div.get_text(separator=' ', strip=True)

                            if not description:
                                description = title

                            entries.append({
                                'title': title,
                                'description': description[:4000],
                                'link': link,
                                'date': date_str,
                                'source': 'SRE Weekly',
                })
                        except Exception as e:
                            print(f"  [SRE Weekly] Makale isleme hatasi: {e}")
                            continue

                except Exception as e:
                    print(f"  [SRE Weekly] Sayi isleme hatasi: {e}")
                    continue

        except Exception as e:
            print(f"[SRE Weekly] RSS hatasi: {e}")

        print(f"[SRE Weekly] {len(entries)} haber bulundu")
        return entries


# ============================================================
# 2. InfoQ SRE — HTML Scraping
# ============================================================
class InfoQSREScraper(SREScraper):
    """InfoQ SRE News (infoq.com/sre/news) scraper"""

    BASE_URL = "https://www.infoq.com/sre/news/"

    def fetch_entries(self, days: int = 30) -> List[Dict]:
        """InfoQ SRE haberlerini ceker"""
        print(f"[InfoQ SRE] Son {days} gunun haberleri cekiliyor...")

        entries = []
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            response = self.session.get(self.BASE_URL, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            cards = soup.select('li[data-id][data-path]')
            print(f"  [InfoQ SRE] {len(cards)} kart bulundu")

            for card in cards:
                try:
                    title_tag = card.select_one('h3.card__title a')
                    if not title_tag:
                        continue

                    title = title_tag.get_text(strip=True)
                    href = title_tag.get('href', '')
                    link = f"https://www.infoq.com{href}" if href.startswith('/') else href

                    if not title or not link:
                        continue

                    desc_tag = card.select_one('p.card__excerpt')
                    description = desc_tag.get_text(strip=True) if desc_tag else title

                    date_str = ''
                    date_span = card.select_one('span.card__date span')
                    if date_span:
                        date_str = date_span.get_text(strip=True)

                    pub_date = self._parse_rss_date(date_str) if date_str else datetime.now()
                    if pub_date is None:
                        pub_date = datetime.now()

                    if pub_date.replace(tzinfo=None) < cutoff_date:
                        continue

                    entries.append({
                        'title': title,
                        'description': description[:4000],
                        'link': link,
                        'date': pub_date.strftime('%Y-%m-%d'),
                        'source': 'InfoQ SRE',
                })
                except Exception as e:
                    print(f"  [InfoQ SRE] Kart isleme hatasi: {e}")
                    continue

        except Exception as e:
            print(f"[InfoQ SRE] Hata: {e}")

        print(f"[InfoQ SRE] {len(entries)} haber bulundu")
        return entries


# ============================================================
# 3. PagerDuty Engineering Blog — RSS Feed
# ============================================================
class PagerDutyEngScraper(SREScraper):
    """PagerDuty Engineering Blog RSS scraper"""

    FEED_URL = "https://www.pagerduty.com/eng/feed/"

    def fetch_entries(self, days: int = 30) -> List[Dict]:
        """PagerDuty Engineering Blog'dan haberleri ceker"""
        print(f"[PagerDuty Eng] Son {days} gunun haberleri cekiliyor (RSS)...")

        entries = []
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            response = self.session.get(self.FEED_URL, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'xml')
            items = soup.find_all('item')
            print(f"  [PagerDuty Eng] RSS'te {len(items)} makale bulundu")

            for item in items:
                try:
                    title = item.find('title')
                    title_text = title.get_text(strip=True) if title else ''
                    if not title_text:
                        continue

                    # "by Author" kismini basliktan cikar
                    title_text = re.sub(r'\s+by\s+[\w\s]+$', '', title_text)

                    link_tag = item.find('link')
                    link = link_tag.get_text(strip=True) if link_tag else ''
                    if not link:
                        continue

                    pub_date_tag = item.find('pubDate')
                    pub_date = self._parse_rss_date(pub_date_tag.get_text(strip=True)) if pub_date_tag else None

                    if pub_date and pub_date.replace(tzinfo=None) < cutoff_date:
                        continue

                    # Aciklama: description veya content:encoded
                    desc_tag = item.find('description')
                    description = ''
                    if desc_tag:
                        description = self._html_to_text(desc_tag.get_text())

                    if not description:
                        content_tag = item.find('content:encoded') or item.find('encoded')
                        if content_tag:
                            description = self._html_to_text(content_tag.get_text())

                    if not description:
                        description = title_text

                    date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')

                    entries.append({
                        'title': title_text,
                        'description': description[:4000],
                        'link': link,
                        'date': date_str,
                        'source': 'PagerDuty Eng',
                })
                except Exception as e:
                    print(f"  [PagerDuty Eng] Makale isleme hatasi: {e}")
                    continue

        except Exception as e:
            print(f"[PagerDuty Eng] RSS hatasi: {e}")

        print(f"[PagerDuty Eng] {len(entries)} haber bulundu")
        return entries


# ============================================================
# 4. Google Cloud Blog — RSS Feed (SRE filtreli)
# ============================================================
class GoogleCloudSREScraper(SREScraper):
    """Google Cloud Blog RSS scraper — SRE/DevOps/reliability konulari"""

    FEED_URL = "https://cloudblog.withgoogle.com/rss/"

    # SRE ile ilgili anahtar kelimeler (dar filtreleme — cok genel sonuclardan kacinmak icin)
    SRE_KEYWORDS = [
        'sre', 'site reliability', 'incident response', 'incident management',
        'postmortem', 'post-mortem', 'on-call', 'oncall',
        'observability', 'slo', 'sla', 'sli',
        'error budget', 'toil', 'devops', 'outage',
        'chaos engineering', 'load balancing', 'auto-scaling', 'autoscaling',
        'reliability engineering', 'service mesh',
    ]

    def fetch_entries(self, days: int = 30) -> List[Dict]:
        """Google Cloud Blog'dan SRE ile ilgili haberleri ceker"""
        print(f"[Google Cloud SRE] Son {days} gunun haberleri cekiliyor (RSS)...")

        entries = []
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            response = self.session.get(self.FEED_URL, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'xml')
            items = soup.find_all('item')
            print(f"  [Google Cloud SRE] RSS'te {len(items)} toplam makale")

            sre_count = 0
            for item in items:
                try:
                    title = item.find('title')
                    title_text = title.get_text(strip=True) if title else ''
                    if not title_text:
                        continue

                    link_tag = item.find('link')
                    link = link_tag.get_text(strip=True) if link_tag else ''

                    # Kategori etiketleri
                    categories = [cat.get_text(strip=True).lower() for cat in item.find_all('category')]

                    # Aciklama
                    desc_tag = item.find('description')
                    description = self._html_to_text(desc_tag.get_text()) if desc_tag else ''

                    # SRE ile ilgili mi kontrol et
                    combined_text = (title_text + ' ' + description + ' ' + ' '.join(categories)).lower()
                    is_sre = any(kw in combined_text for kw in self.SRE_KEYWORDS)

                    if not is_sre:
                        continue

                    pub_date_tag = item.find('pubDate')
                    pub_date = self._parse_rss_date(pub_date_tag.get_text(strip=True)) if pub_date_tag else None

                    if pub_date and pub_date.replace(tzinfo=None) < cutoff_date:
                        continue

                    date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')

                    entries.append({
                        'title': title_text,
                        'description': description[:4000] if description else title_text,
                        'link': link,
                        'date': date_str,
                        'source': 'Google Cloud SRE',
                    })
                    sre_count += 1

                except Exception as e:
                    print(f"  [Google Cloud SRE] Makale isleme hatasi: {e}")
                    continue

            print(f"  [Google Cloud SRE] {sre_count} SRE makalesi filtrelendi")

        except Exception as e:
            print(f"[Google Cloud SRE] RSS hatasi: {e}")

        print(f"[Google Cloud SRE] {len(entries)} haber bulundu")
        return entries


# ============================================================
# 5. DZone DevOps — RSS Feed
# ============================================================
class DZoneDevOpsScraper(SREScraper):
    """DZone DevOps RSS scraper"""

    FEED_URL = "https://feeds.dzone.com/devops"

    def fetch_entries(self, days: int = 30) -> List[Dict]:
        """DZone DevOps RSS'ten haberleri ceker"""
        print(f"[DZone DevOps] Son {days} gunun haberleri cekiliyor (RSS)...")

        entries = []
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            response = self.session.get(self.FEED_URL, timeout=20)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'xml')
            items = soup.find_all('item')
            print(f"  [DZone DevOps] RSS'te {len(items)} makale bulundu")

            for item in items:
                try:
                    title = item.find('title')
                    title_text = title.get_text(strip=True) if title else ''
                    if not title_text:
                        continue

                    link_tag = item.find('link')
                    link = link_tag.get_text(strip=True) if link_tag else ''
                    if not link:
                        continue

                    pub_date_tag = item.find('pubDate')
                    pub_date = self._parse_rss_date(pub_date_tag.get_text(strip=True)) if pub_date_tag else None

                    if pub_date and pub_date.replace(tzinfo=None) < cutoff_date:
                        continue

                    desc_tag = item.find('description')
                    description = self._html_to_text(desc_tag.get_text()) if desc_tag else title_text

                    date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')

                    entries.append({
                        'title': title_text,
                        'description': description[:4000],
                        'link': link,
                        'date': date_str,
                        'source': 'DZone DevOps',
                })
                except Exception as e:
                    print(f"  [DZone DevOps] Makale isleme hatasi: {e}")
                    continue

        except Exception as e:
            print(f"[DZone DevOps] RSS hatasi: {e}")

        print(f"[DZone DevOps] {len(entries)} haber bulundu")
        return entries


# ============================================================
# Multi SRE Scraper — Tum kaynaklari birlestiren sinif
# ============================================================
class MultiSREScraper(SREScraper):
    """Tum SRE kaynaklarini birlestiren scraper"""

    def __init__(self):
        super().__init__()
        self.sre_weekly = SREWeeklyScraper()
        self.infoq_sre = InfoQSREScraper()
        self.pagerduty_eng = PagerDutyEngScraper()
        self.google_cloud_sre = GoogleCloudSREScraper()
        self.dzone_devops = DZoneDevOpsScraper()

    def fetch_all(self, days: int = 30, selected_sources: list = None, max_total: int = 30) -> List[Dict]:
        """Tum kaynaklardan SRE haberi ceker"""
        all_entries = []

        print("=" * 80)
        print(f"TUM SRE KAYNAKLARINDAN HABER CEKILIYOR ({days} gun, maks {max_total})")
        print("=" * 80)

        sources = {
            'SRE Weekly': self.sre_weekly,
            'InfoQ SRE': self.infoq_sre,
            'PagerDuty Eng': self.pagerduty_eng,
            'Google Cloud SRE': self.google_cloud_sre,
            'DZone DevOps': self.dzone_devops,
        }

        if selected_sources:
            sources = {k: v for k, v in sources.items() if k in selected_sources}

        per_source_limit = max(5, max_total // max(len(sources), 1))

        for source_name, scraper in sources.items():
            try:
                entries = scraper.fetch_entries(days=days)
                if len(entries) > per_source_limit:
                    entries = entries[:per_source_limit]
                    print(f"  -> {source_name}: {per_source_limit} haber (sinirlandirildi)")
                else:
                    print(f"  -> {source_name}: {len(entries)} haber")
                all_entries.extend(entries)
            except Exception as e:
                print(f"  -> {source_name}: HATA - {e}")

        # Tarihe gore sirala
        all_entries.sort(key=lambda x: x['date'], reverse=True)

        # Toplam sinir
        if len(all_entries) > max_total:
            all_entries = all_entries[:max_total]

        # Duplicate link kontrolu
        seen_links = set()
        unique = []
        for entry in all_entries:
            if entry['link'] not in seen_links:
                seen_links.add(entry['link'])
                unique.append(entry)

        print("=" * 80)
        print(f"TOPLAM {len(unique)} SRE HABERI CEKILDI")
        print("=" * 80)

        return unique

    def process_entries(self, entries: List[Dict]) -> List[Dict]:
        """SRE haberlerini Turkceye cevirir"""
        total = len(entries)

        print(f"\nSRE haberleri cevriliyor ({total} adet)...")

        for i, entry in enumerate(entries, 1):
            try:
                if i % 10 == 0:
                    print(f"  Cevriliyor: {i}/{total}")

                # Baslik cevirisi
                try:
                    translated_title = translate_text(entry['title'])
                except Exception:
                    translated_title = entry['title']

                # Icerik cevirisi
                translated_desc = translate_long_text(entry['description'])

                yield {
                    'original_title': entry['title'],
                    'turkish_title': translated_title,
                    'original_description': entry['description'],
                    'turkish_description': translated_desc,
                    'link': entry['link'],
                    'published_date': entry['date'],
                    'source': entry['source'],
                }
            except Exception as e:
                print(f"  SRE haber isleme hatasi: {e}")
                yield {
                    'original_title': entry['title'],
                    'turkish_title': entry['title'],
                    'original_description': entry['description'],
                    'turkish_description': entry['description'],
                    'link': entry['link'],
                    'published_date': entry['date'],
                    'source': entry['source'],
                }
        


if __name__ == "__main__":
    scraper = MultiSREScraper()
    entries = scraper.fetch_all(days=30)
    print(f"\nToplam {len(entries)} SRE haberi cekildi")
    for e in entries[:10]:
        print(f"  [{e['source']}] {e['title'][:60]}...")
