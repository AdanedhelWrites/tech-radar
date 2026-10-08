"""2026-10-08 kaynak turu: yeni ve onarilan scraper'larin HTTP'siz birim testleri.

Her test `session.get`'i mock'lar; hicbir test aga cikmaz. Kapsam:
  - GitHub Releases ortak sinifi (LiteLLM/LangGraph/Langfuse/Keycloak) ve GITHUB_TOKEN kurali
  - GitLab resmi surum Atom'u, MongoDB tags Atom + surum notu sayfasi
  - CISA KEV (NVD hasKev) eklenme-tarihi penceresi ve kayit sirasi
  - RSSNewsSource (7 yeni haber kaynagi) ve SecurityWeek'in RSS'e gecisi
  - Bleeping Computer UA'si, fetch_all tavaninin kaynak sayisiyla buyumesi
  - InfoQ SRE'nin RSS'e gecisi, DZone adresi
"""
import os
from datetime import datetime, timedelta
from unittest import mock

import requests
from django.test import SimpleTestCase

import scraper_multi as sm
from news.cve_scraper import CISAKEVScraper, MultiCVEScraper
from news.devtools_scraper import (
    GitHubReleasesScraper, GitLabScraper, MongoDBScraper, MultiDevToolsScraper,
)
from news.sre_scraper import DZoneDevOpsScraper, InfoQSREScraper


def _gun(n):
    return datetime.now() - timedelta(days=n)


def iso(n):
    return _gun(n).strftime('%Y-%m-%dT12:00:00Z')


def rfc(n):
    return _gun(n).strftime('%a, %d %b %Y 12:00:00 GMT')


