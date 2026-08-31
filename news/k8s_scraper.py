from news.base_scraper import BaseRSSScraper
"""
Kubernetes Scraper Module
kubernetes.io/blog, GitHub Releases, CNCF Blog kaynaklarindan
Kubernetes haberlerini, surum guncellemelerini ve guvenlik bilgilerini ceker.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
from typing import List, Dict, Optional
import time

from news.translation_utils import (
    translate_text, translate_long_text,
    _protect_terms, _restore_terms, turkish_post_process,
)


class K8sScraper(BaseRSSScraper):
    """Kubernetes Scraper temel sinifi"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        })
    def fetch_article_content(self, url: str) -> Dict:
        """Haber linkine gidip gercek baslik ve icerigi ceker"""
        result = {'title': '', 'description': ''}
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Baslik: og:title meta > h1 > title
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                result['title'] = og_title['content'].strip()
            else:
                h1 = soup.find('h1')
                if h1:
                    result['title'] = h1.get_text(strip=True)
                else:
                    title_tag = soup.find('title')
                    if title_tag:
                        result['title'] = title_tag.get_text(strip=True)

            # Gereksiz tag'leri kaldir
            for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header',
                                       'aside', 'iframe', 'form', 'noscript']):
                tag.decompose()

            # Article body'yi bul
            article_body = (
                soup.find('div', class_=re.compile(r'article-body|article_body|articlebody', re.I)) or
                soup.find('div', class_=re.compile(r'post-body|post_body|postbody', re.I)) or
                soup.find('div', class_=re.compile(r'post-content|post_content|postcontent', re.I)) or
                soup.find('div', class_=re.compile(r'entry-content|entry_content|entrycontent', re.I)) or
                soup.find('div', class_=re.compile(r'blog-content|blog_content|blogcontent', re.I)) or
                soup.find('div', class_=re.compile(r'content-body|content_body|contentbody', re.I)) or
                soup.find('article') or
                soup.find('main')
            )

            # Article body icindeki gereksiz alt bloklari temizle
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
                    if len(txt) > 20 and not re.match(
                        r'^(Share|Tweet|Email|Print|Related|Also read|Read more|'
                        r'Subscribe|Sign up|Follow us|Advertisement|Recommended)',
                        txt, re.I):
                        text_parts.append(txt)
                result['description'] = '\n\n'.join(text_parts)
            else:
                # Fallback: og:description veya meta description
                og_desc = soup.find('meta', property='og:description')
                if og_desc and og_desc.get('content') and len(og_desc['content'].strip()) > 30:
                    result['description'] = og_desc['content'].strip()
                else:
                    meta_desc = soup.find('meta', attrs={'name': 'description'})
                    if meta_desc and meta_desc.get('content') and len(meta_desc['content'].strip()) > 30:
                        result['description'] = meta_desc['content'].strip()

            time.sleep(0.3)
        except Exception as e:
            print(f"  [fetch_article_content] Hata ({url[:60]}): {e}")

        return result

    def classify_entry(self, title: str, description: str) -> str:
        """Haberi kategorize eder: release, security, feature, ecosystem, blog"""
        text = (title + " " + description).lower()
        if any(w in text for w in ['cve', 'vulnerability', 'security advisory', 'patch', 'guvenlik']):
            return 'security'
        if any(w in text for w in ['release', 'v1.', 'changelog', 'upgrade', 'surum', 'version']):
            return 'release'
        if any(w in text for w in ['feature', 'enhancement', 'new in', 'beta', 'alpha', 'deprecat']):
            return 'feature'
        if any(w in text for w in ['cncf', 'helm', 'istio', 'envoy', 'prometheus', 'argo', 'ecosystem']):
            return 'ecosystem'
        return 'blog'

    # K8s PROTECTED_TERMS ve protect/restore artik translation_utils modulunden geliyor


