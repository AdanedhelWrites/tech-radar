"""
Guncel Haberler - Multi-Source Scraper
5 farkli kaynaktan siber guvenlik haberi ceker ve tam icerik olarak cevirir.
"""

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timedelta
import re
import time
from abc import ABC, abstractmethod

from news.translation_utils import translate_text, translate_long_text
from news.base_scraper import BaseRSSScraper


class NewsSource(BaseRSSScraper):
    """Haber kaynagi icin abstract base class"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
    @abstractmethod
    def get_name(self):
        pass

    @abstractmethod
    def fetch_news(self, days=7):
        pass

    @abstractmethod
    def get_base_url(self):
        pass

    def fetch_full_article(self, url):
        """Haber sayfasina gidip baslik + tam makale icerigini ceker"""
        result = {'title': '', 'content': ''}
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Baslik: og:title > h1 > title
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                result['title'] = og_title['content'].strip()
            else:
                h1 = soup.find('h1')
                if h1:
                    result['title'] = h1.get_text(strip=True)

            # Gereksiz tag'leri kaldir (ama article body'yi bozmayacak sekilde)
            for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header',
                                       'aside', 'iframe', 'form', 'noscript']):
                tag.decompose()

            # ONCE article body'yi bul
            article_body = (
                soup.find('div', class_=re.compile(r'article-body|article_body|articlebody', re.I)) or
                soup.find('div', class_=re.compile(r'post-body|post_body|postbody', re.I)) or
                soup.find('div', class_=re.compile(r'post-content|post_content|postcontent', re.I)) or
                soup.find('div', class_=re.compile(r'entry-content|entry_content|entrycontent', re.I)) or
                soup.find('div', class_=re.compile(r'story-content|story_content|storycontent', re.I)) or
                soup.find('div', class_=re.compile(r'article-text|article_text|articletext', re.I)) or
                soup.find('div', class_=re.compile(r'blog-content|blog_content|blogcontent', re.I)) or
                soup.find('div', class_=re.compile(r'content-body|content_body|contentbody', re.I)) or
                soup.find('article') or
                soup.find('main')
            )

            # SONRA article body icindeki gereksiz alt bloklari temizle
            if article_body:
                for tag in article_body.find_all(['div', 'section', 'aside'], class_=re.compile(
                    r'related|sidebar|comment|social|share|newsletter|signup|ad-|promo|widget|footer|nav',
                    re.I)):
                    tag.decompose()

            if article_body:
                paragraphs = article_body.find_all('p')
                text_parts = []
                for p in paragraphs:
                    txt = p.get_text(strip=True)
                    # Kisa ve gereksiz paragraflari atla
                    if len(txt) > 20 and not re.match(
                        r'^(Share|Tweet|Email|Print|Related|Also read|Read more|'
                        r'Subscribe|Sign up|Follow us|Advertisement|Recommended|'
                        r'Found this article|Update \d|Editor)',
                        txt, re.I):
                        text_parts.append(txt)
                result['content'] = '\n\n'.join(text_parts)

            time.sleep(0.3)
        except Exception as e:
            print(f"  [fetch_full_article] Hata ({url[:60]}): {e}")

        return result


class TheHackerNewsSource(NewsSource):
    """The Hacker News kaynagi"""

    def get_name(self):
        return "The Hacker News"

    def get_base_url(self):
        return "https://thehackernews.com"

    def fetch_news(self, days=7):
        print(f"[{self.get_name()}] Haberler cekiliyor...")

        try:
            response = self.session.get(self.get_base_url(), timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"[{self.get_name()}] Hata: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []

        story_divs = soup.find_all('div', class_='body-post')
        cutoff_date = datetime.now() - timedelta(days=days)

        print(f"[{self.get_name()}] {len(story_divs)} story div bulundu")

        for story in story_divs:
            try:
                title_tag = story.find('h2', class_='home-title')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)

                link_tag = story.find('a', class_='story-link')
                link = link_tag.get('href', '') if link_tag else ""

                date_tag = story.find('span', class_='h-datetime')
                date_str = ""
                if date_tag:
                    date_str = date_tag.get_text(strip=True)
                    pub_date = self._parse_date(date_str)
                else:
                    pub_date = datetime.now()

                if pub_date >= cutoff_date:
                    # Habere gidip tam icerik cek
                    content = ''
                    if link:
                        print(f"  [THN] Tam icerik cekiliyor: {title[:50]}...")
                        article_data = self.fetch_full_article(link)
                        if article_data['title'] and len(article_data['title']) > len(title):
                            title = article_data['title']
                        content = article_data['content']

                    # Fallback: listing sayfasindaki kisa aciklama
                    if not content:
                        desc_tag = story.find('div', class_='home-desc')
                        content = desc_tag.get_text(strip=True) if desc_tag else title

                    articles.append({
                        'title': title,
                        'description': content,
                        'link': link,
                        'date': pub_date.strftime('%Y-%m-%d'),
                        'original_date': date_str,
                        'source': self.get_name()
                })
            except Exception as e:
                print(f"[{self.get_name()}] Haber islenirken hata: {e}")
                continue

        print(f"[{self.get_name()}] {len(articles)} haber bulundu.")
        return articles

    def _parse_date(self, date_str):
        try:
            return datetime.strptime(date_str, '%B %d, %Y')
        except:
            try:
                return datetime.strptime(date_str, '%b %d, %Y')
            except:
                return datetime.now()


class BleepingComputerSource(NewsSource):
    """Bleeping Computer kaynagi"""

    def get_name(self):
        return "Bleeping Computer"

    def get_base_url(self):
        return "https://www.bleepingcomputer.com"

    def fetch_news(self, days=7):
        print(f"[{self.get_name()}] Haberler cekiliyor...")

        try:
            response = self.session.get(
                f"{self.get_base_url()}/news/security/",
                timeout=30
            )
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"[{self.get_name()}] Hata: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []
        cutoff_date = datetime.now() - timedelta(days=days)

        # Gercek yapi: h4 > a (parent = div.bc_latest_news_text)
        news_divs = soup.find_all('div', class_='bc_latest_news_text')
        print(f"[{self.get_name()}] {len(news_divs)} news div bulundu")

        for news_div in news_divs:
            try:
                h4 = news_div.find('h4')
                if not h4:
                    continue

                link_tag = h4.find('a')
                if not link_tag:
                    continue

                title = link_tag.get_text(strip=True)
                link = link_tag.get('href', '')

                if not title or not link:
                    continue

                # Sponsorlu/reklam linkleri atla
                if 'bleepingcomputer.com' not in link:
                    continue

                # Tarih: <ul> icindeki text'ten parse et
                date_str = ""
                pub_date = datetime.now()
                ul_tag = news_div.find('ul')
                if ul_tag:
                    date_text = ul_tag.get_text(strip=True)
                    # "AuthorNameFebruary 24, 202606:40 AM0" formatindan tarihi cikar
                    date_match = re.search(
                        r'((?:January|February|March|April|May|June|July|August|'
                        r'September|October|November|December)\s+\d{1,2},\s+\d{4})',
                        date_text
                    )
                    if date_match:
                        date_str = date_match.group(1)
                        pub_date = self._parse_date(date_str)

                if pub_date < cutoff_date:
                    continue

                # Kisa aciklama (listing sayfasindan)
                p_tag = news_div.find('p')
                short_desc = p_tag.get_text(strip=True) if p_tag else ""

                # Habere gidip tam icerik cek
                content = ''
                print(f"  [BC] Tam icerik cekiliyor: {title[:50]}...")
                article_data = self.fetch_full_article(link)
                if article_data['title'] and len(article_data['title']) > len(title):
                    title = article_data['title']
                content = article_data['content']

                if not content:
                    content = short_desc or title

                articles.append({
                    'title': title,
                    'description': content,
                    'link': link,
                    'date': pub_date.strftime('%Y-%m-%d'),
                    'original_date': date_str,
                    'source': self.get_name()
                })
            except Exception as e:
                print(f"[{self.get_name()}] Haber islenirken hata: {e}")
                continue

        print(f"[{self.get_name()}] {len(articles)} haber bulundu.")
        return articles

    def _parse_date(self, date_str):
        try:
            return datetime.strptime(date_str, '%B %d, %Y')
        except:
            try:
                return datetime.strptime(date_str, '%b %d, %Y')
            except:
                return datetime.now()


class SecurityWeekSource(NewsSource):
    """SecurityWeek kaynagi"""

    def get_name(self):
        return "SecurityWeek"

    def get_base_url(self):
        return "https://www.securityweek.com"

    def fetch_news(self, days=7):
        print(f"[{self.get_name()}] Haberler cekiliyor...")

        try:
            response = self.session.get(self.get_base_url(), timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"[{self.get_name()}] Hata: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []

        story_divs = soup.find_all('div', class_='views-row') or soup.find_all('article')
        cutoff_date = datetime.now() - timedelta(days=days)

        print(f"[{self.get_name()}] {len(story_divs)} story bulundu")

        for story in story_divs:
            try:
                title_tag = story.find('h2', class_='node-title') or story.find('h3') or story.find('h2')
                if not title_tag:
                    continue

                link_tag = title_tag.find('a')
                title = link_tag.get_text(strip=True) if link_tag else title_tag.get_text(strip=True)
                link = link_tag.get('href', '') if link_tag else ""
                if link and not link.startswith('http'):
                    link = self.get_base_url() + link

                date_tag = story.find('span', class_='date-display-single') or story.find('time')
                date_str = ""
                pub_date = datetime.now()

                if date_tag:
                    date_str = date_tag.get_text(strip=True)
                    pub_date = self._parse_date(date_str)

                if pub_date >= cutoff_date:
                    # Habere gidip tam icerik cek
                    content = ''
                    if link:
                        print(f"  [SW] Tam icerik cekiliyor: {title[:50]}...")
                        article_data = self.fetch_full_article(link)
                        if article_data['title'] and len(article_data['title']) > len(title):
                            title = article_data['title']
                        content = article_data['content']

                    if not content:
                        desc_tag = (story.find('div', class_='field-name-body') or
                                   story.find('p'))
                        content = desc_tag.get_text(strip=True) if desc_tag else title

                    articles.append({
                        'title': title,
                        'description': content,
                        'link': link,
                        'date': pub_date.strftime('%Y-%m-%d'),
                        'original_date': date_str,
                        'source': self.get_name()
                })
            except Exception as e:
                print(f"[{self.get_name()}] Haber islenirken hata: {e}")
                continue

        print(f"[{self.get_name()}] {len(articles)} haber bulundu.")
        return articles

    def _parse_date(self, date_str):
        try:
            return datetime.strptime(date_str, '%B %d, %Y')
        except:
            try:
                return datetime.strptime(date_str, '%b %d, %Y')
            except:
                return datetime.now()


class DarkReadingSource(NewsSource):
    """Dark Reading kaynagi - RSS tabanli (site 403 donuyor)"""

    def get_name(self):
        return "Dark Reading"

    def get_base_url(self):
        return "https://www.darkreading.com"

    def fetch_news(self, days=7):
        print(f"[{self.get_name()}] RSS'den haberler cekiliyor...")

        try:
            response = self.session.get(
                f"{self.get_base_url()}/rss.xml",
                timeout=30
            )
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"[{self.get_name()}] RSS Hatasi: {e}")
            return []

        # html.parser ile XML parse (lxml gerekmiyor)
        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []
        cutoff_date = datetime.now() - timedelta(days=days)

        items = soup.find_all('item')
        print(f"[{self.get_name()}] {len(items)} RSS item bulundu")

        for item in items:
            try:
                # Title (CDATA icinde olabilir)
                title_tag = item.find('title')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                # CDATA temizligi
                title = re.sub(r'<!\[CDATA\[|\]\]>', '', title).strip()

                # Link - RSS'te <link> tag'inin text'i bos, ardindan URL gelir
                link = ''
                link_tag = item.find('link')
                if link_tag:
                    link = link_tag.get_text(strip=True)
                    if not link and link_tag.next_sibling:
                        link = str(link_tag.next_sibling).strip()

                if not link or not title:
                    continue

                # Date
                date_str = ""
                pub_date = datetime.now()
                pubdate_tag = item.find('pubdate')
                if pubdate_tag:
                    date_str = pubdate_tag.get_text(strip=True)
                    pub_date = self._parse_rss_date(date_str)

                if pub_date < cutoff_date:
                    continue

                # Description (RSS'ten kisa aciklama)
                desc_tag = item.find('description')
                short_desc = ""
                if desc_tag:
                    desc_text = desc_tag.get_text(strip=True)
                    short_desc = re.sub(r'<[^>]+>', '', desc_text).strip()

                # Tam icerik icin makaleye git
                content = ''
                if link:
                    print(f"  [DR] Tam icerik cekiliyor: {title[:50]}...")
                    article_data = self.fetch_full_article(link)
                    if article_data['title'] and len(article_data['title']) > len(title):
                        title = article_data['title']
                    content = article_data['content']

                if not content:
                    content = short_desc or title

                articles.append({
                    'title': title,
                    'description': content,
                    'link': link,
                    'date': pub_date.strftime('%Y-%m-%d'),
                    'original_date': date_str,
                    'source': self.get_name()
                })
            except Exception as e:
                print(f"[{self.get_name()}] Haber islenirken hata: {e}")
                continue

        print(f"[{self.get_name()}] {len(articles)} haber bulundu.")
        return articles

    
    def get_name(self):
        return "Krebs on Security"

    def get_base_url(self):
        return "https://krebsonsecurity.com"

    def fetch_news(self, days=7):
        print(f"[{self.get_name()}] Haberler cekiliyor...")

        try:
            response = self.session.get(self.get_base_url(), timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"[{self.get_name()}] Hata: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []

        story_articles = soup.find_all('article')
        cutoff_date = datetime.now() - timedelta(days=days)

        print(f"[{self.get_name()}] {len(story_articles)} article bulundu")

        for article in story_articles:
            try:
                title_tag = article.find('h2', class_='entry-title')
                if not title_tag:
                    continue

                link_tag = title_tag.find('a')
                title = link_tag.get_text(strip=True) if link_tag else title_tag.get_text(strip=True)
                link = link_tag.get('href', '') if link_tag else ""

                date_tag = article.find('span', class_='date') or article.find('time', class_='entry-date')
                date_str = ""
                pub_date = datetime.now()

                if date_tag:
                    date_str = date_tag.get_text(strip=True)
                    pub_date = self._parse_date(date_str)

                if pub_date >= cutoff_date:
                    # Habere gidip tam icerik cek
                    content = ''
                    if link:
                        print(f"  [Krebs] Tam icerik cekiliyor: {title[:50]}...")
                        article_data = self.fetch_full_article(link)
                        if article_data['title'] and len(article_data['title']) > len(title):
                            title = article_data['title']
                        content = article_data['content']

                    if not content:
                        desc_tag = article.find('div', class_='entry-content')
                        if desc_tag:
                            desc_p = desc_tag.find('p')
                            content = desc_p.get_text(strip=True) if desc_p else ""
                        if not content:
                            content = title

                    articles.append({
                        'title': title,
                        'description': content,
                        'link': link,
                        'date': pub_date.strftime('%Y-%m-%d'),
                        'original_date': date_str,
                        'source': self.get_name()
                })
            except Exception as e:
                print(f"[{self.get_name()}] Haber islenirken hata: {e}")
                continue

        print(f"[{self.get_name()}] {len(articles)} haber bulundu.")
        return articles

    def _parse_date(self, date_str):
        try:
            return datetime.strptime(date_str, '%B %d, %Y')
        except:
            try:
                return datetime.strptime(date_str, '%b %d, %Y')
            except:
                return datetime.now()



class KrebsOnSecuritySource(NewsSource):
    SOURCE_NAME = 'Krebs on Security'
    FEED_URL = 'https://krebsonsecurity.com/feed/'
    
    def fetch_entries(self, days=30):
        return self.fetch_standard_rss_entries(self.FEED_URL, self.SOURCE_NAME, days)

class MultiSourceScraper(BaseRSSScraper):
    """Coklu kaynak haber cekici"""

    def __init__(self):
        self.sources = [
            TheHackerNewsSource(),
            BleepingComputerSource(),
            SecurityWeekSource(),
            DarkReadingSource(),
            KrebsOnSecuritySource()
        ]

    def fetch_all_news(self, days=7, selected_sources=None, max_total=30):
        """Tum kaynaklardan haber ceker (max_total ile sinirli)"""
        print(f"\n{'='*80}")
        print(f"TUM KAYNAKLARDAN HABER CEKILIYOR ({days} gun, maks {max_total})")
        print(f"{'='*80}\n")

        all_articles = []
        sources_to_fetch = self.sources

        if selected_sources:
            sources_to_fetch = [s for s in self.sources if s.get_name() in selected_sources]

        # Her kaynaga esit pay ver
        per_source_limit = max(5, max_total // max(len(sources_to_fetch), 1))

        for source in sources_to_fetch:
            try:
                articles = source.fetch_news(days=days)
                # Kaynak basina limit uygula
                if len(articles) > per_source_limit:
                    articles = articles[:per_source_limit]
                    print(f"  -> {source.get_name()}: {per_source_limit} haber (sinirlandirildi)\n")
                else:
                    print(f"  -> {source.get_name()}: {len(articles)} haber\n")
                all_articles.extend(articles)
            except Exception as e:
                print(f"[{source.get_name()}] Kaynak hatasi: {e}")
                continue

        # Tarihe gore sirala (en yeni en ustte)
        all_articles.sort(key=lambda x: x['date'], reverse=True)

        # Toplam sinir
        if len(all_articles) > max_total:
            all_articles = all_articles[:max_total]

        print(f"{'='*80}")
        print(f"TOPLAM {len(all_articles)} HABER CEKILDI")
        print(f"{'='*80}\n")

        return all_articles

    def process_news(self, articles):
        """Haberleri tam olarak Turkceye cevirir"""

        total = len(articles)
        print(f"\n{'='*60}")
        print(f"CEVIRI BASLADI: {total} haber cevriliyor...")
        print(f"{'='*60}\n")

        for i, article in enumerate(articles):
            print(f"Cevriliyor: {i+1}/{total} - {article['title'][:50]}...")

            try:
                # Baslik cevirisi
                try:
                    translated_title = translate_text(article['title'])
                    time.sleep(0.2)
                except Exception:
                    translated_title = article['title']

                # Tam icerik cevirisi (chunk'larla)
                translated_desc = translate_long_text(
                    article['description']
                )

                yield {
                    'original_title': article['title'],
                    'turkish_title': translated_title,
                    'turkish_description': translated_desc,
                    'turkish_summary': '',
                    'link': article['link'],
                    'date': article['date'],
                    'original_date': article['original_date'],
                    'source': article['source']
                }
            except Exception as e:
                print(f"Haber islenirken hata: {e}")
                yield {
                    'original_title': article['title'],
                    'turkish_title': article['title'],
                    'turkish_description': article['description'],
                    'turkish_summary': '',
                    'link': article['link'],
                    'date': article['date'],
                    'original_date': article['original_date'],
                    'source': article['source']
                }
        print(f"\n{'='*60}")
        print(f"{'='*60}\n")

        

    def save_to_json(self, articles, filename=None):
        """Haberleri JSON olarak kaydeder"""
        if not filename:
            filename = f"cybersecurity_news_multi_{datetime.now().strftime('%Y%m%d_%H%M')}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)

        print(f"Haberler {filename} dosyasina kaydedildi.")
        return filename


if __name__ == "__main__":
    scraper = MultiSourceScraper()
    articles = scraper.fetch_all_news(days=7)

    if articles:
        processed = scraper.process_news(articles)
        scraper.save_to_json(processed)
    else:
        print("\nHaber bulunamadi!")