class SahteYanit:
    def __init__(self, content='', json_data=None, status=200):
        self.content = content.encode('utf-8') if isinstance(content, str) else content
        self.text = self.content.decode('utf-8', 'replace')
        self._json = json_data
        self.status_code = status
        self.ok = status < 400
        self.headers = {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(f'HTTP {self.status_code}')


def yonlendir(tablo):
    """URL onekine gore sahte yanit secen session.get yedegi; eslesmeyen URL 404."""
    def _get(url, *args, **kwargs):
        for onek, yanit in tablo.items():
            if url.startswith(onek):
                return yanit
        return SahteYanit('', status=404)
    return _get


# ============================================================
# GitHub Releases ortak sinifi
# ============================================================
def _release(tag, gun, prerelease=False, name=None, body='notes'):
    return {'tag_name': tag, 'name': name or tag, 'prerelease': prerelease, 'draft': False,
            'published_at': iso(gun), 'html_url': f'https://github.com/x/r/releases/tag/{tag}',
            'body': body}


class GitHubReleasesScraperTests(SimpleTestCase):

    def test_on_surum_desen_disi_ve_eski_surumler_elenir(self):
        s = GitHubReleasesScraper('LiteLLM', 'BerriAI/litellm', r'^v\d+\.\d+\.\d+$')
        releases = [
            _release('v1.106.0-dev.2', 0, prerelease=True),
            _release('v1.105.0-rc.3', 0, prerelease=True),
            _release('v1.104.2', 1, body="## What's Changed\n* **Fix** [thing](https://e) by @a"),
            _release('v1.100.0', 90),
            _release('nightly', 0),
        ]
        with mock.patch.object(s.session, 'get', return_value=SahteYanit(json_data=releases)) as get:
            entries = s.fetch_entries(days=60)

        self.assertEqual([e['version'] for e in entries], ['v1.104.2'])
        self.assertEqual(entries[0]['title'], 'LiteLLM v1.104.2')
        self.assertEqual(entries[0]['source'], 'LiteLLM')
        self.assertEqual(entries[0]['entry_type'], 'release')
        self.assertIn('Fix thing', entries[0]['description'])
        self.assertNotIn('](', entries[0]['description'])
        self.assertEqual(get.call_args.args[0], 'https://api.github.com/repos/BerriAI/litellm/releases')
        self.assertEqual(get.call_args.kwargs['params'], {'per_page': 20})

    def test_langgraph_deseni_cekirdek_sdk_cli_alir_paket_esitligini_bosluk_yapar(self):
        s = MultiDevToolsScraper().scrapers['LangGraph']
        releases = [
            _release('1.2.14', 1, name='langgraph==1.2.14'),
            _release('sdk==0.4.6', 2, name='langgraph-sdk==0.4.6'),
            _release('cli==0.4.32.dev0', 3, name='langgraph-cli==0.4.32.dev0'),
            _release('checkpointpostgres==3.1.2', 4, name='langgraph-checkpoint-postgres==3.1.2'),
        ]
        with mock.patch.object(s.session, 'get', return_value=SahteYanit(json_data=releases)):
            entries = s.fetch_entries(days=60)

        self.assertEqual([e['title'] for e in entries], ['langgraph 1.2.14', 'langgraph-sdk 0.4.6'])
        self.assertEqual(entries[1]['version'], 'sdk==0.4.6')

    def test_bes_yeni_kaynak_kayitli(self):
        scrapers = MultiDevToolsScraper().scrapers
        for ad in ('LiteLLM', 'LangGraph', 'Langfuse', 'GitLab', 'Keycloak'):
            self.assertIn(ad, scrapers)
        self.assertIsInstance(scrapers['GitLab'], GitLabScraper)
        self.assertEqual(scrapers['Keycloak'].repo, 'keycloak/keycloak')

    def test_api_hatasi_bos_liste_dondurur(self):
        s = GitHubReleasesScraper('Keycloak', 'keycloak/keycloak', r'^\d+\.\d+\.\d+$')
        with mock.patch.object(s.session, 'get', return_value=SahteYanit('', status=403)):
            self.assertEqual(s.fetch_entries(days=60), [])


class GitHubTokenTests(SimpleTestCase):

    def test_token_yalniz_api_github_com_istegine_eklenir(self):
        s = GitHubReleasesScraper('Keycloak', 'keycloak/keycloak', r'^\d+\.\d+\.\d+$')
        with mock.patch.dict(os.environ, {'GITHUB_TOKEN': 'ghp_test'}), \
                mock.patch.object(s.session, 'get', return_value=SahteYanit(json_data=[])) as get:
            s._github_get('https://api.github.com/repos/keycloak/keycloak/releases')
            s._github_get('https://datalust.co/blog/rss/')

        self.assertEqual(get.call_args_list[0].kwargs['headers']['Authorization'], 'Bearer ghp_test')
        self.assertNotIn('Authorization', get.call_args_list[1].kwargs['headers'])
        # Oturum basliklarina hic yazilmaz: diger hostlara giden isteklere sizmasin
        self.assertNotIn('Authorization', s.session.headers)

    def test_token_yoksa_baslik_yok(self):
        s = GitHubReleasesScraper('Keycloak', 'keycloak/keycloak', r'^\d+\.\d+\.\d+$')
        with mock.patch.dict(os.environ, {'GITHUB_TOKEN': ''}), \
                mock.patch.object(s.session, 'get', return_value=SahteYanit(json_data=[])) as get:
            s._github_get('https://api.github.com/repos/keycloak/keycloak/releases')
        self.assertNotIn('Authorization', get.call_args.kwargs['headers'])
        self.assertEqual(get.call_args.kwargs['headers']['Accept'], 'application/vnd.github+json')


# ============================================================
# GitLab ve MongoDB
# ============================================================
def _gitlab_atom():
    return f'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>GitLab 19.4 release notes</title>
<link href="https://docs.gitlab.com/releases/19/gitlab-19-4-released/" rel="alternate"/>
<published>{iso(5)}</published><updated>{iso(5)}</updated>
<content type="html">&lt;p&gt;On September 17, GitLab 19.4 was released with features.&lt;/p&gt;</content></entry>
<entry><title>GitLab Critical Patch Release: 19.4.1, 19.3.3, 19.2.7</title>
<link href="https://docs.gitlab.com/releases/patches/patch-release-gitlab-19-4-1-released/" rel="alternate"/>
<published>{iso(2)}</published><content type="html">&lt;p&gt;Patch.&lt;/p&gt;</content></entry>
<entry><title>GitLab 18.0 release notes</title>
<link href="https://docs.gitlab.com/releases/18/gitlab-18-0-released/" rel="alternate"/>
<published>{iso(400)}</published><content type="html">eski</content></entry>
</feed>'''


class GitLabScraperTests(SimpleTestCase):

    def test_atom_surumleri_pencere_icinde_okur(self):
        s = GitLabScraper()
        with mock.patch.object(s.session, 'get', return_value=SahteYanit(_gitlab_atom())):
            entries = s.fetch_entries(days=60)

        self.assertEqual([e['version'] for e in entries], ['19.4', '19.4.1'])
        self.assertEqual(entries[0]['title'], 'GitLab 19.4 release notes')
        self.assertEqual(entries[0]['description'], 'On September 17, GitLab 19.4 was released with features.')
        self.assertEqual(entries[0]['link'], 'https://docs.gitlab.com/releases/19/gitlab-19-4-released/')
        self.assertEqual(entries[0]['source'], 'GitLab')
        self.assertEqual(entries[0]['date'], _gun(5).strftime('%Y-%m-%d'))


def _mongo_tags():
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>a</id><updated>{iso(3)}</updated>
<link rel="alternate" type="text/html" href="https://github.com/mongodb/mongo/releases/tag/r8.0.34"/>
<title>r8.0.34</title></entry>
<entry><id>b</id><updated>{iso(4)}</updated>
<link rel="alternate" type="text/html" href="https://github.com/mongodb/mongo/releases/tag/r9.1.0-alpha0"/>
<title>r9.1.0-alpha0</title></entry>
<entry><id>c</id><updated>{iso(200)}</updated>
<link rel="alternate" href="https://github.com/mongodb/mongo/releases/tag/r8.0.1"/>
<title>r8.0.1</title></entry>
</feed>'''


MONGO_NOTLAR = '''<html><body><main>
<section id="x"><h3>8.0.34 - Sept 24, 2026</h3><p>Issues fixed:</p>
<ul><li>SERVER-1 Fix the thing that was broken in sharding.</li></ul></section>
<section id="y"><h3>8.0.32 - Sept 11, 2026</h3><p>Other notes.</p></section>
</main></body></html>'''


class MongoDBScraperTests(SimpleTestCase):

    def test_stabil_tag_surum_notuyla_okunur_alpha_ve_eski_elenir(self):
        s = MongoDBScraper()
        tablo = {
            MongoDBScraper.TAGS_ATOM: SahteYanit(_mongo_tags()),
            'https://www.mongodb.com/docs/manual/release-notes/8.0/': SahteYanit(MONGO_NOTLAR),
        }
        with mock.patch.object(s.session, 'get', side_effect=yonlendir(tablo)):
            entries = s.fetch_entries(days=60)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['title'], 'MongoDB 8.0.34')
        self.assertEqual(entries[0]['version'], '8.0.34')
        self.assertEqual(entries[0]['link'], 'https://github.com/mongodb/mongo/releases/tag/r8.0.34')
        self.assertIn('SERVER-1 Fix the thing', entries[0]['description'])
        self.assertNotIn('Other notes', entries[0]['description'])

    def test_surum_notu_sayfasi_yoksa_yedek_aciklama(self):
        s = MongoDBScraper()
        with mock.patch.object(s.session, 'get',
                               side_effect=yonlendir({MongoDBScraper.TAGS_ATOM: SahteYanit(_mongo_tags())})):
            entries = s.fetch_entries(days=60)

        self.assertEqual(len(entries), 1)
        self.assertIn('https://www.mongodb.com/docs/manual/release-notes/8.0/', entries[0]['description'])