class K8sBlogScraper(K8sScraper):
    """kubernetes.io/blog scraper - sidebar navigation'dan blog postlarini ceker"""

    BASE_URL = "https://kubernetes.io/blog/"

    def fetch_entries(self, days: int = 30) -> List[Dict]:
        print(f"[K8s Blog] Son {days} gunun haberleri cekiliyor...")
        entries = []
        cutoff = datetime.now().date() - timedelta(days=days)

        try:
            response = self.session.get(self.BASE_URL, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Sidebar navigation'daki blog post linkleri
            # Yapi: <nav id="td-section-nav"> icinde <a href="/blog/YYYY/MM/DD/slug/"> <span>Title</span> </a>
            sidebar_nav = soup.find('nav', id='td-section-nav')
            if not sidebar_nav:
                sidebar_nav = soup.find('nav', class_=re.compile(r'sidebar', re.I))

            if not sidebar_nav:
                print("[K8s Blog] Sidebar navigation bulunamadi, tum sayfa taranacak")
                # Fallback: tum sayfadaki /blog/YYYY/MM/DD/ formatindaki linkleri bul
                all_links = soup.find_all('a', href=re.compile(r'^/blog/\d{4}/\d{2}/\d{2}/'))
            else:
                all_links = sidebar_nav.find_all('a', href=re.compile(r'^/blog/\d{4}/\d{2}/\d{2}/'))

            seen_urls = set()
            for link_tag in all_links:
                try:
                    href = link_tag['href']
                    full_url = f"https://kubernetes.io{href}"

                    # Tekrarlari onle
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    # Basligi sidebar link textinden al
                    span = link_tag.find('span')
                    title = span.get_text(strip=True) if span else link_tag.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    # URL'den tarih cikar: /blog/YYYY/MM/DD/slug/
                    date_match = re.search(r'/blog/(\d{4})/(\d{2})/(\d{2})/', href)
                    if date_match:
                        try:
                            pub_date = datetime(
                                int(date_match.group(1)),
                                int(date_match.group(2)),
                                int(date_match.group(3))
                            ).date()
                        except ValueError:
                            pub_date = datetime.now().date()
                    else:
                        pub_date = datetime.now().date()

                    if pub_date < cutoff:
                        continue

                    # Haberin icine girip gercek icerigi cek
                    print(f"  [K8s Blog] Icerik cekiliyor: {title[:60]}...")
                    content = self.fetch_article_content(full_url)

                    # Eger deep fetch'ten daha iyi baslik geldiyse kullan
                    if content['title'] and len(content['title']) > len(title):
                        title = content['title']

                    desc = content['description'] or ''
                    category = self.classify_entry(title, desc)

                    entries.append({
                        'source': 'K8s Blog',
                        'original_title': title,
                        'original_description': desc or title,
                        'link': full_url,
                        'published_date': pub_date,
                        'category': category,
                        'version': self._extract_version(title + ' ' + desc),
                })
                except Exception as e:
                    print(f"[K8s Blog] Isleme hatasi: {e}")
                    continue

            print(f"[K8s Blog] {len(entries)} haber bulundu")
        except Exception as e:
            print(f"[K8s Blog] Hata: {e}")
        return entries

    def _extract_version(self, text: str) -> str:
        m = re.search(r'v?(\d+\.\d+(?:\.\d+)?)', text)
        return m.group(0) if m else ''


class K8sGitHubScraper(K8sScraper):
    """GitHub kubernetes/kubernetes releases scraper - Gercek CHANGELOG iceriklerini ceker"""

    API_URL = "https://api.github.com/repos/kubernetes/kubernetes/releases"
    CHANGELOG_RAW_URL = "https://raw.githubusercontent.com/kubernetes/kubernetes/master/CHANGELOG/CHANGELOG-{major_minor}.md"

    def _parse_changelog_to_structured(self, changes_md: str) -> str:
        """
        CHANGELOG markdown'ini yapisal formata donusturur.
        Format:
          ===SECTION: Bug or Regression===
          ---ITEM---
          Aciklama metni buraya gelir.
          <<<PR#136567|@pohly|SIG Node, Scheduling and Testing>>>
          ---ITEM---
          Baska bir aciklama.
          <<<PR#135843|@princepereira|SIG Network and Windows>>>
          ===SECTION: Feature===
          ...
        """
        lines = changes_md.split('\n')
        result_parts = []
        current_section = None
        current_item_lines = []

        def flush_item():
            nonlocal current_item_lines
            if not current_item_lines:
                return
            item_text = ' '.join(current_item_lines).strip()
            if not item_text:
                current_item_lines = []
                return

            # PR referansini ayikla: ([#123456](url), [@user](url)) [SIG ...]
            pr_match = re.search(
                r'\(\[#(\d+)\]\([^)]+\),\s*\[@([\w-]+)\]\([^)]+\)\)\s*\[SIG ([^\]]+)\]',
                item_text
            )
            if not pr_match:
                # Alternatif: (#123456, @user) [SIG ...]  (URL'siz)
                pr_match = re.search(
                    r'\(#(\d+),\s*@([\w-]+)\)\s*\[SIG ([^\]]+)\]',
                    item_text
                )

            if pr_match:
                pr_num = pr_match.group(1)
                author = pr_match.group(2)
                sigs = pr_match.group(3)
                # Aciklama metninden PR referansini cikar
                desc = item_text[:pr_match.start()].strip()
                # Markdown linklerini temizle: [text](url) -> text
                desc = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', desc)
                # Backtick'leri koru ama isaretlerini temizle
                desc = re.sub(r'`([^`]+)`', r'«\1»', desc)
                # Bold/italic temizle
                desc = re.sub(r'\*\*([^*]+)\*\*', r'\1', desc)
                desc = re.sub(r'\*([^*]+)\*', r'\1', desc)

                result_parts.append(f"---ITEM---")
                result_parts.append(desc.strip())
                result_parts.append(f"<<<PR#{pr_num}|@{author}|SIG {sigs}>>>")
            else:
                # PR referansi bulunamadi — duuz metin olarak ekle
                desc = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', item_text)
                desc = re.sub(r'`([^`]+)`', r'«\1»', desc)
                desc = re.sub(r'\*\*([^*]+)\*\*', r'\1', desc)
                desc = re.sub(r'\*([^*]+)\*', r'\1', desc)
                result_parts.append(f"---ITEM---")
                result_parts.append(desc.strip())

            current_item_lines = []

        for line in lines:
            stripped = line.strip()

            # Section basligi: ## Changes by Kind, ### Bug or Regression
            section_match = re.match(r'^#{2,3}\s+(.+)', stripped)
            if section_match:
                flush_item()
                section_name = section_match.group(1).strip()
                # "Changes by Kind" ana basligini atla, alt basliklari tut
                if section_name.lower() not in ('changes by kind', 'changelog since'):
                    current_section = section_name
                    result_parts.append(f"===SECTION: {section_name}===")
                continue

            # Yeni madde: - ile baslar
            if re.match(r'^[-*+]\s+', stripped):
                flush_item()
                item_text = re.sub(r'^[-*+]\s+', '', stripped)
                current_item_lines.append(item_text)
                continue

            # Devam eden madde: bos olmayan indent'li satir
            if stripped and current_item_lines:
                current_item_lines.append(stripped)
                continue

            # Bos satir
            if not stripped:
                # Biriken item varsa flush et
                if current_item_lines:
                    flush_item()

        flush_item()

        return '\n'.join(result_parts)

    def _clean_markdown_to_text(self, md_text: str) -> str:
        """Markdown formatindaki release notes'u okunabilir metne cevirir"""
        if not md_text:
            return ""

        text = md_text

        # Markdown linklerini temizle: [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        # Bold/italic temizle
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        # Inline code temizle
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # Header'lari temizle: ## Title -> Title
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # HTML tag'lerini temizle
        text = re.sub(r'<[^>]+>', '', text)
        # Horizontal rule temizle
        text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
        # Liste isaretlerini temizle ama icerik kalsin
        text = re.sub(r'^\s*[-*+]\s+', '- ', text, flags=re.MULTILINE)
        # Bos satirlari normalize et
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _extract_version_section(self, full_changelog: str, version: str) -> str:
        """
        Buyuk CHANGELOG dosyasindan sadece belirli versiyonun bolumunu cikarir.
        Ornek: version='v1.35.1' -> '# v1.35.1' ile baslayan bolumu alir,
        bir sonraki '# v...' basligina kadar.
        """
        # Versiyon basligini bul: "# v1.35.1" (basinda # ve v ile)
        version_clean = version.lstrip('v')

        # Farkli formatlari dene: "# v1.35.1", "## v1.35.1", "# v1.35.1 " (trailing space)
        match = None
        for prefix in [r'^# ', r'^## ']:
            pattern = prefix + r'v' + re.escape(version_clean) + r'\s*$'
            match = re.search(pattern, full_changelog, re.MULTILINE)
            if match:
                break

        if not match:
            print(f"  [K8s GitHub] Versiyon bolumu bulunamadi: {version}")
            # Debug: ilk 500 karakteri goster
            print(f"  [K8s GitHub] CHANGELOG ilk 500 kar: {full_changelog[:500]}")
            return ""

        start = match.start()
        print(f"  [K8s GitHub] Versiyon bolumu bulundu: pozisyon {start}")

        # Sonraki versiyon basligini bul (bir sonraki "# v" satirina kadar)
        # Hem "# vX.Y.Z" hem "## vX.Y.Z" formatlarini destekle
        next_version = re.search(r'^#{1,2} v\d+\.\d+', full_changelog[match.end():], re.MULTILINE)
        if next_version:
            end = match.end() + next_version.start()
        else:
            end = len(full_changelog)

        section = full_changelog[start:end]
        print(f"  [K8s GitHub] Versiyon bolumu: {len(section)} karakter")
        return section

    def _extract_changes_section(self, version_section: str) -> str:
        """
        Versiyon bolumunden Downloads/hashes tablolarini cikarip sadece
        anlamli icerigi (Changes by Kind, Urgent Upgrade Notes, Dependencies) birakir.
        """
        lines = version_section.split('\n')
        result_lines = []
        skip_section = False

        # Atlanacak bolumlerin baslik kaliplari
        skip_headers = [
            'downloads for v',
            'source code',
            'client binaries',
            'server binaries',
            'node binaries',
            'container images',
        ]

        # Tutulacak bolumlerin baslik kaliplari (bunlar geldiklerinde skip durur)
        keep_headers = [
            'changelog since',
            'changes by kind',
            'urgent upgrade notes',
            'dependencies',
        ]

        for line in lines:
            # Header satiri mi kontrol et (## veya ### ile baslar)
            if re.match(r'^#{1,4}\s+', line):
                header_text = re.sub(r'^#{1,4}\s+', '', line).lower().strip()

                # Bu atlanacak bir bolum mu?
                if any(skip in header_text for skip in skip_headers):
                    skip_section = True
                    continue

                # Bu tutulacak bir bolum mu? (veya skip listesinde degilse)
                if any(keep in header_text for keep in keep_headers):
                    skip_section = False
                elif not any(skip in header_text for skip in skip_headers):
                    # Bilinmeyen baslik — skip_section durumunu koru
                    # ama download sectionlari icinde degilse tut
                    if skip_section:
                        continue

            # Skip durumundaysa atla
            if skip_section:
                continue

            # Tablo satirlarini atla (sha512 hash, download linkleri)
            if '|' in line:
                lower = line.lower()
                if ('sha512' in lower or '----' in line or
                    'filename' in lower or '.tar.gz' in line or
                    'registry.k8s.io' in line or 'console.cloud.google' in line or
                    'architectures' in lower):
                    continue

            # Icerik satirini ekle
            result_lines.append(line)

        text = '\n'.join(result_lines)
        print(f"  [K8s GitHub] Filtrelenmis icerik: {len(text)} karakter")
        return text

    def __init__(self):
        super().__init__()
        # CHANGELOG dosya icerigini cache'le (ayni major.minor icin tekrar indirme)
        self._changelog_cache = {}

    def _get_full_changelog(self, major_minor: str) -> str:
        """CHANGELOG dosyasini indir veya cache'ten al"""
        if major_minor in self._changelog_cache:
            return self._changelog_cache[major_minor]

        url = self.CHANGELOG_RAW_URL.format(major_minor=major_minor)
        try:
            print(f"  [K8s GitHub] CHANGELOG dosyasi indiriliyor: CHANGELOG-{major_minor}.md")
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            content = response.text
            self._changelog_cache[major_minor] = content
            print(f"  [K8s GitHub] CHANGELOG-{major_minor}.md: {len(content)} karakter indirildi")
            return content
        except Exception as e:
            print(f"  [K8s GitHub] CHANGELOG indirilemedi ({major_minor}): {e}")
            self._changelog_cache[major_minor] = ""
            return ""

    def _fetch_real_changelog(self, tag_name: str) -> str:
        """
        GitHub'dan CHANGELOG-X.YY.md dosyasini ceker ve
        yapisal formatta (===SECTION, ---ITEM---, <<<PR>>>)
        sadece ilgili versiyonun Changes by Kind bolumunu dondurur.
        """
        # tag_name'den major.minor cikar: v1.35.1 -> 1.35
        version_match = re.match(r'v?(\d+\.\d+)', tag_name)
        if not version_match:
            print(f"  [K8s GitHub] Versiyon parse edilemedi: {tag_name}")
            return ""

        major_minor = version_match.group(1)

        try:
            full_changelog = self._get_full_changelog(major_minor)
            if not full_changelog:
                return ""

            # Sadece bu versiyonun bolumunu cikar
            version_section = self._extract_version_section(full_changelog, tag_name)
            if not version_section:
                return ""

            # Downloads/hashes tablolarini cikar, sadece Changes by Kind birak
            changes_only = self._extract_changes_section(version_section)

            # Yapisal formata donustur
            structured = self._parse_changelog_to_structured(changes_only)

            print(f"  [K8s GitHub] Yapisal CHANGELOG: {len(structured)} karakter ({tag_name})")
            return structured.strip()

        except Exception as e:
            print(f"  [K8s GitHub] CHANGELOG cekilemedi ({tag_name}): {e}")
            return ""

    def fetch_entries(self, days: int = 30) -> List[Dict]:
        print(f"[K8s GitHub] Son {days} gunun release'leri cekiliyor (gercek CHANGELOG dahil)...")
        entries = []
        cutoff = datetime.now().date() - timedelta(days=days)

        try:
            response = self.session.get(self.API_URL, params={'per_page': 30}, timeout=30)
            response.raise_for_status()
            releases = response.json()

            for rel in releases:
                try:
                    pub_str = rel.get('published_at', '')
                    if not pub_str:
                        continue
                    pub_date = datetime.strptime(pub_str[:10], '%Y-%m-%d').date()
                    if pub_date < cutoff:
                        continue

                    name = rel.get('name', '') or rel.get('tag_name', '')
                    tag_name = rel.get('tag_name', '')
                    version = tag_name

                    # Gercek CHANGELOG icerigini cek
                    body = self._fetch_real_changelog(tag_name)

                    if not body or len(body) < 50:
                        body = f"Kubernetes {name} surumu yayinlandi. Detaylar icin CHANGELOG'a bakiniz."

                    is_pre = rel.get('prerelease', False)
                    category = 'release'
                    if is_pre:
                        category = 'feature'

                    entries.append({
                        'source': 'GitHub Releases',
                        'original_title': f"Kubernetes {name} Released",
                        'original_description': body,
                        'link': rel.get('html_url', ''),
                        'published_date': pub_date,
                        'category': category,
                        'version': version,
                    })
                    print(f"  [K8s GitHub] {name}: {len(body)} karakter icerik")
                except Exception as e:
                    print(f"[K8s GitHub] Isleme hatasi: {e}")
                    continue

            print(f"[K8s GitHub] {len(entries)} release bulundu")
        except Exception as e:
            print(f"[K8s GitHub] Hata: {e}")
        return entries


class CNCFBlogScraper(K8sScraper):
    """CNCF Blog scraper - WordPress REST API kullanir"""

    # WordPress REST API - Blog kategorisi (category ID 230)
    API_URL = "https://www.cncf.io/wp-json/wp/v2/posts"

    def fetch_entries(self, days: int = 30) -> List[Dict]:
        print(f"[CNCF Blog] Son {days} gunun haberleri cekiliyor (WP API)...")
        entries = []
        cutoff = datetime.now().date() - timedelta(days=days)

        try:
            # WordPress API'den blog postlarini cek
            params = {
                'per_page': 30,
                'orderby': 'date',
                'order': 'desc',
                # Tum blog postlari (category filtresi olmadan daha genis sonuc)
                '_fields': 'id,date,title,excerpt,content,link,categories',
            }

            response = self.session.get(self.API_URL, params=params, timeout=30)
            response.raise_for_status()
            posts = response.json()

            for post in posts:
                try:
                    # Tarih parse
                    date_str = post.get('date', '')
                    if not date_str:
                        continue
                    pub_date = datetime.strptime(date_str[:10], '%Y-%m-%d').date()
                    if pub_date < cutoff:
                        continue

                    # Baslik: WordPress API'de rendered HTML olarak gelir
                    title_raw = post.get('title', {}).get('rendered', '')
                    # HTML entity'leri temizle
                    title_soup = BeautifulSoup(title_raw, 'html.parser')
                    title = title_soup.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    link = post.get('link', '')

                    # WordPress API'den tam icerik al (content.rendered)
                    desc = ''
                    content_raw = post.get('content', {}).get('rendered', '')
                    if content_raw:
                        content_soup = BeautifulSoup(content_raw, 'html.parser')
                        # Gereksiz elementleri temizle
                        for tag in content_soup.find_all(['script', 'style', 'iframe', 'form']):
                            tag.decompose()
                        paragraphs = content_soup.find_all('p')
                        text_parts = []
                        for p in paragraphs:
                            txt = p.get_text(strip=True)
                            if len(txt) > 20:
                                text_parts.append(txt)
                        desc = '\n\n'.join(text_parts)
                    
                    # Fallback: excerpt kullan
                    if not desc:
                        excerpt_raw = post.get('excerpt', {}).get('rendered', '')
                        excerpt_soup = BeautifulSoup(excerpt_raw, 'html.parser')
                        desc = excerpt_soup.get_text(strip=True)

                    # "Continue reading" gibi kaliplari temizle
                    desc = re.sub(r'\s*Continue reading.*$', '', desc, flags=re.I)
                    desc = re.sub(r'\s*Read more.*$', '', desc, flags=re.I)
                    category = self.classify_entry(title, desc)

                    entries.append({
                        'source': 'CNCF Blog',
                        'original_title': title,
                        'original_description': desc or title,
                        'link': link,
                        'published_date': pub_date,
                        'category': category,
                        'version': self._extract_version(title + ' ' + desc),
                })
                except Exception as e:
                    print(f"[CNCF Blog] Isleme hatasi: {e}")
                    continue

            print(f"[CNCF Blog] {len(entries)} haber bulundu")
        except Exception as e:
            print(f"[CNCF Blog] Hata: {e}")
        return entries

    def _extract_version(self, text: str) -> str:
        m = re.search(r'v?(\d+\.\d+(?:\.\d+)?)', text)
        return m.group(0) if m else ''


class MultiK8sScraper(K8sScraper):
    """Tum Kubernetes kaynaklarini birlestiren scraper"""

    def __init__(self):
        super().__init__()
        self.blog_scraper = K8sBlogScraper()
        self.github_scraper = K8sGitHubScraper()
        self.cncf_scraper = CNCFBlogScraper()

    def fetch_all(self, days: int = 30, selected_sources: list = None) -> List[Dict]:
        all_entries = []

        print("=" * 80)
        print(f"TUM KUBERNETES KAYNAKLARINDAN VERI CEKILIYOR ({days} gun)")
        print("=" * 80)

        sources = {
            'K8s Blog': self.blog_scraper,
            'GitHub Releases': self.github_scraper,
            'CNCF Blog': self.cncf_scraper,
        }

        if selected_sources:
            sources = {k: v for k, v in sources.items() if k in selected_sources}

        for name, scraper in sources.items():
            try:
                items = scraper.fetch_entries(days=days)
                print(f"  -> {name}: {len(items)} haber")
                all_entries.extend(items)
            except Exception as e:
                print(f"  -> {name}: HATA - {e}")

        # Link bazli deduplicate
        seen = set()
        unique = []
        for e in all_entries:
            key = e.get('link', '') or e.get('original_title', '')
            if key and key not in seen:
                seen.add(key)
                unique.append(e)

        print("=" * 80)
        print(f"TOPLAM {len(unique)} KUBERNETES HABERI CEKILDI")
        print("=" * 80)
        return unique

    def _translate_structured_changelog(self, structured_text: str) -> str:
        """
        Yapisal CHANGELOG formatindaki her ITEM'in aciklama kismini
        teknik terimleri koruyarak cevirir.
        ===SECTION, <<<PR>>>, ---ITEM--- satirlarini oldugu gibi birakir.
        """
        lines = structured_text.split('\n')
        result_lines = []
        desc_buffer = []

        # Section başlıklarının Türkçe karşılıkları
        section_translations = {
            'Bug or Regression': 'Hata veya Gerileme',
            'Feature': 'Özellik',
            'Failing Test': 'Başarısız Test',
            'Documentation': 'Dokümantasyon',
            'Deprecation': 'Kaldırılacak Özellikler',
            'API Change': 'API Değişikliği',
            'Other (Cleanup or Flake)': 'Diğer (Temizlik)',
            'Uncategorized': 'Kategorisiz',
            'Dependencies': 'Bağımlılıklar',
            'Added': 'Eklenen',
            'Changed': 'Değişen',
            'Removed': 'Kaldırılan',
            'Urgent Upgrade Notes': 'Acil Yükseltme Notları',
        }

        def flush_desc():
            nonlocal desc_buffer
            if not desc_buffer:
                return
            desc_text = ' '.join(desc_buffer).strip()
            if desc_text:
                # Teknik terimleri koru, cevir, geri yukle
                protected, replacements = _protect_terms(desc_text)
                translated = translate_long_text(protected)
                restored = _restore_terms(translated, replacements)
                # «term» isaretlerini geri `term` formatina cevir
                restored = re.sub(r'[«»]', '`', restored)
                result_lines.append(restored)
            desc_buffer = []

        for line in lines:
            stripped = line.strip()

            # Section basligi
            if stripped.startswith('===SECTION:') and stripped.endswith('==='):
                flush_desc()
                section_name = stripped[11:-3].strip()
                tr_name = section_translations.get(section_name, section_name)
                result_lines.append(f"===SECTION: {tr_name}===")
                continue

            # PR referansi
            if stripped.startswith('<<<') and stripped.endswith('>>>'):
                flush_desc()
                result_lines.append(stripped)
                continue

            # Item ayirici
            if stripped == '---ITEM---':
                flush_desc()
                result_lines.append(stripped)
                continue

            # Aciklama metni
            if stripped:
                desc_buffer.append(stripped)

        flush_desc()
        return '\n'.join(result_lines)

    def process_entries(self, entries: List[Dict]) -> List[Dict]:
        print("\nKubernetes haberleri Turkceye cevriliyor...")
        total = len(entries)

        for i, entry in enumerate(entries, 1):
            try:
                desc = entry.get('original_description', '')
                source = entry.get('source', '')
                print(f"Isleniyor: {i}/{total} - {entry['original_title'][:50]}... ({len(desc)} karakter)")

                entry['turkish_title'] = translate_text(entry['original_title'])

                if source == 'GitHub Releases' and '===SECTION:' in desc:
                    # Yapisal CHANGELOG — ozel ceviri
                    entry['turkish_description'] = self._translate_structured_changelog(desc)
                else:
                    # Normal blog/haber icerigi — standart ceviri
                    entry['turkish_description'] = translate_long_text(desc)

                yield entry
            except Exception as e:
                print(f"Isleme hatasi: {e}")
                entry['turkish_title'] = entry['original_title']
                entry['turkish_description'] = entry['original_description']
                yield entry
        


if __name__ == "__main__":
    scraper = MultiK8sScraper()
    entries = scraper.fetch_all(days=30)
    print(f"\nToplam {len(entries)} Kubernetes haberi cekildi")
