"""
DevTools Scraper Module — Altyapi Araclari Guncelleme Takibi
14 kaynak:
  - MinIO (GitHub Releases API) — ust kaynak Ekim 2025'ten beri surum yayinlamiyor
  - Seq (Datalust Blog RSS)
  - Ceph (GitHub Releases Atom)
  - MongoDB (GitHub Tags Atom + resmi surum notlari sayfasi)
  - PostgreSQL (Resmi News RSS)
  - RabbitMQ (GitHub Releases API)
  - Elasticsearch + Kibana (GitHub Releases API)
  - Redis (Blog RSS, filtreli)
  - Moodle (GitHub Tags API + Download page)
  - LiteLLM, LangGraph, Langfuse, Keycloak (GitHub Releases API, ortak sinif)
  - GitLab (docs.gitlab.com resmi surum notlari Atom)

GitHub API anonim limiti 60 istek/saat/IP'dir; GITHUB_TOKEN verilirse yalniz
api.github.com isteklerine Bearer baslik eklenir (bkz. DevToolsScraper._github_get).
"""

import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
from typing import List, Dict, Optional
import time
from email.utils import parsedate_to_datetime

from news.translation_utils import translate_text, translate_long_text
from news.base_scraper import BaseRSSScraper
import logging

log = logging.getLogger(__name__)


