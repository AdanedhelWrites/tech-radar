"""Feed linklerinde SSRF korumasi (2026-10-08): news/base_scraper.link_guvenli ve cagri noktalari."""
from unittest import mock

from django.test import SimpleTestCase

import scraper_multi as sm
from news.base_scraper import BaseRSSScraper, kok_alan, link_guvenli
from news.devtools_scraper import RedisScraper
from news.k8s_scraper import K8sBlogScraper
from news.tests.test_kaynaklar import SahteYanit, _item, _rss, yonlendir


class LinkGuvenliTests(SimpleTestCase):

    def test_kabul_edilenler(self):
        for url, kok in [
            ('https://www.securityweek.com/a', 'securityweek.com'),
            ('https://securityweek.com/a', 'securityweek.com'),
            ('https://www.theregister.com/x', None),
            ('https://isc.sans.edu/diary/1', 'sans.edu'),
        ]:
            with self.subTest(url=url):
                self.assertTrue(link_guvenli(url, kok))

    def test_reddedilenler(self):
        for url, kok in [
            ('http://www.securityweek.com/a', 'securityweek.com'),      # https degil
            ('https://10.0.0.5/admin', None),                            # IP
            ('https://[::1]/', None),                                     # IPv6
            ('https://localhost/', None),
            ('https://teknoloji-redis:6379/', None),                      # tek etiket (kume ici servis)
            ('https://teknoloji-api.tech-radar.svc/', None),              # .svc
            ('https://vault.internal/', None),
            ('https://user:pw@www.securityweek.com/', 'securityweek.com'),
            ('https://evil.example/x', 'securityweek.com'),               # kok disi
            ('https://securityweek.com.evil.example/x', 'securityweek.com'),
            ('', None), ('bos', None), ('ftp://x.y/', None),
        ]:
            with self.subTest(url=url):
                self.assertFalse(link_guvenli(url, kok))

    def test_kok_alan(self):
        self.assertEqual(kok_alan('api.theregister.com'), 'theregister.com')
        self.assertEqual(kok_alan('feed.infoq.com'), 'infoq.com')
        self.assertEqual(kok_alan('deepmind.google'), 'deepmind.google')
        self.assertEqual(kok_alan('localhost'), 'localhost')


class CagriNoktalariTests(SimpleTestCase):

    def test_rss_kaynagi_kok_disi_linki_sayfadan_tamamlamaz(self):
        s = sm.RSSNewsSource('Infosecurity Magazine', 'https://www.infosecurity-magazine.com/rss/news/',
                             'https://www.infosecurity-magazine.com')
        rss = _rss([_item('Kisa haber', 'https://teknoloji-redis:6379/x', 1, desc='Kisa ozet.')])
        with mock.patch.object(s.session, 'get',
                               side_effect=yonlendir({'https://www.infosecurity-magazine.com/rss/news/': SahteYanit(rss)})) as get:
            articles = s.fetch_news(days=7)

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]['description'], 'Kisa ozet.')
        self.assertEqual(get.call_count, 1)  # yalniz akis; ic adrese istek yok
        self.assertEqual(s._aktif_kok, 'infosecurity-magazine.com')

    def test_fetch_full_article_kok_disi_url_acmaz(self):
        s = sm.SecurityWeekSource()
        with mock.patch.object(s.session, 'get') as get:
            sonuc = s.fetch_full_article('https://10.0.0.5/')
            sonuc2 = s.fetch_full_article('http://www.securityweek.com/a')
        self.assertEqual(sonuc, {'title': '', 'content': ''})
        self.assertEqual(sonuc2, {'title': '', 'content': ''})
        get.assert_not_called()

    def test_standart_rss_akis_kokunu_kurar(self):
        s = BaseRSSScraper()
        with mock.patch.object(s.session, 'get', return_value=SahteYanit(_rss([]))):
            s.fetch_standard_rss_entries('https://feed.infoq.com/sre/', 'InfoQ SRE', 30)
        self.assertEqual(s._aktif_kok, 'infoq.com')

    def test_k8s_ve_redis_sayfa_cekimi_kok_disinda_acmaz(self):
        k = K8sBlogScraper()
        r = RedisScraper()
        with mock.patch.object(k.session, 'get') as kget, mock.patch.object(r.session, 'get') as rget:
            self.assertEqual(k.fetch_article_content('https://evil.example/blog'), {'title': '', 'description': ''})
            self.assertEqual(r._fetch_full_article('https://teknoloji-redis:6379/'), '')
        kget.assert_not_called()
        rget.assert_not_called()