# ============================================================
# CISA KEV (NVD hasKev)
# ============================================================
def _nvd_cve(cve_id, eklenme_gun, ad='Vendor Product Vulnerability', score=9.8, durum='Analyzed'):
    return {'cve': {
        'id': cve_id, 'vulnStatus': durum,
        'published': '2024-01-05T10:00:00.000', 'lastModified': iso(1),
        'descriptions': [{'lang': 'en', 'value': 'A remote attacker can execute arbitrary code via crafted packets.'}],
        'metrics': {'cvssMetricV31': [{'cvssData': {'baseScore': score, 'baseSeverity': 'CRITICAL'}}]},
        'references': [{'url': 'https://vendor.example/advisory'}],
        'weaknesses': [{'description': [{'value': 'CWE-787'}]}],
        'cisaExploitAdd': _gun(eklenme_gun).strftime('%Y-%m-%d'),
        'cisaActionDue': _gun(eklenme_gun - 3).strftime('%Y-%m-%d'),
        'cisaVulnerabilityName': ad,
    }}


class CISAKEVScraperTests(SimpleTestCase):

    def test_yalniz_pencerede_eklenenler_ve_kev_alanlari(self):
        s = CISAKEVScraper()
        veri = {'vulnerabilities': [
            _nvd_cve('CVE-2024-0001', 3),
            _nvd_cve('CVE-2020-0002', 100),          # KEV'e 100 gun once eklenmis, lastMod yeni
            _nvd_cve('CVE-2024-0003', 2, durum='Rejected'),
        ]}
        with mock.patch.object(s.session, 'get', return_value=SahteYanit(json_data=veri)) as get:
            cves = s.fetch_cves(days=30)

        self.assertEqual([c['cve_id'] for c in cves], ['CVE-2024-0001'])
        kayit = cves[0]
        self.assertEqual(kayit['source'], 'CISA KEV')
        self.assertEqual(kayit['original_title'], 'CVE-2024-0001 - Vendor Product Vulnerability')
        self.assertTrue(kayit['original_description'].startswith('Added to the CISA KEV catalog on '))
        self.assertIn('required action due', kayit['original_description'])
        self.assertIn('A remote attacker can execute', kayit['original_description'])
        self.assertEqual(kayit['severity'], 'Kritik')
        self.assertEqual(kayit['cvss_score'], 9.8)
        self.assertEqual(kayit['cwe_ids'], ['CWE-787'])
        self.assertEqual(kayit['references'][0], CISAKEVScraper.KEV_KATALOG)
        self.assertEqual(kayit['link'], 'https://nvd.nist.gov/vuln/detail/CVE-2024-0001')
        self.assertTrue(get.call_args.args[0].endswith('?hasKev'))
        self.assertIn('lastModStartDate', get.call_args.kwargs['params'])

    def test_cvss_siz_kayit_elenir(self):
        s = CISAKEVScraper()
        kayit = _nvd_cve('CVE-2024-0009', 1)
        kayit['cve']['metrics'] = {}
        with mock.patch.object(s.session, 'get', return_value=SahteYanit(json_data={'vulnerabilities': [kayit]})):
            self.assertEqual(s.fetch_cves(days=30), [])

    def test_kayit_defterinde_ilk_sirada_ve_secilebilir(self):
        m = MultiCVEScraper()
        beklenen = [{'cve_id': 'CVE-2024-0001', 'source': 'CISA KEV'}]
        with mock.patch.object(m.kev_scraper, 'fetch_cves', return_value=beklenen), \
                mock.patch.object(m.nvd_scraper, 'fetch_cves', side_effect=AssertionError('NVD cagrilmamali')):
            sonuc = m.fetch_all_cves(days=7, selected_sources=['CISA KEV'])
        self.assertEqual(sonuc, beklenen)


