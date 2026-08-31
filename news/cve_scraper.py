"""
CVE Scraper Module
NVD, CVEDetails, Rapid7, Tenable, VulDB gibi kaynaklardan CVE verilerini çeker.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
from typing import List, Dict, Optional
import time

from news.translation_utils import translate_text, translate_long_text
from news.base_scraper import BaseRSSScraper


class CVEScraper(BaseRSSScraper):
    """CVE Scraper temel sınıfı"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    def parse_cvss_score(self, severity_text: str) -> Optional[float]:
        """CVSS skorunu metinden çıkarır"""
        if not severity_text:
            return None
        
        match = re.search(r'(\d+\.?\d*)', severity_text)
        if match:
            try:
                score = float(match.group(1))
                if 0 <= score <= 10:
                    return score
            except:
                pass
        
        return None
    
    def get_severity_from_score(self, score: Optional[float]) -> str:
        """CVSS skorundan şiddet seviyesini belirler"""
        if score is None:
            return "Bilinmiyor"
        elif score >= 9.0:
            return "Kritik"
        elif score >= 7.0:
            return "Yüksek"
        elif score >= 4.0:
            return "Orta"
        else:
            return "Düşük"


class NVDScraper(CVEScraper):
    """NVD (National Vulnerability Database) scraper"""
    
    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    
    def fetch_cves(self, days: int = 30) -> List[Dict]:
        """NVD'den CVE verilerini çeker"""
        print(f"[NVD] Son {days} gunun CVE'leri cekiliyor...")
        
        cves = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            params = {
                'pubStartDate': start_date.strftime('%Y-%m-%dT00:00:00.000'),
                'pubEndDate': end_date.strftime('%Y-%m-%dT23:59:59.999'),
                'resultsPerPage': 100
            }
            
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if 'vulnerabilities' not in data:
                print("[NVD] Veri bulunamadi")
                return cves
            
            # NVD severity İngilizce -> Türkçe eşleme
            severity_tr = {
                'CRITICAL': 'Kritik',
                'HIGH': 'Yüksek',
                'MEDIUM': 'Orta',
                'LOW': 'Düşük',
            }

            skipped_rejected = 0
            skipped_no_cvss = 0

            for item in data['vulnerabilities']:
                try:
                    cve_data = item.get('cve', {})
                    cve_id = cve_data.get('id', '')
                    
                    if not cve_id:
                        continue
                    
                    # Reddedilmiş veya ayrılmış (reserved) durumunu kontrol et
                    vuln_status = cve_data.get('vulnStatus', '')
                    if vuln_status in ('Rejected', 'Reserved'):
                        skipped_rejected += 1
                        continue

                    descriptions = cve_data.get('descriptions', [])
                    description = ""
                    for desc in descriptions:
                        if desc.get('lang') == 'en':
                            description = desc.get('value', '')
                            break
                    
                    if not description:
                        description = descriptions[0].get('value', '') if descriptions else ''

                    # Rejected/Reserved açıklamaları filtrele
                    desc_lower = description.lower()
                    if any(reject_pattern in desc_lower for reject_pattern in [
                        'rejected reason', '** reserved **', '** reject **',
                        'this cve id has been rejected', 'not used',
                        'this candidate has been reserved',
                    ]):
                        skipped_rejected += 1
                        continue
                    
                    # Boş veya anlamsız açıklamaları filtrele
                    if not description or len(description.strip()) < 20:
                        skipped_rejected += 1
                        continue

                    cvss_score = None
                    severity = "Bilinmiyor"
                    
                    metrics = cve_data.get('metrics', {})
                    if 'cvssMetricV31' in metrics:
                        cvss_data = metrics['cvssMetricV31'][0].get('cvssData', {})
                        cvss_score = cvss_data.get('baseScore')
                        raw_severity = cvss_data.get('baseSeverity', '')
                        severity = severity_tr.get(raw_severity, self.get_severity_from_score(cvss_score))
                    elif 'cvssMetricV30' in metrics:
                        cvss_data = metrics['cvssMetricV30'][0].get('cvssData', {})
                        cvss_score = cvss_data.get('baseScore')
                        raw_severity = cvss_data.get('baseSeverity', '')
                        severity = severity_tr.get(raw_severity, self.get_severity_from_score(cvss_score))
                    elif 'cvssMetricV2' in metrics:
                        cvss_data = metrics['cvssMetricV2'][0].get('cvssData', {})
                        cvss_score = cvss_data.get('baseScore')
                        severity = self.get_severity_from_score(cvss_score)

                    # CVSS skoru olmayan (henüz analiz edilmemiş) CVE'leri atla
                    if cvss_score is None:
                        skipped_no_cvss += 1
                        continue
                    
                    references = []
                    for ref in cve_data.get('references', []):
                        if ref.get('url'):
                            references.append(ref['url'])
                    
                    cwe_ids = []
                    for weakness in cve_data.get('weaknesses', []):
                        for desc in weakness.get('description', []):
                            if desc.get('value', '').startswith('CWE-'):
                                cwe_ids.append(desc['value'])
                    
                    published = cve_data.get('published', '')
                    modified = cve_data.get('lastModified', '')
                    
                    try:
                        published_date = datetime.strptime(published[:10], '%Y-%m-%d').date() if published else datetime.now().date()
                    except:
                        published_date = datetime.now().date()
                    
                    try:
                        modified_date = datetime.strptime(modified[:10], '%Y-%m-%d').date() if modified else None
                    except:
                        modified_date = None
                    
                    cve = {
                        'cve_id': cve_id,
                        'source': 'NVD',
                        'original_title': f"{cve_id} - Güvenlik Açığı",
                        'original_description': description,
                        'severity': severity,
                        'cvss_score': cvss_score,
                        'published_date': published_date,
                        'modified_date': modified_date,
                        'link': f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                        'cwe_ids': cwe_ids,
                        'references': references[:5],
                        'affected_products': ''
                    }
                    
                    cves.append(cve)
                    
                except Exception as e:
                    print(f"[NVD] CVE işleme hatası: {e}")
                    continue
            
            print(f"[NVD] Atlanan: {skipped_rejected} reddedilmiş/ayrılmış, {skipped_no_cvss} CVSS'siz")
            
            print(f"[NVD] {len(cves)} CVE bulundu")
            
        except Exception as e:
            print(f"[NVD] Hata: {e}")
        
        return cves


