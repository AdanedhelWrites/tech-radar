"""
Guncel Haberler - Multi-Source Scraper
12 farkli kaynaktan siber guvenlik haberi ceker ve tam icerik olarak cevirir.

  HTML: The Hacker News, Bleeping Computer, Krebs on Security
  RSS : SecurityWeek (+tam makale), Dark Reading, The Record (+tam makale), CyberScoop,
        Help Net Security (+tam makale), Infosecurity Magazine, SANS ISC, The Register,
        Security Affairs
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
import logging

log = logging.getLogger(__name__)


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
            log.warning(f"  [fetch_full_article] Hata ({url[:60]}): {e}")

        return result


class TheHackerNewsSource(NewsSource):
    """The Hacker News kaynagi"""

    def get_name(self):
        return "The Hacker News"

    def get_base_url(self):
        return "https://thehackernews.com"

    def fetch_news(self, days=7):
        log.info(f"[{self.get_name()}] Haberler cekiliyor...")

        try:
            response = self.session.get(self.get_base_url(), timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            log.warning(f"[{self.get_name()}] Hata: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []

        story_divs = soup.find_all('div', class_='body-post')
        cutoff_date = datetime.now() - timedelta(days=days)

        log.info(f"[{self.get_name()}] {len(story_divs)} story div bulundu")

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
                        log.info(f"  [THN] Tam icerik cekiliyor: {title[:50]}...")
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
                log.warning(f"[{self.get_name()}] Haber islenirken hata: {e}")
                continue

        log.info(f"[{self.get_name()}] {len(articles)} haber bulundu.")
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

    # Cloudflare, Chrome/120 User-Agent'ini python'un TLS parmak iziyle eslesmedigi icin
    # 403 ile reddediyor (2026-10-08 olcumu: hem /feed/ hem /news/security/; kaynak hic
    # kayit uretmemisti). Firefox UA ve kisa UA geciyor.
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0'
    # Makale sayfalari arka arkaya cekilince ~15. istekten sonra 429 donuyor (2026-10-08);
    # tur basina en fazla bu kadar makale, istekler arasi bekleme ile.
    MAX_ITEMS = 10
    ARTICLE_DELAY = 1.0

    def __init__(self):
        super().__init__()
        self.session.headers['User-Agent'] = self.USER_AGENT

    def get_name(self):
        return "Bleeping Computer"

    def get_base_url(self):
        return "https://www.bleepingcomputer.com"

    def fetch_news(self, days=7):
        log.info(f"[{self.get_name()}] Haberler cekiliyor...")

        try:
            response = self.session.get(
                f"{self.get_base_url()}/news/security/",
                timeout=30
            )
            response.raise_for_status()
        except requests.RequestException as e:
            log.warning(f"[{self.get_name()}] Hata: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []
        cutoff_date = datetime.now() - timedelta(days=days)

        # Gercek yapi: h4 > a (parent = div.bc_latest_news_text)
        news_divs = soup.find_all('div', class_='bc_latest_news_text')
        log.info(f"[{self.get_name()}] {len(news_divs)} news div bulundu")

        for news_div in news_divs:
            if len(articles) >= self.MAX_ITEMS:
                break
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
                log.info(f"  [BC] Tam icerik cekiliyor: {title[:50]}...")
                time.sleep(self.ARTICLE_DELAY)
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
                log.warning(f"[{self.get_name()}] Haber islenirken hata: {e}")
                continue

        log.info(f"[{self.get_name()}] {len(articles)} haber bulundu.")
        return articles

    def _parse_date(self, date_str):
        try:
            return datetime.strptime(date_str, '%B %d, %Y')
        except:
            try:
                return datetime.strptime(date_str, '%b %d, %Y')
            except:
                return datetime.now()


class RSSNewsSource(NewsSource):
    """RSS tabanli genel haber kaynagi.

    Akis okunur, `days` penceresi uygulanir, en fazla `max_items` haber islenir
    (Infosecurity Magazine gibi 250 item tasiyan akislarda sayfa cekimi patlamasin).
    Aciklama: content:encoded varsa tam metin oradan; 200 karakterden kisaysa makale
    sayfasindaki paragraflar (BaseRSSScraper._get_expanded_description). `tam_makale`
    True ise ayrica NewsSource.fetch_full_article ile govde denenir ve uzun olan alinir.
    """

    max_items = 15

    def __init__(self, name, feed_url, base_url, tam_makale=False):
        super().__init__()
        self._name = name
        self.feed_url = feed_url
        self.base_url = base_url
        self.tam_makale = tam_makale

    def get_name(self):
        return self._name

    def get_base_url(self):
        return self.base_url

    @staticmethod
    def _baslik_temizle(title):
        # SANS ISC basliklari "... https://isc.sans.edu/podcastdetail/9638, (Thu, Oct 8th)"
        # bicimindedir: URL ve sondaki gun eki atilir; CDATA kaliplari da temizlenir
        title = re.sub(r'<!\[CDATA\[|\]\]>', '', title)
        title = re.sub(r'\s*https?://\S+', '', title)
        title = re.sub(r',?\s*\((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),[^)]*\)\s*$', '', title)
        return title.strip(' ,')

    def fetch_news(self, days=7):
        log.info(f"[{self._name}] RSS'den haberler cekiliyor...")
        try:
            response = self.session.get(self.feed_url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as e:
            log.warning(f"[{self._name}] RSS Hatasi: {e}")
            return []

        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item') or soup.find_all('entry')
        log.info(f"[{self._name}] {len(items)} RSS item bulundu")

        articles = []
        cutoff_date = datetime.now() - timedelta(days=days)
        for item in items:
            if len(articles) >= self.max_items:
                break
            try:
                title_tag = item.find('title')
                title = self._baslik_temizle(title_tag.get_text(strip=True)) if title_tag else ''
                link_tag = item.find('link')
                link = (link_tag.get('href') or link_tag.get_text(strip=True)) if link_tag else ''
                if not title or not link:
                    continue

                pub_tag = item.find('pubDate') or item.find('published') or item.find('updated')
                date_str = pub_tag.get_text(strip=True) if pub_tag else ''
                pub_date = self._parse_rss_date(date_str) if date_str else None
                if pub_date is None:
                    pub_date = datetime.now()
                if pub_date < cutoff_date:
                    continue

                content = self._get_expanded_description(item, link, title)
                if self.tam_makale:
                    try:
                        article_data = self.fetch_full_article(link)
                        if len(article_data['content']) > len(content):
                            content = article_data['content']
                    except Exception as e:
                        log.warning(f"  [{self._name}] Tam icerik alinamadi: {e}")

                articles.append({
                    'title': title,
                    'description': content,
                    'link': link,
                    'date': pub_date.strftime('%Y-%m-%d'),
                    'original_date': date_str,
                    'source': self._name,
                })
            except Exception as e:
                log.warning(f"[{self._name}] Haber islenirken hata: {e}")
                continue

        log.info(f"[{self._name}] {len(articles)} haber bulundu.")
        return articles


class SecurityWeekSource(RSSNewsSource):
    """SecurityWeek kaynagi - RSS + tam makale.

    2026-10-08: ana sayfa HTML'inde baslik linkleri bos geliyordu; bir cekimdeki 22 haber
    tek bir link='' kaydina cokuyordu (NewsArticle.link unique). RSS linkleri tasiyor,
    makale govdesi sayfadan cekilir.
    """

    def __init__(self):
        super().__init__('SecurityWeek', 'https://www.securityweek.com/feed/',
                         'https://www.securityweek.com', tam_makale=True)


class DarkReadingSource(NewsSource):
    """Dark Reading kaynagi - RSS tabanli (site 403 donuyor)"""

    def get_name(self):
        return "Dark Reading"

    def get_base_url(self):
        return "https://www.darkreading.com"

    def fetch_news(self, days=7):
        log.info(f"[{self.get_name()}] RSS'den haberler cekiliyor...")

        try:
            response = self.session.get(
                f"{self.get_base_url()}/rss.xml",
                timeout=30
            )
            response.raise_for_status()
        except requests.RequestException as e:
            log.warning(f"[{self.get_name()}] RSS Hatasi: {e}")
            return []

        # html.parser ile XML parse (lxml gerekmiyor)
        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []
        cutoff_date = datetime.now() - timedelta(days=days)

        items = soup.find_all('item')
        log.info(f"[{self.get_name()}] {len(items)} RSS item bulundu")

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
                log.warning(f"[{self.get_name()}] Haber islenirken hata: {e}")
                continue

        log.info(f"[{self.get_name()}] {len(articles)} haber bulundu.")
        return articles


class KrebsOnSecuritySource(NewsSource):
    """Krebs on Security kaynagi"""

    def get_name(self):
        return "Krebs on Security"

    def get_base_url(self):
        return "https://krebsonsecurity.com"

    def fetch_news(self, days=7):
        log.info(f"[{self.get_name()}] Haberler cekiliyor...")

        try:
            response = self.session.get(self.get_base_url(), timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            log.warning(f"[{self.get_name()}] Hata: {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []

        story_articles = soup.find_all('article')
        cutoff_date = datetime.now() - timedelta(days=days)

        log.info(f"[{self.get_name()}] {len(story_articles)} article bulundu")

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
                        log.info(f"  [Krebs] Tam icerik cekiliyor: {title[:50]}...")
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
                log.warning(f"[{self.get_name()}] Haber islenirken hata: {e}")
                continue

        log.info(f"[{self.get_name()}] {len(articles)} haber bulundu.")
        return articles

    def _parse_date(self, date_str):
        try:
            return datetime.strptime(date_str, '%B %d, %Y')
        except:
            try:
                return datetime.strptime(date_str, '%b %d, %Y')
            except:
                return datetime.now()

class MultiSourceScraper(BaseRSSScraper):
    """Coklu kaynak haber cekici"""

    def __init__(self):
        self.sources = [
            TheHackerNewsSource(),
            BleepingComputerSource(),
            SecurityWeekSource(),
            DarkReadingSource(),
            KrebsOnSecuritySource(),
            # 2026-10-08 eklenen RSS kaynaklari (hepsi anahtarsiz, bot engeli yok)
            RSSNewsSource('The Record', 'https://therecord.media/feed',
                          'https://therecord.media', tam_makale=True),
            RSSNewsSource('CyberScoop', 'https://cyberscoop.com/feed/', 'https://cyberscoop.com'),
            RSSNewsSource('Help Net Security', 'https://www.helpnetsecurity.com/feed/',
                          'https://www.helpnetsecurity.com', tam_makale=True),
            RSSNewsSource('Infosecurity Magazine', 'https://www.infosecurity-magazine.com/rss/news/',
                          'https://www.infosecurity-magazine.com'),
            RSSNewsSource('SANS ISC', 'https://isc.sans.edu/rssfeed_full.xml', 'https://isc.sans.edu'),
            RSSNewsSource('The Register', 'https://www.theregister.com/security/headlines.atom',
                          'https://www.theregister.com'),
            RSSNewsSource('Security Affairs', 'https://securityaffairs.com/feed',
                          'https://securityaffairs.com'),
        ]

    def fetch_all_news(self, days=7, selected_sources=None, max_total=30):
        """Tum kaynaklardan haber ceker (max_total ile sinirli)"""
        all_articles = []
        sources_to_fetch = self.sources

        if selected_sources:
            sources_to_fetch = [s for s in self.sources if s.get_name() in selected_sources]

        # Kaynak sayisi arttikca toplam tavan da buyusun: 12 kaynakta 30'luk sabit tavan,
        # tarihe gore siralamada seyrek yazan kaynaklari (Krebs, SANS) tamamen dusuruyordu.
        max_total = max(max_total, 3 * len(sources_to_fetch))

        log.debug(f"\n{'='*80}")
        log.info(f"TUM KAYNAKLARDAN HABER CEKILIYOR ({days} gun, maks {max_total})")
        log.debug(f"{'='*80}\n")

        # Her kaynaga esit pay ver
        per_source_limit = max(5, max_total // max(len(sources_to_fetch), 1))

        for source in sources_to_fetch:
            try:
                articles = source.fetch_news(days=days)
                # Kaynak basina limit uygula
                if len(articles) > per_source_limit:
                    articles = articles[:per_source_limit]
                    log.info(f"  -> {source.get_name()}: {per_source_limit} haber (sinirlandirildi)\n")
                else:
                    log.info(f"  -> {source.get_name()}: {len(articles)} haber\n")
                all_articles.extend(articles)
            except Exception as e:
                log.warning(f"[{source.get_name()}] Kaynak hatasi: {e}")
                continue

        # Tarihe gore sirala (en yeni en ustte)
        all_articles.sort(key=lambda x: x['date'], reverse=True)

        # Toplam sinir
        if len(all_articles) > max_total:
            all_articles = all_articles[:max_total]

        log.debug(f"{'='*80}")
        log.info(f"TOPLAM {len(all_articles)} HABER CEKILDI")
        log.debug(f"{'='*80}\n")

        return all_articles

    def process_news(self, articles):
        """Haberleri tam olarak Turkceye cevirir"""

        total = len(articles)
        log.debug(f"\n{'='*60}")
        log.info(f"CEVIRI BASLADI: {total} haber cevriliyor...")
        log.debug(f"{'='*60}\n")

        for i, article in enumerate(articles):
            log.info(f"Cevriliyor: {i+1}/{total} - {article['title'][:50]}...")

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
                    'original_description': article['description'],
                    'turkish_description': translated_desc,
                    'turkish_summary': '',
                    'link': article['link'],
                    'date': article['date'],
                    'original_date': article['original_date'],
                    'source': article['source']
                }
            except Exception as e:
                log.warning(f"Haber islenirken hata: {e}")
                yield {
                    'original_title': article['title'],
                    'turkish_title': article['title'],
                    'original_description': article['description'],
                    'turkish_description': article['description'],
                    'turkish_summary': '',
                    'link': article['link'],
                    'date': article['date'],
                    'original_date': article['original_date'],
                    'source': article['source']
                }
        log.debug(f"\n{'='*60}")
        log.debug(f"{'='*60}\n")

        

    def save_to_json(self, articles, filename=None):
        """Haberleri JSON olarak kaydeder"""
        if not filename:
            filename = f"cybersecurity_news_multi_{datetime.now().strftime('%Y%m%d_%H%M')}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)

        log.info(f"Haberler {filename} dosyasina kaydedildi.")
        return filename


if __name__ == "__main__":
    scraper = MultiSourceScraper()
    articles = scraper.fetch_all_news(days=7)

    if articles:
        processed = scraper.process_news(articles)
        scraper.save_to_json(processed)
    else:
        print("\nHaber bulunamadi!")
