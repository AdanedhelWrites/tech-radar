"""news/metin_temizle.py: kaynak metninin ceviriden once temizlenmesi (2026-10-16 uctan uca test bulgulari).

Her ornek canli veriden alindi: SecurityWeek yapisik kelimeler ve yazar biyografisi, SANS ISC makrolari ve
cozulmemis varliklar, Google Cloud'un Python repr kod bloklari, MarkTechPost kapanis satiri ve ham HTML.
"""
from unittest import mock

from bs4 import BeautifulSoup
from django.test import SimpleTestCase

from news import metin_temizle as mt


def _p(html):
    return BeautifulSoup(html, 'html.parser').find('p')


class ParagrafMetniTests(SimpleTestCase):

    def test_satir_ici_etiket_sinirinda_bosluk_korunur(self):
        p = _p('<p>SecurityWeek’s weekly <a href="#">cybersecurity news roundup</a> offers a concise '
               'overview. University researchers have detailed <a href="#">ICS-Sniper</a>, a proof-of-concept.</p>')
        self.assertEqual(
            mt.paragraf_metni(p),
            'SecurityWeek’s weekly cybersecurity news roundup offers a concise overview. '
            'University researchers have detailed ICS-Sniper, a proof-of-concept.')

    def test_noktalama_oncesi_bosluk_ve_coklu_bosluk_toplanir(self):
        p = _p('<p>Patch <strong>now</strong> , before <em>Friday</em> .   It   matters ( really ) .</p>')
        self.assertEqual(mt.paragraf_metni(p), 'Patch now, before Friday. It matters (really).')

    def test_ic_ice_paragrafta_yalniz_kendi_metni_alinir(self):
        # SecurityWeek kapanmamis <p> kullanir; html.parser her paragrafi sonrakilerin hepsini
        # icine alacak sekilde ic ice kurar (canlida 3 KB makale 24 KB'a sisti)
        soup = BeautifulSoup('<div><p>First paragraph.<p>Second <b>one</b>.<p>Third.</div>', 'html.parser')
        self.assertEqual([mt.paragraf_metni(p) for p in soup.find_all('p')],
                         ['First paragraph.', 'Second one.', 'Third.'])


