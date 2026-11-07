"""
CVE Scraper Module
NVD, CVEDetails, Rapid7, Tenable, VulDB gibi kaynaklardan CVE verilerini çeker.
"""

import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
from typing import List, Dict, Optional
import time

from news.translation_utils import translate_text
from news.base_scraper import BaseRSSScraper, oturum_kur
import logging

log = logging.getLogger(__name__)

# NVD 2.0 sayfalama (2026-11-07). Sayfa boyu API'nin izin verdigi en buyuk deger; tavanlar bir
# turun suresini ve bellegini sinirlar (7 gunde ~3.000 yayin, 2 gunde ~6.600 degisiklik).
NVD_SAYFA_BOYU = 2000
NVD_YAYIN_TAVANI = 4000
NVD_GUNCEL_GUN = 2
NVD_GUNCEL_TAVANI = 8000
NVD_ZAMAN_ASIMI = 60
# NVD hiz siniri: anahtarsiz 5 istek / 30 sn, anahtarla 50 / 30 sn. Bir turdaki butun NVD istekleri
# (KEV, yayin, guncel; sayfalar dahil) bu araliktan sik gitmez. None: anahtara gore secilir.
# Test calistiricisi 0 yapar.
NVD_ISTEK_ARALIGI = None
_son_nvd_istegi = 0.0

# Aciklamasi henuz yayinlanmamis CVE'lerde kaynaklarin koydugu yer tutucular (Tenable: 10-23'ten beri
# 57 kayit "No description provided" ile kaldi). Boyle bir kayit gercek aciklama gelince guncellenir.
_YER_TUTUCU_ACIKLAMALAR = {'no description provided', 'no description available', 'n/a'}


def aciklama_yer_tutucu_mu(metin) -> bool:
    """Aciklama bos, cok kisa ya da kaynagin yer tutucusu mu."""
    temiz = (metin or '').strip().rstrip('.').lower()
    return len(temiz) < 20 or temiz in _YER_TUTUCU_ACIKLAMALAR


def _nvd_araligi() -> float:
    if NVD_ISTEK_ARALIGI is not None:
        return NVD_ISTEK_ARALIGI
    return 0.7 if os.environ.get('NVD_API_KEY', '').strip() else 6.5


def tekil_cwe(cwe_ids) -> List[str]:
    """CWE listesini sirayi koruyarak tekillestirir, bos degerleri atar."""
    return list(dict.fromkeys(c for c in (cwe_ids or []) if c))


def nvd_cwe_listesi(weaknesses) -> List[str]:
    """NVD 'weaknesses' alanindan tekil CWE kimlikleri.

    NVD ayni CWE'yi hem kendi analizinden (Primary) hem CNA'dan (Secondary)
    ayri kayit olarak verebilir; ikisi de alinirsa liste yinelenir.
    """
    return tekil_cwe(
        d.get('value', '') for w in (weaknesses or [])
        for d in w.get('description', []) if d.get('value', '').startswith('CWE-')
    )