# ============================================================
# Haber: RSSNewsSource, SecurityWeek, Bleeping Computer, tavan
# ============================================================
UZUN = ('Uzun tam icerik paragrafi burada, en az iki yuz karakter olacak kadar uzatilmis bir metin; '
        'bu metin content:encoded alanindan okunur ve sayfaya gidilmez. Devam eden cumle, devam eden '
        'cumle, devam eden cumle, devam eden cumle, devam eden cumle sonu.')


def _rss(items):
    govde = ''.join(items)
    return ('<?xml version="1.0"?><rss version="2.0" '
            'xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>'
            f'{govde}</channel></rss>')


def _item(title, link, gun, desc='Kisa.', full=None):
    enc = f'<content:encoded><![CDATA[<p>{full}</p>]]></content:encoded>' if full else ''
    link_xml = f'<link>{link}</link>' if link else ''
    return (f'<item><title>{title}</title>{link_xml}<pubDate>{rfc(gun)}</pubDate>'
            f'<description>{desc}</description>{enc}</item>')


class RSSNewsSourceTests(SimpleTestCase):

    def test_akis_okunur_baslik_temizlenir_eski_ve_linksiz_elenir(self):
        s = sm.RSSNewsSource('SANS ISC', 'https://feed.test/rss', 'https://ornek.test')
        rss = _rss([
            _item('ISC Stormcast For Thursday, October 8th, 2026 https://isc.sans.edu/podcastdetail/9638, (Thu, Oct 8th)',
                  'https://ornek.test/a', 1, full=UZUN),
            _item('Eski haber', 'https://ornek.test/eski', 40),
            _item('Linksiz', '', 1),
        ])
        with mock.patch.object(s.session, 'get', side_effect=yonlendir({'https://feed.test/rss': SahteYanit(rss)})) as get:
            articles = s.fetch_news(days=7)

        self.assertEqual(len(articles), 1)
        a = articles[0]
        self.assertEqual(a['title'], 'ISC Stormcast For Thursday, October 8th, 2026')
        self.assertEqual(a['link'], 'https://ornek.test/a')
        self.assertEqual(a['source'], 'SANS ISC')
        self.assertEqual(a['date'], _gun(1).strftime('%Y-%m-%d'))
        self.assertEqual(a['original_date'], rfc(1))
        self.assertIn('Uzun tam icerik', a['description'])
        # content:encoded 200 karakterden uzun: makale sayfasina gidilmedi
        self.assertEqual(get.call_count, 1)

    def test_max_items_tavani(self):
        s = sm.RSSNewsSource('CyberScoop', 'https://feed.test/rss', 'https://ornek.test')
        s.max_items = 3
        rss = _rss([_item(f'Haber {i}', f'https://ornek.test/{i}', 1, full=UZUN) for i in range(10)])
        with mock.patch.object(s.session, 'get', side_effect=yonlendir({'https://feed.test/rss': SahteYanit(rss)})):
            self.assertEqual(len(s.fetch_news(days=7)), 3)

    def test_akis_hatasi_bos_liste(self):
        s = sm.RSSNewsSource('The Record', 'https://feed.test/rss', 'https://ornek.test')
        with mock.patch.object(s.session, 'get', side_effect=requests.ConnectionError('kopuk')):
            self.assertEqual(s.fetch_news(days=7), [])

    def test_yedi_yeni_kaynak_kayitli(self):
        adlar = [s.get_name() for s in sm.MultiSourceScraper().sources]
        for ad in ('The Record', 'CyberScoop', 'Help Net Security', 'Infosecurity Magazine',
                   'SANS ISC', 'The Register', 'Security Affairs'):
            self.assertIn(ad, adlar)
        self.assertEqual(len(adlar), 12)


