import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
from typing import List, Dict, Optional
from email.utils import parsedate_to_datetime

class BaseRSSScraper:
    """Tüm RSS tabanli scraperlar icin temel sinif."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        })

    def _parse_rss_date(self, date_str: str) -> Optional[datetime]:
        if not date_str: return None
        try:
            dt = parsedate_to_datetime(date_str)
            return dt.replace(tzinfo=None) if dt else None
        except:
            pass
        formats = [
            '%a, %d %b %Y %H:%M:%S %Z', '%a, %d %b %Y %H:%M:%S %z',
            '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S%z',
            '%a, %d %b %Y %H:%M:%S +0000', '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d', '%B %d, %Y', '%b %d, %Y'
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.replace(tzinfo=None)
            except:
                continue
        return None

    def _html_to_text(self, html_content: str) -> str:
        if not html_content: return ""
        soup = BeautifulSoup(html_content, 'html.parser')
        for tag in soup.find_all(['script', 'style']):
            tag.decompose()
        text = soup.get_text(separator=' ', strip=True)
        return re.sub(r'\s+', ' ', text).strip()

    def _get_expanded_description(self, item, link: str, title: str) -> str:
        desc_tag = item.find('description')
        desc = self._html_to_text(desc_tag.get_text()) if desc_tag else ""
        
        content_tag = item.find('encoded') or item.find('content:encoded') or item.find('content')
        if content_tag:
            content_desc = self._html_to_text(content_tag.get_text())
            if len(content_desc) > len(desc):
                desc = content_desc

        if len(desc) < 200 and link:
            try:
                resp = self.session.get(link, timeout=5)
                soup = BeautifulSoup(resp.content, 'html.parser')
                ps = [p.get_text(separator=' ', strip=True) for p in soup.find_all('p')]
                blacklist = ['flash sale', 'get $', 'ticket:', 'register now', 'subscribe to', 'newsletter', 'cookies', 'privacy policy']
                valid_ps = []
                for p in ps:
                    if len(p) > 50:
                        p_lower = p.lower()
                        if not any(b in p_lower for b in blacklist):
                            valid_ps.append(p)
                
                if len(valid_ps) > 0:
                    expanded = ""
                    for p in valid_ps:
                        if len(expanded) + len(p) > 1500:
                            break
                        expanded += p + "\n\n"
                    if expanded:
                        desc = expanded.strip()
                    elif len(valid_ps[0]) > 1500:
                        desc = valid_ps[0][:1497].rsplit(' ', 1)[0] + "..."
                    else:
                        desc = valid_ps[0]
            except Exception:
                pass
                
        return desc if desc else title

    def fetch_standard_rss_entries(self, feed_url: str, source_name: str, days: int = 30) -> List[Dict]:
        """Standart bir RSS akisini okuyup liste dondurur."""
        print(f"[{source_name}] Son {days} gunun haberleri cekiliyor...")
        entries = []
        cutoff = datetime.now() - timedelta(days=days)
        try:
            resp = self.session.get(feed_url, timeout=20)
            soup = BeautifulSoup(resp.content, 'xml')
            items = soup.find_all('item')
            if not items:
                items = soup.find_all('entry')

            for item in items:
                pub_tag = item.find('pubDate') or item.find('published') or item.find('updated')
                pub_date = self._parse_rss_date(pub_tag.get_text(strip=True)) if pub_tag else None
                if pub_date and pub_date.replace(tzinfo=None) < cutoff: continue
                
                title_tag = item.find('title')
                title = title_tag.get_text(strip=True) if title_tag else "Basliksiz"
                
                link_tag = item.find('link')
                if link_tag and link_tag.get('href'):
                    link = link_tag.get('href')
                else:
                    link = link_tag.get_text(strip=True) if link_tag else ""

                desc = self._get_expanded_description(item, link, title)
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                
                entries.append({
                    'title': title,
                    'description': desc[:8000],
                    'link': link,
                    'date': date_str,
                    'source': source_name
                })
        except Exception as e:
            print(f"[{source_name}] Hata: {e}")
            
        return entries