class DevToolsScraper(BaseRSSScraper):
    """DevTools Scraper temel sinifi"""

    GITHUB_API = "https://api.github.com/"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/html, application/xhtml+xml, application/xml;q=0.9,*/*;q=0.8',
        })

    def _github_get(self, url: str, **kwargs):
        """api.github.com istegi: GITHUB_TOKEN tanimliysa Bearer baslik ekler.

        Baslik oturuma degil tek istege konur ve yalniz api.github.com'a gider;
        ayni oturum datalust.co, redis.io gibi hostlara da istek attigi icin token
        oraya sizmamali. Token'siz anonim limit 60/saat/IP, token ile 5000/saat.
        """
        headers = dict(kwargs.pop('headers', None) or {})
        token = os.environ.get('GITHUB_TOKEN', '').strip()
        if token and url.startswith(self.GITHUB_API):
            headers['Authorization'] = f'Bearer {token}'
        headers.setdefault('Accept', 'application/vnd.github+json')
        return self.session.get(url, headers=headers, **kwargs)
    def _markdown_to_text(self, md: str) -> str:
        """Markdown'dan temiz metin cikarir"""
        if not md:
            return ""
        text = md
        # Link'leri temizle [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Liste maddeleri ("* **Fix** ..."): once soyulmazsa bold deseni "* **" ile
        # eslesip "Fix**" artigi birakiyordu (2026-10-08, LiteLLM/Keycloak notlari)
        text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
        # Bold/italic
        text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
        # Headers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Code blocks
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Fazla bosluklar
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


# ============================================================
# 1. MinIO — GitHub Releases API
# ============================================================
class MinIOScraper(DevToolsScraper):
    """MinIO GitHub Releases scraper"""

    API_URL = "https://api.github.com/repos/minio/minio/releases"

    def fetch_entries(self, days: int = 60) -> List[Dict]:
        log.info(f"[MinIO] Son {days} gunun guncellemeleri cekiliyor...")
        entries = []
        cutoff = datetime.now() - timedelta(days=days)
        try:
            resp = self.session.get(self.API_URL, params={'per_page': 15}, timeout=20)
            resp.raise_for_status()
            releases = resp.json()
            log.info(f"  [MinIO] {len(releases)} release bulundu")
            for rel in releases:
                pub_date = self._parse_rss_date(rel.get('published_at', ''))
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue
                title = rel.get('name', '') or rel.get('tag_name', '')
                body = self._markdown_to_text(rel.get('body', ''))
                link = rel.get('html_url', '')
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                entries.append({
                    'title': f"MinIO {title}",
                    'description': body[:4000] if body else title,
                    'link': link,
                    'date': date_str,
                    'source': 'MinIO',
                    'version': rel.get('tag_name', ''),
                    'entry_type': 'release',
                })
        except Exception as e:
            log.warning(f"[MinIO] Hata: {e}")
        log.info(f"[MinIO] {len(entries)} guncelleme bulundu")
        return entries


# ============================================================
# 2. Seq — Datalust Blog RSS
# ============================================================
class SeqScraper(DevToolsScraper):
    """Seq (Datalust) Blog RSS scraper — release haberleri"""

    FEED_URL = "https://blog.datalust.co/rss/"

    def fetch_entries(self, days: int = 60) -> List[Dict]:
        log.info(f"[Seq] Son {days} gunun guncellemeleri cekiliyor (RSS)...")
        entries = []
        cutoff = datetime.now() - timedelta(days=days)
        try:
            resp = self.session.get(self.FEED_URL, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'xml')
            items = soup.find_all('item')
            log.info(f"  [Seq] RSS'te {len(items)} paylasim bulundu")
            for item in items:
                title = item.find('title')
                title_text = title.get_text(strip=True) if title else ''
                if not title_text:
                    continue
                # Release ve update ile ilgili olanlari filtrele
                title_lower = title_text.lower()
                is_release = any(kw in title_lower for kw in [
                    'seq 20', 'release', 'update', 'announcing', 'preview',
                    'engineering update', 'what\'s new',
                ])
                if not is_release:
                    continue
                pub_tag = item.find('pubDate')
                pub_date = self._parse_rss_date(pub_tag.get_text(strip=True)) if pub_tag else None
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue
                link_tag = item.find('link')
                link = link_tag.get_text(strip=True) if link_tag else ''
                if link and link.startswith('/'):
                    link = f"https://blog.datalust.co{link}"
                content_tag = item.find('content:encoded') or item.find('encoded')
                description = ''
                if content_tag:
                    description = self._html_to_text(content_tag.get_text())
                if not description:
                    desc_tag = item.find('description')
                    description = self._html_to_text(desc_tag.get_text()) if desc_tag else title_text
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                # Versiyon cikarma
                version_match = re.search(r'Seq\s+(\d{4}\.\d+)', title_text)
                version = version_match.group(1) if version_match else ''
                entries.append({
                    'title': title_text,
                    'description': description[:4000],
                    'link': link,
                    'date': date_str,
                    'source': 'Seq',
                    'version': version,
                    'entry_type': 'release' if 'release' in title_lower else 'blog',
                })
        except Exception as e:
            log.warning(f"[Seq] RSS hatasi: {e}")
        log.info(f"[Seq] {len(entries)} guncelleme bulundu")
        return entries


# ============================================================
# 3. Ceph — GitHub Releases Atom
# ============================================================
class CephScraper(DevToolsScraper):
    """Ceph GitHub Releases Atom feed scraper"""

    ATOM_URL = "https://github.com/ceph/ceph/releases.atom"

    def fetch_entries(self, days: int = 60) -> List[Dict]:
        log.info(f"[Ceph] Son {days} gunun guncellemeleri cekiliyor (Atom)...")
        entries = []
        cutoff = datetime.now() - timedelta(days=days)
        try:
            resp = self.session.get(self.ATOM_URL, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'xml')
            atom_entries = soup.find_all('entry')
            log.info(f"  [Ceph] Atom feed'de {len(atom_entries)} release bulundu")
            for entry in atom_entries:
                title_tag = entry.find('title')
                title = title_tag.get_text(strip=True) if title_tag else ''
                if not title:
                    continue
                updated_tag = entry.find('updated')
                pub_date = self._parse_rss_date(updated_tag.get_text(strip=True)) if updated_tag else None
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue
                link_tag = entry.find('link')
                link = link_tag.get('href', '') if link_tag else ''
                content_tag = entry.find('content')
                description = self._html_to_text(content_tag.get_text()) if content_tag else title
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                entries.append({
                    'title': f"Ceph {title}",
                    'description': description[:4000] if description else f"Ceph {title} released",
                    'link': link,
                    'date': date_str,
                    'source': 'Ceph',
                    'version': title,
                    'entry_type': 'release',
                })
        except Exception as e:
            log.warning(f"[Ceph] Atom hatasi: {e}")
        log.info(f"[Ceph] {len(entries)} guncelleme bulundu")
        return entries


# ============================================================
# 4. MongoDB — GitHub Tags Atom + resmi surum notlari
# ============================================================
class MongoDBScraper(DevToolsScraper):
    """MongoDB sunucu surumleri: GitHub tags Atom akisi + mongodb.com surum notlari.

    2026-10-08: blog RSS'i (mongodb.com/company/blog/rss) Haziran 2026'da donmus ve
    surum yazisi tasimiyordu (60 gunde 0 kayit, veritabaninda hic MongoDB kaydi yoktu).
    tags.atom API limitine girmez; yalniz stabil tag'ler (rX.Y.Z; alpha/rc elenir).
    Aciklama, mongodb.com/docs/manual/release-notes/<X.Y>/ sayfasindaki
    "X.Y.Z - <tarih>" basligi altindaki notlardan alinir (sayfa seri basina bir kez cekilir).
    """

    TAGS_ATOM = "https://github.com/mongodb/mongo/tags.atom"
    RELEASE_NOTES_URL = "https://www.mongodb.com/docs/manual/release-notes/{seri}/"
    STABIL_TAG = re.compile(r'^r(\d+\.\d+\.\d+)$')

    def __init__(self):
        super().__init__()
        self._notes_cache = {}  # seri (8.0, 8.3...) basina sayfa; ornek omrunde, worker omrunde degil

    def _surum_notu(self, version: str) -> str:
        seri = '.'.join(version.split('.')[:2])
        url = self.RELEASE_NOTES_URL.format(seri=seri)
        try:
            if url not in self._notes_cache:
                resp = self.session.get(url, timeout=30)
                self._notes_cache[url] = resp.content if resp.ok else b''
            if not self._notes_cache[url]:
                return ''
            soup = BeautifulSoup(self._notes_cache[url], 'html.parser')
            for heading in soup.find_all(['h2', 'h3']):
                metin = heading.get_text(strip=True)
                if not (metin == version or metin.startswith(f"{version} ")):
                    continue
                # Sphinx/Snooty: <section><h3>8.0.34 - Sept 24, 2026</h3><p>..</p>..</section>
                parent = heading.parent
                if parent is not None and parent.name == 'section':
                    parts = [sib.get_text(' ', strip=True) for sib in heading.find_next_siblings()
                             if sib.name not in ('h2', 'h3', 'section')]
                else:
                    parts = []
                    for sib in heading.find_next_siblings():
                        if sib.name in ('h2', 'h3'):
                            break
                        parts.append(sib.get_text(' ', strip=True))
                text = re.sub(r'\n{3,}', '\n\n', '\n'.join(p for p in parts if p))
                if len(text) > 50:
                    log.info(f"    [MongoDB] {version} icin {len(text)} karakter surum notu bulundu")
                    return text
                return ''
        except Exception as e:
            log.warning(f"    [MongoDB] Surum notu cekilemedi ({version}): {e}")
        return ''

    def fetch_entries(self, days: int = 60) -> List[Dict]:
        log.info(f"[MongoDB] Son {days} gunun surumleri cekiliyor (GitHub tags Atom)...")
        entries = []
        cutoff = datetime.now() - timedelta(days=days)
        try:
            resp = self.session.get(self.TAGS_ATOM, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'xml')
            atom_entries = soup.find_all('entry')
            log.info(f"  [MongoDB] Atom feed'de {len(atom_entries)} tag bulundu")
            for entry in atom_entries:
                title_tag = entry.find('title')
                tag = title_tag.get_text(strip=True) if title_tag else ''
                match = self.STABIL_TAG.match(tag)
                if not match:
                    continue
                version = match.group(1)
                updated_tag = entry.find('updated')
                pub_date = self._parse_rss_date(updated_tag.get_text(strip=True)) if updated_tag else None
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue
                link_tag = entry.find('link')
                link = link_tag.get('href', '') if link_tag else ''
                if not link:
                    continue
                seri = '.'.join(version.split('.')[:2])
                notes_url = self.RELEASE_NOTES_URL.format(seri=seri)
                description = self._surum_notu(version) or (
                    f"MongoDB {version} has been tagged. Release notes: {notes_url}")
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                entries.append({
                    'title': f"MongoDB {version}",
                    'description': description[:4000],
                    'link': link,
                    'date': date_str,
                    'source': 'MongoDB',
                    'version': version,
                    'entry_type': 'release',
                })
        except Exception as e:
            log.warning(f"[MongoDB] Atom hatasi: {e}")
        log.info(f"[MongoDB] {len(entries)} guncelleme bulundu")
        return entries


# ============================================================
# 5. PostgreSQL — Resmi News RSS
# ============================================================
class PostgreSQLScraper(DevToolsScraper):
    """PostgreSQL resmi news RSS scraper"""

    FEED_URL = "https://www.postgresql.org/news.rss"

    def fetch_entries(self, days: int = 60) -> List[Dict]:
        log.info(f"[PostgreSQL] Son {days} gunun guncellemeleri cekiliyor (RSS)...")
        entries = []
        cutoff = datetime.now() - timedelta(days=days)
        try:
            resp = self.session.get(self.FEED_URL, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'xml')
            items = soup.find_all('item')
            log.info(f"  [PostgreSQL] RSS'te {len(items)} haber bulundu")
            for item in items:
                title = item.find('title')
                title_text = title.get_text(strip=True) if title else ''
                if not title_text:
                    continue
                pub_tag = item.find('pubDate')
                pub_date = self._parse_rss_date(pub_tag.get_text(strip=True)) if pub_tag else None
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue
                link_tag = item.find('link')
                link = link_tag.get_text(strip=True) if link_tag else ''
                desc_tag = item.find('description')
                description = self._html_to_text(desc_tag.get_text()) if desc_tag else title_text
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', title_text)
                version = version_match.group(1) if version_match else ''
                title_lower = title_text.lower()
                entry_type = 'release' if any(kw in title_lower for kw in ['released', 'release', 'update']) else 'news'
                entries.append({
                    'title': title_text,
                    'description': description[:4000],
                    'link': link,
                    'date': date_str,
                    'source': 'PostgreSQL',
                    'version': version,
                    'entry_type': entry_type,
                })
        except Exception as e:
            log.warning(f"[PostgreSQL] RSS hatasi: {e}")
        log.info(f"[PostgreSQL] {len(entries)} guncelleme bulundu")
        return entries


# ============================================================
# 6. RabbitMQ — GitHub Releases API
# ============================================================
class RabbitMQScraper(DevToolsScraper):
    """RabbitMQ GitHub Releases scraper"""

    API_URL = "https://api.github.com/repos/rabbitmq/rabbitmq-server/releases"

    def fetch_entries(self, days: int = 60) -> List[Dict]:
        log.info(f"[RabbitMQ] Son {days} gunun guncellemeleri cekiliyor...")
        entries = []
        cutoff = datetime.now() - timedelta(days=days)
        try:
            resp = self.session.get(self.API_URL, params={'per_page': 15}, timeout=20)
            resp.raise_for_status()
            releases = resp.json()
            log.info(f"  [RabbitMQ] {len(releases)} release bulundu")
            for rel in releases:
                if rel.get('prerelease', False):
                    continue
                pub_date = self._parse_rss_date(rel.get('published_at', ''))
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue
                raw_title = rel.get('name', '') or rel.get('tag_name', '')
                body = self._markdown_to_text(rel.get('body', ''))
                link = rel.get('html_url', '')
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                title = raw_title if raw_title.lower().startswith('rabbitmq') else f"RabbitMQ {raw_title}"
                entries.append({
                    'title': title,
                    'description': body[:4000] if body else f"{title} released",
                    'link': link,
                    'date': date_str,
                    'source': 'RabbitMQ',
                    'version': rel.get('tag_name', ''),
                    'entry_type': 'release',
                })
        except Exception as e:
            log.warning(f"[RabbitMQ] Hata: {e}")
        log.info(f"[RabbitMQ] {len(entries)} guncelleme bulundu")
        return entries


# ============================================================
# 7. Elasticsearch + Kibana — Resmi Release Notes sayfasindan
# ============================================================
class ElasticScraper(DevToolsScraper):
    """Elasticsearch + Kibana — elastic.co release notes sayfasindan detayli changelog cekilir"""

    ES_API = "https://api.github.com/repos/elastic/elasticsearch/releases"
    KIBANA_API = "https://api.github.com/repos/elastic/kibana/releases"
    ES_RELEASE_NOTES_URL = "https://www.elastic.co/docs/release-notes/elasticsearch"
    KIBANA_RELEASE_NOTES_URL = "https://www.elastic.co/docs/release-notes/kibana"

    def __init__(self):
        super().__init__()
        # Ornek duzeyinde: sinif duzeyinde tutulsaydi Celery worker surecinin omru
        # boyunca kalir, yeni surumlerin notlari bayat sayfadan aranirdi (2026-10-08).
        self._release_notes_cache = {}

    def _fetch_release_notes_section(self, url: str, version_tag: str) -> str:
        """elastic.co release notes sayfasindan belirli bir versiyonun notlarini cikar.
        Sayfa tek bir <section> icinde tum versiyonlari barindirir.
        h2 elementleri versiyon basliklarini, aralarindaki icerik release notlarini icerir."""
        try:
            version = version_tag.lstrip('v')
            # Sayfa cache'i — ayni sayfayi tekrar tekrar cekmeyelim
            if url not in self._release_notes_cache:
                resp = self.session.get(url, timeout=30)
                if not resp.ok:
                    return ""
                self._release_notes_cache[url] = resp.content
            soup = BeautifulSoup(self._release_notes_cache[url], 'html.parser')

            # h2'lerden versiyonumuzu bul
            target_h2 = None
            for h2 in soup.find_all('h2'):
                if h2.get_text(strip=True) == version:
                    target_h2 = h2
                    break
            if not target_h2:
                return ""

            # h2'nin heading-wrapper parent'indan sonraki sibling'leri topla
            # ta ki bir sonraki h2'ye kadar
            start = target_h2.parent if target_h2.parent.name == 'div' else target_h2
            content_parts = []
            for sib in start.find_next_siblings():
                # Eger bu sibling icinde bir h2 varsa ve farkli bir versiyon ise dur
                inner_h2 = sib.find('h2') if hasattr(sib, 'find') else None
                if inner_h2:
                    inner_text = inner_h2.get_text(strip=True)
                    if re.match(r'\d+\.\d+', inner_text) and inner_text != version:
                        break
                # Eger sibling kendisi h2 ise
                if hasattr(sib, 'name') and sib.name == 'h2':
                    sib_text = sib.get_text(strip=True)
                    if re.match(r'\d+\.\d+', sib_text) and sib_text != version:
                        break
                text = sib.get_text(separator='\n', strip=True) if hasattr(sib, 'get_text') else str(sib).strip()
                if text:
                    content_parts.append(text)

            result = '\n'.join(content_parts)
            result = re.sub(r'\n{3,}', '\n\n', result)
            if len(result) > 100:
                log.info(f"    [Elastic] {version} icin {len(result)} karakter release notes bulundu")
                return result
            return ""
        except Exception as e:
            log.warning(f"    [Elastic] Release notes cekilemedi ({version_tag}): {e}")
            return ""

    def fetch_entries(self, days: int = 60) -> List[Dict]:
        log.info(f"[Elastic] Son {days} gunun guncellemeleri cekiliyor...")
        entries = []
        cutoff = datetime.now() - timedelta(days=days)

        # Elasticsearch releases — once API'den listeyi al
        try:
            resp = self.session.get(self.ES_API, params={'per_page': 10}, timeout=20)
            resp.raise_for_status()
            releases = resp.json()
            log.info(f"  [Elasticsearch] {len(releases)} release bulundu")
            for rel in releases:
                pub_date = self._parse_rss_date(rel.get('published_at', ''))
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue
                raw_title = rel.get('name', '') or rel.get('tag_name', '')
                tag = rel.get('tag_name', '')
                link = rel.get('html_url', '')
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                # Baslikta "Elasticsearch" zaten varsa tekrar ekleme
                title = raw_title if raw_title.lower().startswith('elasticsearch') else f"Elasticsearch {raw_title}"

                # Resmi release notes sayfasindan detayli changelog cek
                description = self._fetch_release_notes_section(self.ES_RELEASE_NOTES_URL, tag)
                if not description:
                    # Fallback: GitHub body
                    description = self._markdown_to_text(rel.get('body', ''))
                if not description:
                    description = f"{title} released. See release notes at elastic.co for details."

                entries.append({
                    'title': title,
                    'description': description[:8000],
                    'link': link,
                    'date': date_str,
                    'source': 'Elastic',
                    'version': tag,
                    'entry_type': 'release',
                })
        except Exception as e:
            log.warning(f"[Elasticsearch] Hata: {e}")

        # Kibana releases (sadece ES'te olmayanlari ekle)
        es_versions = {e['version'] for e in entries}
        try:
            resp = self.session.get(self.KIBANA_API, params={'per_page': 10}, timeout=20)
            resp.raise_for_status()
            releases = resp.json()
            log.info(f"  [Kibana] {len(releases)} release bulundu")
            for rel in releases:
                tag = rel.get('tag_name', '')
                if tag in es_versions:
                    continue
                pub_date = self._parse_rss_date(rel.get('published_at', ''))
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue
                raw_title = rel.get('name', '') or tag
                link = rel.get('html_url', '')
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                title = raw_title if raw_title.lower().startswith('kibana') else f"Kibana {raw_title}"

                # Kibana release notes
                description = self._fetch_release_notes_section(self.KIBANA_RELEASE_NOTES_URL, tag)
                if not description:
                    description = self._markdown_to_text(rel.get('body', ''))
                if not description:
                    description = f"{title} released. See release notes at elastic.co for details."

                entries.append({
                    'title': title,
                    'description': description[:8000],
                    'link': link,
                    'date': date_str,
                    'source': 'Elastic',
                    'version': tag,
                    'entry_type': 'release',
                })
        except Exception as e:
            log.warning(f"[Kibana] Hata: {e}")

        log.info(f"[Elastic] {len(entries)} guncelleme bulundu")
        return entries


# ============================================================
# 8. Redis — Blog RSS + tam makale icerigi
# ============================================================
class RedisScraper(DevToolsScraper):
    """Redis Blog RSS scraper — blog sayfasina girip tam icerik cekilir"""

    FEED_URL = "https://redis.io/blog/feed"

    def _fetch_full_article(self, url: str) -> str:
        """Redis blog sayfasina gidip tam makale icerigini ceker.
        Redis blog icerigi [class*='blockContent'] div'inde bulunur."""
        try:
            resp = self.session.get(url, timeout=20)
            if not resp.ok:
                return ""
            soup = BeautifulSoup(resp.content, 'html.parser')

            # Redis blog icerigi blockContent class'li div'de
            article = soup.select_one('[class*="blockContent"]')

            # Fallback: diger olasi container'lar
            if not article:
                for selector in ['article', '[class*="content__"]', 'main']:
                    article = soup.select_one(selector)
                    if article and len(article.get_text(strip=True)) > 500:
                        break
                    article = None

            if not article:
                return ""

            # Navigation, header, footer, sidebar vs. kaldir
            for tag in article.find_all(['nav', 'header', 'footer', 'aside',
                                          'script', 'style', 'noscript']):
                tag.decompose()

            text = article.get_text(separator='\n', strip=True)
            # Gereksiz satirlari temizle
            lines = text.split('\n')
            clean_lines = []
            for line in lines:
                line = line.strip()
                if len(line) < 3:
                    continue
                # Menu/nav satirlarini atla
                if line in ['Search', 'Login', 'Try Redis', 'Book a meeting',
                            'Back to blog', 'Try for free', 'Talk to sales',
                            'Get started with Redis today']:
                    continue
                clean_lines.append(line)
            result = '\n'.join(clean_lines)
            result = re.sub(r'\n{3,}', '\n\n', result)

            if len(result) > 200:
                log.info(f"    [Redis] Tam makale cekildi: {len(result)} karakter")
                return result
            return ""
        except Exception as e:
            log.warning(f"    [Redis] Makale cekilemedi: {e}")
            return ""

    def fetch_entries(self, days: int = 60) -> List[Dict]:
        log.info(f"[Redis] Son {days} gunun guncellemeleri cekiliyor (RSS + tam icerik)...")
        entries = []
        cutoff = datetime.now() - timedelta(days=days)
        try:
            resp = self.session.get(self.FEED_URL, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'xml')
            items = soup.find_all('item')
            log.info(f"  [Redis] RSS'te {len(items)} paylasim bulundu")
            for item in items:
                title = item.find('title')
                title_text = title.get_text(strip=True) if title else ''
                if not title_text:
                    continue
                title_lower = title_text.lower()
                is_relevant = any(kw in title_lower for kw in [
                    'announcing redis', 'redis', 'release', 'update',
                    'what\'s new', 'security', 'patch',
                ])
                if not is_relevant:
                    continue
                pub_tag = item.find('pubDate')
                pub_date = self._parse_rss_date(pub_tag.get_text(strip=True)) if pub_tag else None
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue
                link_tag = item.find('link')
                link = link_tag.get_text(strip=True) if link_tag else ''
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                version_match = re.search(r'Redis\s+(\d+\.\d+(?:\.\d+)?)', title_text, re.IGNORECASE)
                version = version_match.group(1) if version_match else ''

                # Tam makale icerigini blog sayfasindan cek
                description = ''
                if link:
                    description = self._fetch_full_article(link)
                # Fallback: RSS description
                if not description or len(description) < 200:
                    desc_tag = item.find('description')
                    description = self._html_to_text(desc_tag.get_text()) if desc_tag else title_text

                entries.append({
                    'title': title_text,
                    'description': description[:8000],
                    'link': link,
                    'date': date_str,
                    'source': 'Redis',
                    'version': version,
                    'entry_type': 'release' if 'announcing' in title_lower or 'release' in title_lower else 'blog',
                })
        except Exception as e:
            log.warning(f"[Redis] RSS hatasi: {e}")
        log.info(f"[Redis] {len(entries)} guncelleme bulundu")
        return entries


# ============================================================
# 9. Moodle — GitHub Tags API + moodledev.io release notes
# ============================================================
class MoodleScraper(DevToolsScraper):
    """Moodle GitHub Tags + moodledev.io release notes scraper"""

    TAGS_API = "https://api.github.com/repos/moodle/moodle/tags"

    def _fetch_release_notes(self, version: str) -> str:
        """moodledev.io'dan belirli bir Moodle versiyonunun release notlarini ceker
        URL format: https://moodledev.io/general/releases/{major}.{minor}/{version}
        Ornek: 5.1.3 -> https://moodledev.io/general/releases/5.1/5.1.3
        """
        try:
            parts = version.split('.')
            if len(parts) < 3:
                return ""
            major_minor = f"{parts[0]}.{parts[1]}"
            url = f"https://moodledev.io/general/releases/{major_minor}/{version}"
            log.info(f"    [Moodle] Release notes cekiliyor: {url}")
            resp = self.session.get(url, timeout=20)
            if not resp.ok:
                log.warning(f"    [Moodle] Sayfa acilamadi: HTTP {resp.status_code}")
                return ""
            soup = BeautifulSoup(resp.content, 'html.parser')
            # Ana icerik alani
            article = soup.select_one('article') or soup.select_one('.markdown') or soup.select_one('main')
            if not article:
                return ""
            # Navigation, footer vb. kaldir
            for tag in article.find_all(['nav', 'header', 'footer', 'aside', 'script', 'style']):
                tag.decompose()
            text = article.get_text(separator='\n', strip=True)
            # Gereksiz baslik/menu satirlarini temizle
            lines = text.split('\n')
            clean_lines = []
            skip_patterns = ['Edit this page', 'Last updated on', 'Previous', 'Next',
                             'Tags:', 'Release notes', 'Moodle 5.', 'Moodle 4.']
            content_started = False
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Baslik satiri (Release date iceren) content baslasin
                if 'Release date' in line:
                    content_started = True
                    clean_lines.append(line)
                    continue
                if not content_started:
                    # Ust baslik veya sayfa title'i
                    if line.startswith('Moodle') and 'Released' not in line and len(line) < 30:
                        content_started = True
                    continue
                # Footer satirlarini atla
                if any(skip in line for skip in skip_patterns):
                    continue
                clean_lines.append(line)
            result = '\n'.join(clean_lines)
            result = re.sub(r'\n{3,}', '\n\n', result)
            if len(result) > 50:
                log.info(f"    [Moodle] {version} icin {len(result)} karakter release notes bulundu")
                return result
            return ""
        except Exception as e:
            log.warning(f"    [Moodle] Release notes cekilemedi ({version}): {e}")
            return ""

    def fetch_entries(self, days: int = 60) -> List[Dict]:
        log.info(f"[Moodle] Son {days} gunun guncellemeleri cekiliyor...")
        entries = []

        # GitHub Tags — son stabil versiyonlar
        try:
            resp = self.session.get(self.TAGS_API, params={'per_page': 20}, timeout=20)
            resp.raise_for_status()
            tags = resp.json()
            log.info(f"  [Moodle] {len(tags)} tag bulundu")

            stable_tags = []
            for tag in tags:
                name = tag.get('name', '')
                # Sadece stabil versiyonlar (beta, rc, dev, weekly haric)
                if re.match(r'^v\d+\.\d+\.\d+$', name):
                    stable_tags.append(name)

            # Son 5 stabil tag
            for tag_name in stable_tags[:5]:
                # Tag commit tarihini cek
                commit_url = None
                for tag in tags:
                    if tag.get('name') == tag_name:
                        commit_url = tag.get('commit', {}).get('url', '')
                        break

                pub_date = None
                if commit_url:
                    try:
                        commit_resp = self.session.get(commit_url, timeout=10)
                        if commit_resp.ok:
                            commit_data = commit_resp.json()
                            date_str_raw = commit_data.get('commit', {}).get('committer', {}).get('date', '')
                            pub_date = self._parse_rss_date(date_str_raw)
                    except Exception:
                        pass

                cutoff = datetime.now() - timedelta(days=days)
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue

                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                version = tag_name.lstrip('v')

                # moodledev.io'dan gercek release notes cek
                description = self._fetch_release_notes(version)
                if not description:
                    description = f"Moodle {version} has been released. Visit https://moodledev.io/general/releases for details, changelog, and security fixes."

                release_notes_url = f"https://moodledev.io/general/releases/{'.'.join(version.split('.')[:2])}/{version}"

                entries.append({
                    'title': f"Moodle {version} Released",
                    'description': description[:8000],
                    'link': release_notes_url,
                    'date': date_str,
                    'source': 'Moodle',
                    'version': version,
                    'entry_type': 'release',
                })
        except Exception as e:
            log.warning(f"[Moodle] Tags hatasi: {e}")

        log.info(f"[Moodle] {len(entries)} guncelleme bulundu")
        return entries


# ============================================================
# 10-13. GitHub Releases API — ortak sinif (LiteLLM, LangGraph, Langfuse, Keycloak)
# ============================================================
class GitHubReleasesScraper(DevToolsScraper):
    """GitHub Releases API tabanli genel scraper.

    `tag_deseni` ile eslesmeyen tag'ler (dev, rc, nightly, alt paketler) ve on
    surumler (prerelease/draft) elenir. Baslik release adindan gelir; kaynak adiyla
    baslamiyorsa onune eklenir. "paket==1.2.3" bicimli adlar "paket 1.2.3" olur.
    """

    def __init__(self, source: str, repo: str, tag_deseni: str, per_page: int = 20):
        super().__init__()
        self.source = source
        self.repo = repo
        self.tag_deseni = re.compile(tag_deseni)
        self.per_page = per_page

    @property
    def api_url(self) -> str:
        return f"{self.GITHUB_API}repos/{self.repo}/releases"

    def _baslik(self, rel: Dict) -> str:
        ad = (rel.get('name') or rel.get('tag_name') or '').strip().replace('==', ' ')
        if ad.lower().startswith(self.source.lower()):
            return ad
        return f"{self.source} {ad}"

    def fetch_entries(self, days: int = 60) -> List[Dict]:
        log.info(f"[{self.source}] Son {days} gunun guncellemeleri cekiliyor (GitHub Releases)...")
        entries = []
        cutoff = datetime.now() - timedelta(days=days)
        try:
            resp = self._github_get(self.api_url, params={'per_page': self.per_page}, timeout=20)
            resp.raise_for_status()
            releases = resp.json()
            log.info(f"  [{self.source}] {len(releases)} release bulundu")
            for rel in releases:
                tag = rel.get('tag_name', '') or ''
                if rel.get('prerelease') or rel.get('draft') or not self.tag_deseni.match(tag):
                    continue
                pub_date = self._parse_rss_date(rel.get('published_at', ''))
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue
                title = self._baslik(rel)
                body = self._markdown_to_text(rel.get('body', ''))
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                entries.append({
                    'title': title,
                    'description': body[:4000] if body else f"{title} released",
                    'link': rel.get('html_url', ''),
                    'date': date_str,
                    'source': self.source,
                    'version': tag,
                    'entry_type': 'release',
                })
        except Exception as e:
            log.warning(f"[{self.source}] Hata: {e}")
        log.info(f"[{self.source}] {len(entries)} guncelleme bulundu")
        return entries


# ============================================================
# 14. GitLab — docs.gitlab.com resmi surum notlari Atom
# ============================================================
class GitLabScraper(DevToolsScraper):
    """GitLab ay surumleri ve yama surumleri (docs.gitlab.com/releases/all-releases.xml).

    gitlab.com/api/v4 anonim istege 403 donuyor, about.gitlab.com blog akisi yalniz
    son 20 yaziyi tasiyor (2026-10-08). Resmi surum akisi tam HTML icerik verir.
    """

    FEED_URL = "https://docs.gitlab.com/releases/all-releases.xml"

    def fetch_entries(self, days: int = 60) -> List[Dict]:
        log.info(f"[GitLab] Son {days} gunun surumleri cekiliyor (Atom)...")
        entries = []
        cutoff = datetime.now() - timedelta(days=days)
        try:
            resp = self.session.get(self.FEED_URL, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'xml')
            atom_entries = soup.find_all('entry')
            log.info(f"  [GitLab] Atom feed'de {len(atom_entries)} surum bulundu")
            for entry in atom_entries:
                title_tag = entry.find('title')
                title = title_tag.get_text(strip=True) if title_tag else ''
                if not title:
                    continue
                pub_tag = entry.find('published') or entry.find('updated')
                pub_date = self._parse_rss_date(pub_tag.get_text(strip=True)) if pub_tag else None
                if pub_date and pub_date.replace(tzinfo=None) < cutoff:
                    continue
                link_tag = entry.find('link')
                link = link_tag.get('href', '') if link_tag else ''
                if not link:
                    continue
                content_tag = entry.find('content')
                description = self._html_to_text(content_tag.get_text()) if content_tag else title
                version_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', title)
                date_str = pub_date.strftime('%Y-%m-%d') if pub_date else datetime.now().strftime('%Y-%m-%d')
                entries.append({
                    'title': title if title.lower().startswith('gitlab') else f"GitLab {title}",
                    'description': description[:4000] if description else title,
                    'link': link,
                    'date': date_str,
                    'source': 'GitLab',
                    'version': version_match.group(1) if version_match else '',
                    'entry_type': 'release',
                })
        except Exception as e:
            log.warning(f"[GitLab] Atom hatasi: {e}")
        log.info(f"[GitLab] {len(entries)} guncelleme bulundu")
        return entries


# ============================================================
# Multi DevTools Scraper — Tum kaynaklari birlestiren sinif
# ============================================================
class MultiDevToolsScraper(DevToolsScraper):
    """Tum DevTools kaynaklarini birlestiren scraper"""

    def __init__(self):
        super().__init__()
        self.scrapers = {
            'MinIO': MinIOScraper(),
            'Seq': SeqScraper(),
            'Ceph': CephScraper(),
            'MongoDB': MongoDBScraper(),
            'PostgreSQL': PostgreSQLScraper(),
            'RabbitMQ': RabbitMQScraper(),
            'Elastic': ElasticScraper(),
            'Redis': RedisScraper(),
            'Moodle': MoodleScraper(),
            # 2026-10-08: AI/platform araclari. LiteLLM gunde bircok dev/rc/backport
            # yayinlar; yalniz vX.Y.Z stabil tag'ler. LangGraph tek repoda cekirdek
            # (X.Y.Z), sdk== ve cli== paketlerini etiketler; checkpoint/prebuilt elenir.
            'LiteLLM': GitHubReleasesScraper('LiteLLM', 'BerriAI/litellm', r'^v\d+\.\d+\.\d+$', per_page=50),
            'LangGraph': GitHubReleasesScraper('LangGraph', 'langchain-ai/langgraph',
                                               r'^(\d+\.\d+\.\d+|(sdk|cli)==\d+\.\d+\.\d+)$', per_page=30),
            'Langfuse': GitHubReleasesScraper('Langfuse', 'langfuse/langfuse', r'^v\d+\.\d+\.\d+$'),
            'GitLab': GitLabScraper(),
            'Keycloak': GitHubReleasesScraper('Keycloak', 'keycloak/keycloak', r'^\d+\.\d+\.\d+$'),
        }

    def fetch_all(self, days: int = 60, selected_sources: list = None, max_total: int = 30) -> List[Dict]:
        all_entries = []

        sources = dict(self.scrapers)
        if selected_sources:
            selected_lower = {s.lower() for s in selected_sources}
            sources = {k: v for k, v in sources.items() if k.lower() in selected_lower}

        # 14 kaynakta sabit 30 tavan, gunluk yayinlayan LiteLLM/Langfuse'un aylik
        # yayinlayan Keycloak/GitLab'i tarih siralamasinda dusurmesine yol acardi.
        max_total = max(max_total, 3 * len(sources))

        log.info("=" * 80)
        log.info(f"TUM DEVTOOLS KAYNAKLARINDAN GUNCELLEME CEKILIYOR ({days} gun, maks {max_total})")
        log.info("=" * 80)

        per_source_limit = max(5, max_total // max(len(sources), 1))

        for source_name, scraper in sources.items():
            try:
                entries = scraper.fetch_entries(days=days)
                if len(entries) > per_source_limit:
                    entries = entries[:per_source_limit]
                    log.info(f"  -> {source_name}: {per_source_limit} guncelleme (sinirlandirildi)")
                else:
                    log.info(f"  -> {source_name}: {len(entries)} guncelleme")
                all_entries.extend(entries)
            except Exception as e:
                log.warning(f"  -> {source_name}: HATA - {e}")

        all_entries.sort(key=lambda x: x['date'], reverse=True)

        if len(all_entries) > max_total:
            all_entries = all_entries[:max_total]

        # Duplicate link kontrolu
        seen_links = set()
        unique = []
        for entry in all_entries:
            if entry['link'] not in seen_links:
                seen_links.add(entry['link'])
                unique.append(entry)

        log.info("=" * 80)
        log.info(f"TOPLAM {len(unique)} DEVTOOLS GUNCELLEMESI CEKILDI")
        log.info("=" * 80)
        return unique

    def process_entries(self, entries: List[Dict]) -> List[Dict]:
        """DevTools haberlerini Turkceye cevirir"""
        total = len(entries)
        log.info(f"\nDevTools guncellemeleri cevriliyor ({total} adet)...")

        for i, entry in enumerate(entries, 1):
            try:
                if i % 10 == 0:
                    log.info(f"  Cevriliyor: {i}/{total}")
                try:
                    translated_title = translate_text(entry['title'])
                except Exception:
                    translated_title = entry['title']
                translated_desc = translate_long_text(entry['description'])
                yield {
                    'original_title': entry['title'],
                    'turkish_title': translated_title,
                    'original_description': entry['description'],
                    'turkish_description': translated_desc,
                    'link': entry['link'],
                    'published_date': entry['date'],
                    'source': entry['source'],
                    'version': entry.get('version', ''),
                    'entry_type': entry.get('entry_type', 'release'),
                }
            except Exception as e:
                log.warning(f"  DevTools haber isleme hatasi: {e}")
                yield {
                    'original_title': entry['title'],
                    'turkish_title': entry['title'],
                    'original_description': entry['description'],
                    'turkish_description': entry['description'],
                    'link': entry['link'],
                    'published_date': entry['date'],
                    'source': entry['source'],
                    'version': entry.get('version', ''),
                    'entry_type': entry.get('entry_type', 'release'),
                }
        


if __name__ == "__main__":
    scraper = MultiDevToolsScraper()
    entries = scraper.fetch_all(days=60)
    print(f"\nToplam {len(entries)} DevTools guncellemesi cekildi")
    for e in entries[:15]:
        print(f"  [{e['source']:12s}] {e['date']} | {e.get('version',''):15s} | {e['title'][:55]}")