class SecurityWeekRSSTests(SimpleTestCase):
    """Regresyon: HTML'de link bos geliyordu, 22 haber tek link='' kaydina cokuyordu."""

    def test_rss_link_tasir_ve_tam_makale_cekilir(self):
        s = sm.SecurityWeekSource()
        rss = _rss([_item('Patch Tuesday', 'https://www.securityweek.com/patch', 1, desc='Kisa ozet ' * 25)])
        # Makale govdesi RSS ozetinden (250 karakter) uzun olmali ki tam metin tercih edilsin
        p1 = 'Makale govdesi birinci paragraf, ' + 'yeterince uzun bir metin. ' * 8
        p2 = 'Ikinci paragraf da burada yer aliyor, ' + 'o da uzun tutuldu. ' * 8
        makale = (f'<html><body><article><div class="article-body"><p>{p1}</p><p>{p2}</p></div>'
                  '</article></body></html>')
        tablo = {'https://www.securityweek.com/feed/': SahteYanit(rss),
                 'https://www.securityweek.com/patch': SahteYanit(makale)}
        with mock.patch.object(s.session, 'get', side_effect=yonlendir(tablo)), \
                mock.patch('scraper_multi.time.sleep'):
            articles = s.fetch_news(days=7)

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['link'], 'https://www.securityweek.com/patch')
        self.assertEqual(articles[0]['source'], 'SecurityWeek')
        self.assertIn('Makale govdesi birinci paragraf', articles[0]['description'])
        self.assertIn('Ikinci paragraf', articles[0]['description'])