class GitHubAdvisoryScraper(CVEScraper):
    """GitHub Advisory Database scraper - ücretsiz API, zengin CVE verisi"""
    
    API_URL = "https://api.github.com/advisories"
    
    SEVERITY_MAP = {
        'critical': ('Kritik', 9.5),
        'high': ('Yüksek', 7.5),
        'medium': ('Orta', 5.5),
        'low': ('Düşük', 2.5),
    }
    
    def fetch_cves(self, days: int = 30) -> List[Dict]:
        """GitHub Advisory Database'den CVE verilerini çeker"""
        print(f"[GitHub Advisory] Son {days} günün CVE'leri çekiliyor...")
        
        cves = []
        
        try:
            # Tarih filtresi
            since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT00:00:00Z')
            
            params = {
                'per_page': 50,
                'type': 'reviewed',
                'sort': 'published',
                'direction': 'desc',
                'published': f'>={since_date[:10]}',
            }
            
            response = self.session.get(self.API_URL, params=params, timeout=30)
            response.raise_for_status()
            
            advisories = response.json()
            
            for adv in advisories:
                try:
                    cve_id = adv.get('cve_id')
                    if not cve_id or not cve_id.startswith('CVE-'):
                        continue
                    
                    summary = adv.get('summary', '')
                    description = adv.get('description', '') or summary
                    
                    # CVSS skorunu çıkar
                    cvss_score = None
                    cvss_sev = adv.get('cvss_severities', {})
                    
                    # Önce v3, yoksa v4
                    v3 = cvss_sev.get('cvss_v3', {})
                    v4 = cvss_sev.get('cvss_v4', {})
                    
                    if v3 and v3.get('score') and v3['score'] > 0:
                        cvss_score = v3['score']
                    elif v4 and v4.get('score') and v4['score'] > 0:
                        cvss_score = v4['score']
                    else:
                        # Eski format
                        old_cvss = adv.get('cvss', {})
                        if old_cvss and old_cvss.get('score'):
                            cvss_score = old_cvss['score']
                    
                    # Severity
                    sev_text = adv.get('severity', '').lower()
                    severity_info = self.SEVERITY_MAP.get(sev_text, ('Bilinmiyor', None))
                    severity = severity_info[0]
                    
                    # CVSS skoru yoksa severity'den tahmin et
                    if cvss_score is None and severity_info[1]:
                        cvss_score = severity_info[1]
                    
                    # CVSS skoru hala yoksa atla
                    if cvss_score is None:
                        continue
                    
                    # Tarih
                    published = adv.get('published_at', '')
                    try:
                        pub_date = datetime.strptime(published[:10], '%Y-%m-%d').date()
                    except:
                        pub_date = datetime.now().date()
                    
                    # CWE'ler
                    cwe_ids = []
                    for cwe in adv.get('cwes', []):
                        cwe_id = cwe.get('cwe_id', '')
                        if cwe_id:
                            cwe_ids.append(cwe_id)
                    
                    # Etkilenen ürünler
                    affected = []
                    for vuln in adv.get('vulnerabilities', []):
                        pkg = vuln.get('package', {})
                        eco = pkg.get('ecosystem', '')
                        name = pkg.get('name', '')
                        if eco and name:
                            affected.append(f"{eco}:{name}")
                    
                    # Referanslar (GitHub API string listesi döner, dict değil)
                    raw_refs = adv.get('references', [])
                    references = []
                    for ref in raw_refs:
                        if isinstance(ref, str) and ref.startswith('http'):
                            references.append(ref)
                        elif isinstance(ref, dict) and ref.get('url'):
                            references.append(ref['url'])
                    
                    cve = {
                        'cve_id': cve_id,
                        'source': 'GitHub Advisory',
                        'original_title': f"{cve_id} - {summary[:80]}" if summary else f"{cve_id} - Güvenlik Açığı",
                        'original_description': description[:4000] if description else 'Açıklama bulunamadı',
                        'severity': severity,
                        'cvss_score': cvss_score,
                        'published_date': pub_date,
                        'modified_date': None,
                        'link': adv.get('html_url', f"https://nvd.nist.gov/vuln/detail/{cve_id}"),
                        'cwe_ids': cwe_ids,
                        'references': references[:5],
                        'affected_products': ', '.join(affected[:5])
                    }
                    
                    cves.append(cve)
                    
                except Exception as e:
                    print(f"[GitHub Advisory] CVE işleme hatası: {e}")
                    continue
            
            print(f"[GitHub Advisory] {len(cves)} CVE bulundu")
            
        except Exception as e:
            print(f"[GitHub Advisory] Hata: {e}")
        
        return cves