class TemizleTests(SimpleTestCase):

    def test_html_varliklari_ve_cift_kacis_cozulur(self):
        self.assertEqual(mt.temizle("Panchan's Mining Island &#x5b;Guest Diary&#x5d;"),
                         "Panchan's Mining Island [Guest Diary]")
        self.assertEqual(mt.temizle('a new tactic dubbed &amp;quot;RedFlick&amp;quot;'),
                         'a new tactic dubbed "RedFlick"')

    def test_kacisli_ham_html_metne_cevrilir(self):
        metin = ('Results: &lt;div class="pnl"&gt;&lt;button class="btn" id="gvNext"&gt;Next &lt;/button&gt;'
                 '&lt;span class="lbl"&gt;1/3&lt;/span&gt;&lt;svg viewBox="0 0 9 9"&gt;&lt;path d="M0"/&gt;'
                 '&lt;/svg&gt;&lt;/div&gt; The model scores 65.')
        sonuc = mt.temizle(metin)
        self.assertNotIn('<', sonuc)
        self.assertNotIn('button', sonuc)
        self.assertIn('The model scores 65.', sonuc)

    def test_konu_olan_html_ornekleri_korunur(self):
        # Guvenlik metinlerinde etiketler konunun kendisidir (canli CVE/haber kayitlari)
        for metin in ['Override the `href` attribute of a parent `<a>` element after load.',
                      'sanitizeHtml(\'<meta http-equiv="refresh" content="0;url=javascript:alert(1)">\')',
                      'It follows the same my-<code-host>.com naming pattern.',
                      'An allowed &lt;code&gt; element.']:
            with self.subTest(metin=metin):
                self.assertIn('<', mt.temizle(metin))

    def test_noktali_virgulsuz_varlik_cozulmez(self):
        metin = 'GET /x?param1=value&param2=value&copy=1 HTTP/1.1'
        self.assertEqual(mt.temizle(metin), metin)

    def test_kod_girintisi_korunur(self):
        metin = 'Example:\n\nif ok:\n    body = f"{x}"   # note\n        nested()\n# members:\n#   - apiGroup: x'
        self.assertEqual(mt.temizle(metin), metin)

    def test_markdown_related_basligi_korunur(self):
        metin = 'Fixed in 1.11.0.\n\nRelated:\n- Documentation: caronc/apprise-docs#60'
        self.assertEqual(mt.temizle(metin), metin)

    def test_sans_cve_makrosu_numaraya_doner(self):
        self.assertEqual(mt.temizle('Windows DHCP Server %%cve:2026-70201%% No No - - Important'),
                         'Windows DHCP Server CVE-2026-70201 No No - - Important')

    def test_google_cloud_python_repr_kod_blogu_koda_doner(self):
        metin = ("returns NULL . code_block <ListValue: [StructValue([('code', 'SELECT 1;\\r\\nSELECT 2;'), "
                 "('language', ''), ('caption', <wagtail.rich_text.RichText object at 0x7f93d8fb18d0>)])]> "
                 "Step 2: Run ingestion")
        sonuc = mt.temizle(metin)
        self.assertNotIn('object at 0x', sonuc)
        self.assertNotIn('StructValue', sonuc)
        self.assertIn('SELECT 1;\nSELECT 2;', sonuc)
        self.assertIn('Step 2: Run ingestion', sonuc)

    def test_kirpilmis_repr_blogu_atilir(self):
        metin = "Intro text. code_block <ListValue: [StructValue([('code', 'SET @@udf.properties = JSON"
        self.assertEqual(mt.temizle(metin), 'Intro text.')

    def test_marktechpost_kapanis_satiri_atilir(self):
        metin = ('Join us on telegram as well.\n\nThe post Mistral AI Releases Voxtral 3: Speech-to-Text '
                 'appeared first on MarkTechPost .')
        self.assertEqual(mt.temizle(metin), 'Join us on telegram as well.')

    def test_related_zinciri_ve_yazar_biyografisi_atilir(self):
        metin = ('Previdian has since logged over 1,800 attempts. Related: Mass Exploitation Looms for Leaked '
                 'Critical PHP Flaws Related: AOMEI Backupper Compromised\n\n'
                 'Ionut Arghire is an international correspondent for SecurityWeek.')
        self.assertEqual(mt.temizle(metin), 'Previdian has since logged over 1,800 attempts.')

    def test_metin_icindeki_related_sozcugu_korunur(self):
        metin = 'The related flaw was patched. Researchers say the issue is related to parsing.'
        self.assertEqual(mt.temizle(metin), metin)

    def test_paragraf_sinirlari_korunur(self):
        self.assertEqual(mt.temizle('Birinci\xa0paragraf.  \n\n\n\nIkinci paragraf.\r\n'),
                         'Birinci paragraf.\n\nIkinci paragraf.')

    def test_bos_ve_none(self):
        self.assertEqual(mt.temizle(''), '')
        self.assertEqual(mt.temizle(None), '')