class CVEScraper(BaseRSSScraper):
    """CVE Scraper temel sınıfı"""

    NVD_API = "https://services.nvd.nist.gov/"

    def __init__(self):
        self.session = oturum_kur({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _nvd_get(self, url: str, **kwargs):
        """NVD istegi: NVD_API_KEY tanimliysa `apiKey` basligi ekler (2026-10-08).

        Anonim limit 5 istek / 30 sn; CVE turu artik 3 NVD istegi yapiyor (KEV,
        yayinlanan, guncel) ve 429'da scraper bos doner. Anahtarla 50 / 30 sn.
        Baslik tek istege konur ve yalniz services.nvd.nist.gov'a gider.
        """
        global _son_nvd_istegi
        headers = dict(kwargs.pop('headers', None) or {})
        anahtar = os.environ.get('NVD_API_KEY', '').strip()
        if url.startswith(self.NVD_API):
            if anahtar:
                headers['apiKey'] = anahtar
            bekle = _son_nvd_istegi + _nvd_araligi() - time.monotonic()
            if bekle > 0:
                time.sleep(bekle)
            _son_nvd_istegi = time.monotonic()
        return self.session.get(url, headers=headers, **kwargs)

    def _nvd_sayfalari(self, url: str, params: Dict, tavan: int):
        """NVD 2.0 `vulnerabilities` ogelerini startIndex ile sayfa sayfa verir; `tavan` kayitta durur.

        totalResults yoksa (eski/sahte yanit) ya da sayfa bos donerse tek sayfada biter. Ara sayfada
        hata firlarsa o ana kadar verilenler cagirana ulasmistir; hata yukari iletilir.
        """
        baslangic = 0
        while baslangic < tavan:
            sayfa = dict(params, resultsPerPage=min(NVD_SAYFA_BOYU, tavan - baslangic), startIndex=baslangic)
            response = self._nvd_get(url, params=sayfa, timeout=NVD_ZAMAN_ASIMI)
            response.raise_for_status()
            veri = response.json() or {}
            ogeler = veri.get('vulnerabilities', [])
            yield from ogeler
            baslangic += len(ogeler)
            toplam = veri.get('totalResults')
            if not ogeler or not isinstance(toplam, int) or baslangic >= toplam:
                break
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

    NVD_SEVERITY_TR = {'CRITICAL': 'Kritik', 'HIGH': 'Yüksek', 'MEDIUM': 'Orta', 'LOW': 'Düşük'}

    def _nvd_kaydi(self, cve_data: Dict, source: str) -> Optional[Dict]:
        """NVD 2.0 API'sinin tek `cve` nesnesini kayit sozlugune cevirir.

        Reddedilmis/ayrilmis, aciklamasiz ya da CVSS'siz kayitlar None doner
        (NVDScraper.fetch_cves ile ayni elemeler). CISA KEV kaynagi kullanir.
        """
        cve_id = cve_data.get('id', '')
        if not cve_id or cve_data.get('vulnStatus', '') in ('Rejected', 'Reserved'):
            return None

        descriptions = cve_data.get('descriptions', [])
        description = next((d.get('value', '') for d in descriptions if d.get('lang') == 'en'), '')
        if not description and descriptions:
            description = descriptions[0].get('value', '')
        desc_lower = description.lower()
        if any(p in desc_lower for p in [
            'rejected reason', '** reserved **', '** reject **',
            'this cve id has been rejected', 'not used', 'this candidate has been reserved',
        ]):
            return None
        if len(description.strip()) < 20:
            return None

        cvss_score = None
        severity = "Bilinmiyor"
        metrics = cve_data.get('metrics', {})
        for anahtar in ('cvssMetricV40', 'cvssMetricV31', 'cvssMetricV30', 'cvssMetricV2'):
            if anahtar in metrics and metrics[anahtar]:
                cvss_data = metrics[anahtar][0].get('cvssData', {})
                cvss_score = cvss_data.get('baseScore')
                severity = self.NVD_SEVERITY_TR.get(cvss_data.get('baseSeverity', ''),
                                                    self.get_severity_from_score(cvss_score))
                break
        if cvss_score is None:
            return None

        references = [r['url'] for r in cve_data.get('references', []) if r.get('url')]
        cwe_ids = nvd_cwe_listesi(cve_data.get('weaknesses'))

        def _tarih(deger):
            try:
                return datetime.strptime(deger[:10], '%Y-%m-%d').date() if deger else None
            except ValueError:
                return None

        return {
            'cve_id': cve_id,
            'source': source,
            'original_title': f"{cve_id} - Güvenlik Açığı",
            'original_description': description,
            'severity': severity,
            'cvss_score': cvss_score,
            'published_date': _tarih(cve_data.get('published', '')) or datetime.now().date(),
            'modified_date': _tarih(cve_data.get('lastModified', '')),
            'link': f"https://nvd.nist.gov/vuln/detail/{cve_id}",
            'cwe_ids': cwe_ids,
            'references': references[:5],
            'affected_products': '',
        }


class NVDScraper(CVEScraper):
    """NVD (National Vulnerability Database): yayin tarihi son `days` gun icinde olan CVE'ler.

    2026-11-07: sayfalama eklendi. Once tek istekte ilk 100 kayit aliniyordu; 7 gunluk pencerede
    NVD ~3.000 CVE tutar ve kalanlar hic gelmiyordu. Ust sinir NVD_YAYIN_TAVANI'dir.
    """

    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def fetch_cves(self, days: int = 30) -> List[Dict]:
        log.info(f"[NVD] Son {days} gunun CVE'leri cekiliyor...")
        cves = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        params = {
            'pubStartDate': start_date.strftime('%Y-%m-%dT00:00:00.000'),
            'pubEndDate': end_date.strftime('%Y-%m-%dT23:59:59.999'),
        }
        elenen = 0
        try:
            for item in self._nvd_sayfalari(self.BASE_URL, params, NVD_YAYIN_TAVANI):
                kayit = self._nvd_kaydi(item.get('cve', {}), 'NVD')
                if kayit:
                    cves.append(kayit)
                else:
                    elenen += 1
        except Exception as e:
            # Sayfa ortasinda hata: o ana kadar okunanlar yine doner
            log.warning(f"[NVD] Hata: {e}")
        log.info(f"[NVD] {len(cves)} CVE bulundu ({elenen} reddedilmis/aciklamasiz/CVSS'siz atlandi)")
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
        log.info(f"[GitHub Advisory] Son {days} günün CVE'leri çekiliyor...")
        
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
                    cwe_ids = tekil_cwe(cwe.get('cwe_id', '') for cwe in adv.get('cwes', []))
                    
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
                        # 2026-11-04: ozet 80 karakterde kelime ortasindan kesiliyordu ("... Dual-Header Inco");
                        # GHSA ozetleri kisadir, tamami saklanir. Eski kayitlar API'de duzeltilir (cve_basligi).
                        'original_title': f"{cve_id} - {summary.strip()}" if summary else f"{cve_id} - Güvenlik Açığı",
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
                    log.warning(f"[GitHub Advisory] CVE işleme hatası: {e}")
                    continue
            
            log.info(f"[GitHub Advisory] {len(cves)} CVE bulundu")
            
        except Exception as e:
            log.warning(f"[GitHub Advisory] Hata: {e}")
        
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
        log.info(f"[Tenable] Son {days} günün CVE'leri çekiliyor...")
        
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
                        if aciklama_yer_tutucu_mu(description):  # "No description provided" dahil
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
                        log.warning(f"[Tenable] CVE işleme hatası: {e}")
                        continue
            else:
                log.warning("[Tenable] __NEXT_DATA__ bulunamadı, HTML fallback deneniyor...")
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
                        if aciklama_yer_tutucu_mu(description):
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
                        log.warning(f"[Tenable] Fallback CVE işleme hatası: {e}")
                        continue
            
            log.info(f"[Tenable] {len(cves)} CVE bulundu")
            
        except Exception as e:
            log.warning(f"[Tenable] Hata: {e}")
        
        return cves


class NVDRecentScraper(CVEScraper):
    """NVD'de son NVD_GUNCEL_GUN gunde degisen CVE'ler: yalniz guncelleme kaynagi (2026-11-07).

    Once lastMod penceresinden rastgele bir dilim (startIndex=100'den 50 kayit) yeni kayit olarak
    ekleniyordu. Simdi bu kayitlar veritabanindaki CVE'lerin CVSS/KEV/aciklama guncellemesini
    tasir; yeni kayit olarak yalniz yayin tarihi cekim penceresindeyse alinir (bkz.
    tasks.fetch_cve_task). Pencere `days`'ten bagimsiz: NVD gunde ~3.000 kaydi degistirir.
    """

    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"

    def fetch_cves(self, days: int = 30) -> List[Dict]:
        gun = min(days, NVD_GUNCEL_GUN)
        log.info(f"[NVD Güncel] Son {gun} günde değiştirilen CVE'ler çekiliyor...")
        cves = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=gun)
        params = {
            'lastModStartDate': start_date.strftime('%Y-%m-%dT%H:%M:%S.000'),
            'lastModEndDate': end_date.strftime('%Y-%m-%dT%H:%M:%S.999'),
        }
        try:
            for item in self._nvd_sayfalari(self.BASE_URL, params, NVD_GUNCEL_TAVANI):
                kayit = self._nvd_kaydi(item.get('cve', {}), 'NVD Güncel')
                if kayit:
                    cves.append(kayit)
        except Exception as e:
            log.warning(f"[NVD Güncel] Hata: {e}")
        log.info(f"[NVD Güncel] {len(cves)} CVE bulundu")
        return cves


class CISAKEVScraper(CVEScraper):
    """CISA Known Exploited Vulnerabilities (KEV) — NVD API'sinin `hasKev` filtresiyle.

    cisa.gov'daki resmi JSON akisi (known_exploited_vulnerabilities.json) bot korumasi
    nedeniyle sunucudan 403 donuyor (2026-10-08). NVD ayni kayitlari `cisaExploitAdd`,
    `cisaActionDue` ve `cisaVulnerabilityName` alanlariyla verir; yeni host ve anahtar
    gerekmez. Pencere: KEV'e eklenme tarihi (cisaExploitAdd) son `days` gun icinde olanlar.
    API lastMod penceresini zorunlu kildigi icin o da ayni gun sayisiyla verilir.
    """

    BASE_URL = NVDScraper.BASE_URL
    KEV_KATALOG = "https://www.cisa.gov/known-exploited-vulnerabilities-catalog"

    def fetch_cves(self, days: int = 30) -> List[Dict]:
        log.info(f"[CISA KEV] Son {days} günde KEV'e eklenen CVE'ler çekiliyor...")
        cves = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        cutoff = start_date.date()

        try:
            params = {
                'lastModStartDate': start_date.strftime('%Y-%m-%dT00:00:00.000'),
                'lastModEndDate': end_date.strftime('%Y-%m-%dT23:59:59.999'),
            }
            # hasKev degersiz bir bayrak; requests params ile `hasKev=` uretir, API onu kabul etmez
            for item in self._nvd_sayfalari(f"{self.BASE_URL}?hasKev", params, NVD_SAYFA_BOYU):
                try:
                    cve_data = item.get('cve', {})
                    eklenme = cve_data.get('cisaExploitAdd', '')
                    try:
                        eklenme_tarihi = datetime.strptime(eklenme[:10], '%Y-%m-%d').date()
                    except ValueError:
                        continue
                    if eklenme_tarihi < cutoff:
                        continue

                    kayit = self._nvd_kaydi(cve_data, 'CISA KEV')
                    if not kayit:
                        continue

                    ad = (cve_data.get('cisaVulnerabilityName') or '').strip()
                    kayit['original_title'] = f"{kayit['cve_id']} - {ad}" if ad else f"{kayit['cve_id']} - Aktif Sömürülen Zafiyet"
                    son_tarih = (cve_data.get('cisaActionDue') or '')[:10]
                    onek = f"Added to the CISA KEV catalog on {eklenme[:10]}"
                    if son_tarih:
                        onek += f"; required action due {son_tarih}"
                    kayit['original_description'] = f"{onek}. {kayit['original_description']}"
                    kayit['kev_added_date'] = eklenme_tarihi
                    kayit['references'] = [self.KEV_KATALOG] + kayit['references'][:4]
                    cves.append(kayit)
                except Exception as e:
                    log.warning(f"[CISA KEV] CVE işleme hatası: {e}")
                    continue

            log.info(f"[CISA KEV] {len(cves)} CVE bulundu")
        except Exception as e:
            log.warning(f"[CISA KEV] Hata: {e}")

        return cves


# Ayni CVE birden fazla kaynaktan gelirse tutulacak kayit (2026-11-07). NVD ailesi once: CVSS'i NVD
# analizinden gelir; Tenable'in skoru onem kovasinin sabit degeridir (Critical -> 9.5), GHSA'nin
# basligi Ingilizce ozettir. KEV en once: somuru bilgisini tasir. Listede olmayan kaynak en sona.
KAYNAK_ONCELIGI = ('CISA KEV', 'NVD', 'NVD Güncel', 'GitHub Advisory', 'Tenable')


def tekillestir(cves: List[Dict]) -> List[Dict]:
    """CVE kimligi basina KAYNAK_ONCELIGI'ne gore en iyi kaydi tutar; ilk gorulme sirasi korunur."""
    sira = {ad: i for i, ad in enumerate(KAYNAK_ONCELIGI)}
    secilen: Dict[str, Dict] = {}
    for cve in cves:
        mevcut = secilen.get(cve['cve_id'])
        if mevcut is None:
            secilen[cve['cve_id']] = cve
        elif sira.get(cve.get('source'), len(sira)) < sira.get(mevcut.get('source'), len(sira)):
            secilen[cve['cve_id']] = cve
    return list(secilen.values())


class MultiCVEScraper(CVEScraper):
    """Tum CVE kaynaklarini birlestiren scraper"""

    def __init__(self):
        super().__init__()
        self.kev_scraper = CISAKEVScraper()
        self.nvd_scraper = NVDScraper()
        self.github_scraper = GitHubAdvisoryScraper()
        self.tenable_scraper = TenableScraper()
        self.nvd_recent_scraper = NVDRecentScraper()
        # Ayni CVE birden fazla kaynaktan gelirse hangisinin tutulacagini KAYNAK_ONCELIGI belirler
        # (bkz. tekillestir); bu sira yalniz cekim ve saglik listesinin sirasidir.
        # Kayit defteri news/kaynaklar.py tarafindan da okunur (kaynak sagligi).
        # 2026-10-14: CIRCL cikarildi (/api/last yalniz PYSEC/GHSA ve eski published donuyor; NVD + GitHub Advisory kapsiyor)
        self.sources = {
            'CISA KEV': self.kev_scraper,
            'NVD': self.nvd_scraper,
            'GitHub Advisory': self.github_scraper,
            'Tenable': self.tenable_scraper,
            'NVD Güncel': self.nvd_recent_scraper,
        }
    
    def fetch_all_cves(self, days: int = 30, selected_sources: list = None) -> List[Dict]:
        """Tum kaynaklardan CVE ceker"""
        all_cves = []
        
        log.info("=" * 80)
        log.info(f"TÜM CVE KAYNAKLARINDAN VERİ ÇEKİLİYOR ({days} gün)")
        log.info("=" * 80)
        
        sources = dict(self.sources)

        if selected_sources:
            sources = {k: v for k, v in sources.items() if k in selected_sources}
        
        for source_name, scraper in sources.items():
            try:
                cves = scraper.fetch_cves(days=days)
                log.info(f"  -> {source_name}: {len(cves)} CVE")
                all_cves.extend(cves)
            except Exception as e:
                log.warning(f"  -> {source_name}: HATA - {e}")
        
        unique_cves = tekillestir(all_cves)

        log.info("=" * 80)
        log.info(f"TOPLAM {len(unique_cves)} CVE CEKILDI")
        log.info("=" * 80)
        
        return unique_cves
    
    def process_cves(self, cves: List[Dict]) -> List[Dict]:
        """CVE'leri Türkçeye çevirir ve işler"""
        log.info(f"\nCVE'ler işleniyor ve Türkçeye çevriliyor ({len(cves)} adet)...")
        total = len(cves)
        
        for i, cve in enumerate(cves, 1):
            try:
                # Title zaten Türkçe formatında ("CVE-XXXX - Güvenlik Açığı"), çevirme
                cve['turkish_title'] = cve['original_title']
                
                # Sadece description çevir
                desc = cve.get('original_description', '')
                if desc and len(desc.strip()) > 30:
                    if i % 20 == 0:
                        log.info(f"Çevriliyor: {i}/{total}")
                    cve['turkish_description'] = translate_text(desc)
                else:
                    cve['turkish_description'] = desc
                
                yield cve
                
            except Exception as e:
                log.warning(f"İşleme hatası ({cve['cve_id']}): {e}")
                cve['turkish_title'] = cve['original_title']
                cve['turkish_description'] = cve['original_description']
                yield cve
        
        


if __name__ == "__main__":
    scraper = MultiCVEScraper()
    cves = scraper.fetch_all_cves(days=7)
    print(f"\nToplam {len(cves)} CVE cekildi")