class BleepingComputerTests(SimpleTestCase):

    def test_firefox_user_agent_ve_tavan(self):
        s = sm.BleepingComputerSource()
        self.assertIn('Firefox', s.session.headers['User-Agent'])
        self.assertNotIn('Chrome', s.session.headers['User-Agent'])
        self.assertEqual(s.MAX_ITEMS, 10)


class _SahteKaynak:
    def __init__(self, ad, adet):
        self._ad, self._adet = ad, adet

    def get_name(self):
        return self._ad

    def fetch_news(self, days=7):
        return [{'title': f'{self._ad} {i}', 'description': 'x', 'link': f'https://{self._ad}.test/{i}',
                 'date': _gun(i).strftime('%Y-%m-%d'), 'original_date': '', 'source': self._ad}
                for i in range(self._adet)]


class FetchAllNewsTavanTests(SimpleTestCase):

    def test_tavan_kaynak_sayisiyla_buyur(self):
        m = sm.MultiSourceScraper()
        m.sources = [_SahteKaynak(f'k{i}', 10) for i in range(12)]
        # 12 kaynak: tavan max(30, 36) = 36, kaynak basina max(5, 36//12) = 5
        self.assertEqual(len(m.fetch_all_news(days=7)), 36)

    def test_bes_kaynakta_eski_davranis_korunur(self):
        m = sm.MultiSourceScraper()
        m.sources = [_SahteKaynak(f'k{i}', 10) for i in range(5)]
        self.assertEqual(len(m.fetch_all_news(days=7)), 30)


# ============================================================
# SRE: InfoQ RSS, DZone adresi
# ============================================================
class SREKaynakTests(SimpleTestCase):

    def test_infoq_rss_utm_parametresini_atar(self):
        s = InfoQSREScraper()
        rss = _rss([_item('Article: High Availability', 'https://www.infoq.com/articles/ha/?utm_campaign=x&utm_source=feed',
                          1, desc='Ozet ' * 60)])
        with mock.patch.object(s.session, 'get', side_effect=yonlendir({InfoQSREScraper.FEED_URL: SahteYanit(rss)})):
            entries = s.fetch_entries(days=30)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['link'], 'https://www.infoq.com/articles/ha/')
        self.assertEqual(entries[0]['source'], 'InfoQ SRE')

    def test_dzone_guncel_akis_adresi(self):
        self.assertEqual(DZoneDevOpsScraper.FEED_URL, 'https://feeds.dzone.com/devops-and-cicd')
