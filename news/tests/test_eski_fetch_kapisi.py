"""Eski POST /api/*/fetch/ uclari: v1 bolum kilidi + soguma kapisi (2026-09-30).

Uclar anonim kullanima acik kalir (kullanici karari) ama kaynak sitelere ve
ceviri kotasina giden yuk v1 ile ayni Redis kapisindan gecer. Gercek task
kuyruga atilmaz: RefreshTestMixin alti task'in apply_async'ini mock'lar.
"""
from django.core.cache import cache

from news.api_v1 import refresh
from news.tests.base import RefreshTestMixin, V1TestCase

# URL -> (refresh bolumu, frontend cache anahtari)
UCLAR = {
    '/api/fetch/': ('news', 'cybersecurity_news'),
    '/api/cve/fetch/': ('cve', 'cve_entries'),
    '/api/k8s/fetch/': ('kubernetes', 'k8s_entries'),
    '/api/sre/fetch/': ('sre', 'sre_entries'),
    '/api/devtools/fetch/': ('devtools', 'devtools_entries'),
    '/api/ai/fetch/': ('ai', 'ai_entries'),
}


class EskiFetchKapisiTest(RefreshTestMixin, V1TestCase):

    def _gonder(self, url='/api/cve/fetch/', govde=None):
        return self.client.post(url, govde if govde is not None else {'days': 7},
                                content_type='application/json')

    def test_baslatir_ve_gun_kaynak_etiketi_gecer(self):
        yanit = self._gonder(govde={'days': 3, 'sources': ['NVD Guncel']})

        self.assertEqual(yanit.status_code, 200)
        self.assertTrue(yanit.json()['success'])
        self.assertTrue(yanit.json()['job_id'])
        cagri = self.gorevler['cve'].call_args
        self.assertEqual(cagri.kwargs['kwargs'],
                         {'skip_existing': True, 'days': 3, 'selected_sources': ['NVD Guncel']})
        self.assertEqual(cagri.kwargs['headers'], {'fetchrun_trigger': 'admin'})

    def test_gun_verilmezse_varsayilan_bugunku_davranis(self):
        """fetch_cves eskiden request.data.get('days', 7) kullaniyordu."""
        self._gonder(govde={})
        self.assertEqual(self.gorevler['cve'].call_args.kwargs['kwargs'],
                         {'skip_existing': True, 'days': 7, 'selected_sources': None})

    def test_calisan_is_varken_ikinci_istek_kuyruga_atmaz(self):
        ilk = self._gonder().json()
        ikinci = self._gonder()

        self.assertEqual(ikinci.status_code, 200)
        self.assertTrue(ikinci.json()['success'])
        self.assertEqual(ikinci.json()['job_id'], ilk['job_id'])
        self.assertIn('zaten', ikinci.json()['message'])
        self.assertEqual(self.gorevler['cve'].call_count, 1)

    def test_sogumada_429_ve_retry_after(self):
        self.gate.start_cooldown('cve', 600)

        yanit = self._gonder()

        self.assertEqual(yanit.status_code, 429)
        self.assertEqual(yanit['Retry-After'], '600')
        self.assertFalse(yanit.json()['success'])
        self.assertEqual(yanit.json()['retry_after'], 600)
        self.assertIn('10 dk', yanit.json()['message'])
        self.assertFalse(self.gorevler['cve'].called)

    def test_soguma_v1_ile_paylasilir(self):
        """v1 tuketicisi tetikleyip is bittiyse arayuz de sogumaya takilir."""
        sonuc = refresh.trigger('cve')
        self.gate.release('cve', sonuc.job_id)  # is bitti: kilit birakildi, soguma suruyor

        yanit = self._gonder()

        self.assertEqual(yanit.status_code, 429)
        self.assertEqual(self.gorevler['cve'].call_count, 1)

    def test_gecersiz_gun_400(self):
        for govde in ({'days': 0}, {'days': 1000}, {'days': 'abc'}):
            with self.subTest(govde=govde):
                yanit = self._gonder(govde=govde)
                self.assertEqual(yanit.status_code, 400)
                self.assertFalse(yanit.json()['success'])
        self.assertFalse(self.gorevler['cve'].called)

    def test_asiri_kaynak_listesi_400(self):
        yanit = self._gonder(govde={'days': 7, 'sources': [f'k{i}' for i in range(21)]})
        self.assertEqual(yanit.status_code, 400)
        self.assertFalse(self.gorevler['cve'].called)

    def test_cache_yalniz_baslatilinca_silinir(self):
        cache.set('cve_entries', ['eski'])
        self.gate.start_cooldown('cve', 600)
        self._gonder()
        self.assertEqual(cache.get('cve_entries'), ['eski'], 'sogumada cache silinmemeli')

        self.redis.delete(f'{self.gate.prefix}:cooldown:cve')  # soguma bitti
        self._gonder()
        self.assertIsNone(cache.get('cve_entries'), 'baslatilinca cache silinmeli')

    def test_alti_uc_dogru_bolume_gider(self):
        for url, (bolum, cache_anahtari) in UCLAR.items():
            with self.subTest(url=url):
                cache.set(cache_anahtari, ['eski'])
                yanit = self._gonder(url=url, govde={'days': 7})
                self.assertEqual(yanit.status_code, 200)
                self.assertEqual(self.gorevler[bolum].call_count, 1)
                self.assertIsNone(cache.get(cache_anahtari))

    def test_anonim_istek_kabul_edilir(self):
        """Kullanici karari: uclar anonim kullanima acik kalir."""
        self.client.logout()
        self.assertEqual(self._gonder().status_code, 200)