class KisaltTests(SimpleTestCase):

    def test_sinir_altindaki_metin_degismez(self):
        self.assertEqual(mt.kisalt('Kisa metin.', 100), 'Kisa metin.')

    def test_paragraf_sinirinda_kesilir_ve_isaret_eklenir(self):
        metin = '\n\n'.join([f'Paragraph {i} ' + 'x' * 80 for i in range(10)])
        sonuc = mt.kisalt(metin, 300)
        self.assertLessEqual(len(sonuc), 300)
        self.assertTrue(sonuc.endswith('[…]'))
        self.assertTrue(sonuc.startswith('Paragraph 0 '))
        self.assertNotIn('Paragraph 3', sonuc)

    def test_tek_uzun_paragraf_cumle_sonunda_kesilir(self):
        metin = ('This is a sentence. ' * 40).strip()
        sonuc = mt.kisalt(metin, 100)
        self.assertLessEqual(len(sonuc), 100)
        self.assertTrue(sonuc.endswith('sentence. […]'))

    def test_varsayilan_sinir_gemini_sinirinin_altinda(self):
        from news import gemini
        self.assertLess(mt.MAKALE_MAX_KARAKTER, gemini.GEMINI_MAX_CHARS)


class BaslikTests(SimpleTestCase):

    def test_varlik_ve_bosluk(self):
        self.assertEqual(mt.baslik("Panchan's Mining Island &#x5b;Guest Diary&#x5d;  "),
                         "Panchan's Mining Island [Guest Diary]")
        self.assertEqual(mt.baslik('Extending\xa0Kubernetes\xa0policy'), 'Extending Kubernetes policy')


class ScraperEntegrasyonTests(SimpleTestCase):

    def test_securityweek_ic_ice_paragraf_tekrarlanmaz(self):
        import scraper_multi as sm
        from news.tests.test_kaynaklar import SahteYanit
        sayfa = ('<html><body><div class="entry-content">'
                 '<p>The private keys associated with eight certificates were exposed.'
                 '<p>On October 17,<a href="#">Mozilla</a>and<a href="#">Google</a>blocked the certificates.'
                 '<p><strong>Related:</strong><a href="#">AI Platform Cairn Abused to Hack Over 100 Organizations</a>'
                 '</div></body></html>')
        s = sm.SecurityWeekSource()
        with mock.patch.object(s.session, 'get', return_value=SahteYanit(sayfa)), \
             mock.patch('scraper_multi.time.sleep'):
            sonuc = s.fetch_full_article('https://www.securityweek.com/a')
        self.assertEqual(sonuc['content'],
                         'The private keys associated with eight certificates were exposed.\n\n'
                         'On October 17, Mozilla and Google blocked the certificates.')

    def test_process_news_temizler_ve_kisaltir(self):
        from scraper_multi import MultiSourceScraper
        makale = {'title': 'Panchan&#x27;s Island &#x5b;Guest Diary&#x5d;',
                  'description': 'Body &amp;quot;quoted&amp;quot;.\n\n' + ('Long sentence here. ' * 800),
                  'link': 'https://ornek.test/1', 'date': '2026-10-16', 'original_date': '2026-10-16',
                  'source': 'SANS ISC'}
        with mock.patch('scraper_multi.translate_text', side_effect=lambda t: t), \
             mock.patch('scraper_multi.translate_long_text', side_effect=lambda t: t):
            cikti = list(MultiSourceScraper().process_news([makale]))[0]
        self.assertEqual(cikti['original_title'], "Panchan's Island [Guest Diary]")
        self.assertTrue(cikti['original_description'].startswith('Body "quoted".\n\n'))
        self.assertLessEqual(len(cikti['original_description']), mt.MAKALE_MAX_KARAKTER)
        self.assertTrue(cikti['original_description'].endswith('[…]'))

    def test_k8s_yapisal_changelog_kisaltilmaz(self):
        from news.k8s_scraper import MultiK8sScraper
        desc = '===SECTION: Bug fixes===\n' + '\n'.join(f'- fix number {i}' for i in range(1200))
        entry = {'original_title': 'v1.36.0', 'original_description': desc, 'source': 'GitHub Releases'}
        with mock.patch('news.k8s_scraper.translate_text', side_effect=lambda t: t), \
             mock.patch.object(MultiK8sScraper, '_translate_structured_changelog', side_effect=lambda d: d):
            cikti = list(MultiK8sScraper().process_entries([entry]))[0]
        self.assertEqual(cikti['original_description'], desc)