class TenableScraper(CVEScraper):
    """Tenable CVE scraper - __NEXT_DATA__ JSON ile parse eder"""
    
    BASE_URL = "https://www.tenable.com/cve"
    
    SEVERITY_MAP = {
        'critical': ('Kritik', 9.5),
        'high': ('Yüksek', 7.5),
        'medium': ('Orta', 5.5),
        'low': ('Düşük', 2.5),
    }
    
    def fetch_cves(self, days: int = 30) -> List[Dict]:
        """Tenable'dan CVE verilerini __NEXT_DATA__ JSON'dan çeker"""
        print(f"[Tenable] Son {days} günün CVE'leri çekiliyor...")
        
        cves = []
        
        try:
            response = self.session.get(self.BASE_URL, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # __NEXT_DATA__ JSON: tüm CVE verisi yapılandırılmış şekilde burada
            next_data_script = soup.find('script', id='__NEXT_DATA__')
            
            if next_data_script and next_data_script.string:
                data = json.loads(next_data_script.string)
                page_props = data.get('props', {}).get('pageProps', {})
                
                # newest + updated + vulnWatch listelerini birleştir
                all_entries = []
                all_entries.extend(page_props.get('newest', []))
                all_entries.extend(page_props.get('updated', []))
                all_entries.extend(page_props.get('vulnWatchCves', []))
                
                cutoff_date = (datetime.now() - timedelta(days=days)).date()
                seen_ids = set()
                
                for entry in all_entries:
                    try:
                        cve_id = entry.get('_id', '')
                        if not cve_id.startswith('CVE-') or cve_id in seen_ids:
                            continue
                        seen_ids.add(cve_id)
                        
                        source = entry.get('_source', {})
                        
                        description = source.get('description', '')
                        if not description or len(description.strip()) < 10:
                            continue
                        
                        # Severity: cvss3_severity > severity > cvss2_severity
                        sev_text = (
                            source.get('cvss3_severity') or
                            source.get('severity') or
                            source.get('cvss2_severity') or
                            ''
                        ).lower()
                        
                        sev_info = self.SEVERITY_MAP.get(sev_text, ('Bilinmiyor', None))
                        severity = sev_info[0]
                        cvss_score = sev_info[1]
                        
                        # CVSS skoru yoksa atla
                        if cvss_score is None:
                            continue
                        
                        # Tarih
                        pub_str = source.get('publication_date', '')
                        try:
                            pub_date = datetime.strptime(pub_str[:10], '%Y-%m-%d').date()
                            if pub_date < cutoff_date:
                                continue
                        except:
                            pub_date = datetime.now().date()
                        
                        cve = {
                            'cve_id': cve_id,
                            'source': 'Tenable',
                            'original_title': f"{cve_id} - Güvenlik Açığı",
                            'original_description': description[:4000],
                            'severity': severity,
                            'cvss_score': cvss_score,
                            'published_date': pub_date,
                            'modified_date': None,
                            'link': f"https://www.tenable.com/cve/{cve_id}",
                            'cwe_ids': [],
                            'references': [],
                            'affected_products': ''
                        }
                        
                        cves.append(cve)
                        
                    except Exception as e:
                        print(f"[Tenable] CVE işleme hatası: {e}")
                        continue
            else:
                print("[Tenable] __NEXT_DATA__ bulunamadı, HTML fallback deneniyor...")
                # Fallback: li.list-group-item parse
                items = soup.select('li.list-group-item')
                for item in items[:30]:
                    try:
                        link_tag = item.select_one('div.clearfix h5 a')
                        if not link_tag:
                            continue
                        cve_id = link_tag.text.strip()
                        if not cve_id.startswith('CVE-'):
                            continue
                        
                        # Description: <p> tag (clearfix'in kardeşi)
                        desc_p = item.find('p')
                        description = desc_p.text.strip() if desc_p else ''
                        if not description:
                            continue
                        
                        # Severity badge
                        sev_span = item.select_one('span.badge')
                        sev_text = sev_span.text.strip().lower() if sev_span else ''
                        sev_info = self.SEVERITY_MAP.get(sev_text, ('Bilinmiyor', None))
                        severity = sev_info[0]
                        cvss_score = sev_info[1]
                        
                        if cvss_score is None:
                            continue
                        
                        cve = {
                            'cve_id': cve_id,
                            'source': 'Tenable',
                            'original_title': f"{cve_id} - Güvenlik Açığı",
                            'original_description': description[:4000],
                            'severity': severity,
                            'cvss_score': cvss_score,
                            'published_date': datetime.now().date(),
                            'modified_date': None,
                            'link': f"https://www.tenable.com/cve/{cve_id}",
                            'cwe_ids': [],
                            'references': [],
                            'affected_products': ''
                        }
                        cves.append(cve)
                    except Exception as e:
                        print(f"[Tenable] Fallback CVE işleme hatası: {e}")
                        continue
            
            print(f"[Tenable] {len(cves)} CVE bulundu")
            
        except Exception as e:
            print(f"[Tenable] Hata: {e}")
        
        return cves


class CIRCLScraper(CVEScraper):
    """CIRCL (Computer Incident Response Center Luxembourg) CVE API scraper"""
    
    API_URL = "https://cve.circl.lu/api/last"
    
    def _parse_cvss_from_vector(self, vector: str) -> Optional[float]:
        """CVSS vektör dizesinden skor hesaplar (basit yaklaşım)"""
        if not vector:
            return None
        
        # Vektörden basit skor çıkarma
        score_match = re.search(r'baseScore[:\s]+(\d+\.?\d*)', vector)
        if score_match:
            return float(score_match.group(1))
        
        # V3/V4 vektöründen severity tahmin et
        if 'AV:N' in vector and 'AC:L' in vector:
            if 'PR:N' in vector and 'UI:N' in vector:
                return 9.0  # Network, Low complexity, No privileges, No interaction
            elif 'PR:N' in vector:
                return 7.5
            elif 'PR:L' in vector:
                return 6.5
        elif 'AV:N' in vector:
            return 5.5
        elif 'AV:L' in vector:
            return 4.0
        
        return None
    
    def fetch_cves(self, days: int = 30) -> List[Dict]:
        """CIRCL API'den son CVE'leri çeker"""
        print(f"[CIRCL] Son CVE'ler çekiliyor...")
        
        cves = []
        
        try:
            # Son 50 CVE'yi çek
            response = self.session.get(f"{self.API_URL}/50", timeout=30)
            response.raise_for_status()
            
            items = response.json()
            
            cutoff_date = (datetime.now() - timedelta(days=days)).date()
            
            for item in items:
                try:
                    cve_id = item.get('id', '')
                    
                    # GHSA ID'lerini atla, sadece CVE'leri al
                    if not cve_id.startswith('CVE-'):
                        # aliases'da CVE olabilir
                        aliases = item.get('aliases', [])
                        cve_found = None
                        for alias in aliases:
                            if alias.startswith('CVE-'):
                                cve_found = alias
                                break
                        if not cve_found:
                            continue
                        cve_id = cve_found
                    
                    # Açıklama
                    description = item.get('details', '') or item.get('summary', '')
                    if not description or len(description.strip()) < 20:
                        continue
                    
                    # Tarih
                    published = item.get('published', '')
                    try:
                        pub_date = datetime.strptime(published[:10], '%Y-%m-%d').date()
                        if pub_date < cutoff_date:
                            continue
                    except:
                        pub_date = datetime.now().date()
                    
                    # CVSS skoru
                    cvss_score = None
                    severity_list = item.get('severity', [])
                    for sev in severity_list:
                        score_str = sev.get('score', '')
                        parsed = self._parse_cvss_from_vector(score_str)
                        if parsed:
                            cvss_score = parsed
                            break
                    
                    # CVSS yoksa atla
                    if cvss_score is None:
                        continue
                    
                    severity = self.get_severity_from_score(cvss_score)
                    
                    # Referanslar
                    references = []
                    for ref in item.get('references', []):
                        url = ref.get('url', '')
                        if url:
                            references.append(url)
                    
                    cve = {
                        'cve_id': cve_id,
                        'source': 'CIRCL',
                        'original_title': f"{cve_id} - Güvenlik Açığı",
                        'original_description': description[:4000],
                        'severity': severity,
                        'cvss_score': cvss_score,
                        'published_date': pub_date,
                        'modified_date': None,
                        'link': f"https://cve.circl.lu/cve/{cve_id}",
                        'cwe_ids': [],
                        'references': references[:5],
                        'affected_products': ''
                    }
                    
                    cves.append(cve)
                    
                except Exception as e:
                    print(f"[CIRCL] CVE işleme hatası: {e}")
                    continue
            
            print(f"[CIRCL] {len(cves)} CVE bulundu")
            
        except Exception as e:
            print(f"[CIRCL] Hata: {e}")
        
        return cves


class NVDRecentScraper(CVEScraper):
    """NVD'den ek CVE'leri farklı parametrelerle çeker (Modified tarihine göre)"""
    
    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    
    def fetch_cves(self, days: int = 30) -> List[Dict]:
        """NVD'den son değiştirilen CVE'leri çeker"""
        print(f"[NVD Güncel] Son {days} günde değiştirilen CVE'ler çekiliyor...")
        
        cves = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        severity_tr = {
            'CRITICAL': 'Kritik',
            'HIGH': 'Yüksek',
            'MEDIUM': 'Orta',
            'LOW': 'Düşük',
        }
        
        try:
            # lastModified tarihine göre çek (published yerine)
            params = {
                'lastModStartDate': start_date.strftime('%Y-%m-%dT00:00:00.000'),
                'lastModEndDate': end_date.strftime('%Y-%m-%dT23:59:59.999'),
                'resultsPerPage': 50,
                'startIndex': 100,  # İlk 100'ü NVD scraper alıyor, bunlar farklı
            }
            
            # NVD rate limit - ilk scraper'dan sonra biraz bekle
            time.sleep(2)
            
            response = self.session.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if 'vulnerabilities' not in data:
                print("[NVD Güncel] Veri bulunamadı")
                return cves
            
            for item in data['vulnerabilities']:
                try:
                    cve_data = item.get('cve', {})
                    cve_id = cve_data.get('id', '')
                    
                    if not cve_id:
                        continue
                    
                    vuln_status = cve_data.get('vulnStatus', '')
                    if vuln_status in ('Rejected', 'Reserved'):
                        continue
                    
                    descriptions = cve_data.get('descriptions', [])
                    description = ""
                    for desc in descriptions:
                        if desc.get('lang') == 'en':
                            description = desc.get('value', '')
                            break
                    
                    if not description:
                        description = descriptions[0].get('value', '') if descriptions else ''
                    
                    desc_lower = description.lower()
                    if any(p in desc_lower for p in [
                        'rejected reason', '** reserved **', '** reject **',
                        'this cve id has been rejected', 'not used',
                        'this candidate has been reserved',
                    ]):
                        continue
                    
                    if not description or len(description.strip()) < 20:
                        continue
                    
                    cvss_score = None
                    severity = "Bilinmiyor"
                    
                    metrics = cve_data.get('metrics', {})
                    if 'cvssMetricV31' in metrics:
                        cvss_data = metrics['cvssMetricV31'][0].get('cvssData', {})
                        cvss_score = cvss_data.get('baseScore')
                        raw_sev = cvss_data.get('baseSeverity', '')
                        severity = severity_tr.get(raw_sev, self.get_severity_from_score(cvss_score))
                    elif 'cvssMetricV30' in metrics:
                        cvss_data = metrics['cvssMetricV30'][0].get('cvssData', {})
                        cvss_score = cvss_data.get('baseScore')
                        raw_sev = cvss_data.get('baseSeverity', '')
                        severity = severity_tr.get(raw_sev, self.get_severity_from_score(cvss_score))
                    elif 'cvssMetricV2' in metrics:
                        cvss_data = metrics['cvssMetricV2'][0].get('cvssData', {})
                        cvss_score = cvss_data.get('baseScore')
                        severity = self.get_severity_from_score(cvss_score)
                    
                    if cvss_score is None:
                        continue
                    
                    published = cve_data.get('published', '')
                    try:
                        published_date = datetime.strptime(published[:10], '%Y-%m-%d').date() if published else datetime.now().date()
                    except:
                        published_date = datetime.now().date()
                    
                    cwe_ids = []
                    for weakness in cve_data.get('weaknesses', []):
                        for desc in weakness.get('description', []):
                            if desc.get('value', '').startswith('CWE-'):
                                cwe_ids.append(desc['value'])
                    
                    references = []
                    for ref in cve_data.get('references', []):
                        if ref.get('url'):
                            references.append(ref['url'])
                    
                    cve = {
                        'cve_id': cve_id,
                        'source': 'NVD Güncel',
                        'original_title': f"{cve_id} - Güvenlik Açığı",
                        'original_description': description,
                        'severity': severity,
                        'cvss_score': cvss_score,
                        'published_date': published_date,
                        'modified_date': None,
                        'link': f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                        'cwe_ids': cwe_ids,
                        'references': references[:5],
                        'affected_products': ''
                    }
                    
                    cves.append(cve)
                    
                except Exception as e:
                    print(f"[NVD Güncel] CVE işleme hatası: {e}")
                    continue
            
            print(f"[NVD Güncel] {len(cves)} CVE bulundu")
            
        except Exception as e:
            print(f"[NVD Güncel] Hata: {e}")
        
        return cves


class MultiCVEScraper(CVEScraper):
    """Tum CVE kaynaklarini birlestiren scraper"""
    
    def __init__(self):
        super().__init__()
        self.nvd_scraper = NVDScraper()
        self.github_scraper = GitHubAdvisoryScraper()
        self.tenable_scraper = TenableScraper()
        self.circl_scraper = CIRCLScraper()
        self.nvd_recent_scraper = NVDRecentScraper()
    
    def fetch_all_cves(self, days: int = 30, selected_sources: list = None) -> List[Dict]:
        """Tum kaynaklardan CVE ceker"""
        all_cves = []
        
        print("=" * 80)
        print(f"TÜM CVE KAYNAKLARINDAN VERİ ÇEKİLİYOR ({days} gün)")
        print("=" * 80)
        
        sources = {
            'NVD': self.nvd_scraper,
            'GitHub Advisory': self.github_scraper,
            'Tenable': self.tenable_scraper,
            'CIRCL': self.circl_scraper,
            'NVD Güncel': self.nvd_recent_scraper,
        }
        
        if selected_sources:
            sources = {k: v for k, v in sources.items() if k in selected_sources}
        
        for source_name, scraper in sources.items():
            try:
                cves = scraper.fetch_cves(days=days)
                print(f"  -> {source_name}: {len(cves)} CVE")
                all_cves.extend(cves)
            except Exception as e:
                print(f"  -> {source_name}: HATA - {e}")
        
        seen_ids = set()
        unique_cves = []
        for cve in all_cves:
            if cve['cve_id'] not in seen_ids:
                seen_ids.add(cve['cve_id'])
                unique_cves.append(cve)
        
        print("=" * 80)
        print(f"TOPLAM {len(unique_cves)} CVE CEKILDI")
        print("=" * 80)
        
        return unique_cves
    
    def process_cves(self, cves: List[Dict]) -> List[Dict]:
        """CVE'leri Türkçeye çevirir ve işler"""
        print(f"\nCVE'ler işleniyor ve Türkçeye çevriliyor ({len(cves)} adet)...")
        total = len(cves)
        
        for i, cve in enumerate(cves, 1):
            try:
                # Title zaten Türkçe formatında ("CVE-XXXX - Güvenlik Açığı"), çevirme
                cve['turkish_title'] = cve['original_title']
                
                # Sadece description çevir
                desc = cve.get('original_description', '')
                if desc and len(desc.strip()) > 30:
                    if i % 20 == 0:
                        print(f"Çevriliyor: {i}/{total}")
                    cve['turkish_description'] = translate_text(desc)
                else:
                    cve['turkish_description'] = desc
                
                yield cve
                
            except Exception as e:
                print(f"İşleme hatası ({cve['cve_id']}): {e}")
                cve['turkish_title'] = cve['original_title']
                cve['turkish_description'] = cve['original_description']
                yield cve
        
        


if __name__ == "__main__":
    scraper = MultiCVEScraper()
    cves = scraper.fetch_all_cves(days=7)
    print(f"\nToplam {len(cves)} CVE cekildi")
