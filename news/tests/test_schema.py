"""OpenAPI semasi (A5b). Sema dis sozlesmedir; buradaki assert'ler onu korur."""
from drf_spectacular import drainage
from drf_spectacular.generators import SchemaGenerator

from news.tests.base import V1TestCase


def sema_uret():
    """Semayi uretir. Istatistikler uretim oncesi sifirlanir ki onceki
    calismalardan kalan uyarilar sonuca karismasin."""
    drainage.reset_generator_stats()
    return SchemaGenerator().get_schema(request=None, public=True)


class SemaKapsamiTests(V1TestCase):

    def test_sema_yalniz_v1_yollarini_icerir(self):
        yollar = list(sema_uret()['paths'])

        self.assertTrue(yollar, 'sema hic yol uretmedi')
        v1_disi = [y for y in yollar if not y.startswith('/api/v1/')]
        self.assertEqual(v1_disi, [], f'eski uclar semaya sizdi: {v1_disi}')

    def test_sema_ucu_tokensiz_401(self):
        yanit = self.client.get('/api/v1/schema/')

        self.assertEqual(yanit.status_code, 401)

    def test_sema_ucu_token_ile_200(self):
        yanit = self.client.get('/api/v1/schema/', **self.token_basligi())

        self.assertEqual(yanit.status_code, 200)


class SerializerTipleriTests(V1TestCase):

    def test_method_field_uyarisi_kalmadi(self):
        sema_uret()

        uyarilar = [u for u in drainage.GENERATOR_STATS._warn_cache
                    if 'unable to resolve type hint' in str(u)]
        self.assertEqual(uyarilar, [], f'{len(uyarilar)} method-field uyarisi kaldi')

    def test_title_string_degil_nesne_olarak_belgelenir(self):
        bilesenler = sema_uret()['components']['schemas']

        title = bilesenler['CVEEntryV1']['properties']['title']
        self.assertEqual(title['type'], 'object')
        self.assertEqual(sorted(title['properties']), ['original', 'tr'])

    def test_severity_kod_ve_etiket_olarak_belgelenir(self):
        bilesenler = sema_uret()['components']['schemas']

        severity = bilesenler['CVEEntryV1']['properties']['severity']
        self.assertEqual(severity['type'], 'object')
        self.assertEqual(sorted(severity['properties']), ['code', 'label'])

    def test_translation_provider_nullable(self):
        bilesenler = sema_uret()['components']['schemas']

        alan = bilesenler['CVEEntryV1']['properties']['translation_provider']
        self.assertTrue(alan.get('nullable'), 'translation_provider nullable olmali')


DELTA_YOLLARI = {
    'news': '/api/v1/news/',
    'cve': '/api/v1/cve/',
    'kubernetes': '/api/v1/kubernetes/',
    'sre': '/api/v1/sre/',
    'devtools': '/api/v1/devtools/',
    'ai': '/api/v1/ai/',
}

ORTAK_PARAMETRELER = {
    'since_cursor', 'since', 'limit', 'source', 'needs_translation',
}


class DeltaSemasiTests(V1TestCase):

    def _get(self, sema, yol):
        return sema['paths'][yol]['get']

    def test_delta_uclari_zarf_dondurur(self):
        sema = sema_uret()

        for bolum, yol in DELTA_YOLLARI.items():
            with self.subTest(bolum=bolum):
                govde = self._get(sema, yol)['responses']['200']
                ref = govde['content']['application/json']['schema']['$ref']
                ad = ref.rsplit('/', 1)[-1]
                zarf = sema['components']['schemas'][ad]['properties']
                self.assertEqual(
                    sorted(zarf), ['count', 'has_more', 'next_cursor', 'results'])
                self.assertEqual(zarf['results']['type'], 'array')

    def test_ortak_parametreler_her_delta_ucunda(self):
        sema = sema_uret()

        for bolum, yol in DELTA_YOLLARI.items():
            with self.subTest(bolum=bolum):
                adlar = {p['name'] for p in self._get(sema, yol)['parameters']}
                self.assertTrue(ORTAK_PARAMETRELER <= adlar,
                                f'{bolum} eksik: {ORTAK_PARAMETRELER - adlar}')

    def test_bolume_ozgu_parametreler(self):
        sema = sema_uret()

        def adlar(yol):
            return {p['name'] for p in self._get(sema, yol)['parameters']}

        self.assertTrue({'min_severity', 'severity'} <= adlar(DELTA_YOLLARI['cve']))
        self.assertIn('category', adlar(DELTA_YOLLARI['kubernetes']))
        self.assertIn('entry_type', adlar(DELTA_YOLLARI['devtools']))
        # Sizinti olmamali: severity yalniz CVE'nindir
        self.assertNotIn('min_severity', adlar(DELTA_YOLLARI['news']))
        self.assertNotIn('category', adlar(DELTA_YOLLARI['sre']))

    def test_min_severity_gecerli_degerleri_enum_olarak_verir(self):
        sema = sema_uret()

        parametreler = self._get(sema, DELTA_YOLLARI['cve'])['parameters']
        ms = next(p for p in parametreler if p['name'] == 'min_severity')
        # OpenAPI enum sirasiz bir kumedir; drf-spectacular degerleri alfabetik
        # yazar (build_parameter_type -> sorted(enum, key=str)). Siralama
        # anlami tasimadigindan kume olarak karsilastiriliyor; eksik/fazla
        # deger olursa yine dusmeli.
        self.assertEqual(set(ms['schema']['enum']),
                         {'low', 'medium', 'high', 'critical'})


class DeltaDisiUclarTests(V1TestCase):

    def test_hicbir_uyari_veya_hata_kalmadi(self):
        sema_uret()

        uyarilar = list(drainage.GENERATOR_STATS._warn_cache)
        hatalar = list(drainage.GENERATOR_STATS._error_cache)
        self.assertEqual(uyarilar, [], f'{len(uyarilar)} uyari kaldi')
        self.assertEqual(hatalar, [], f'{len(hatalar)} hata kaldi')

    def test_delta_disi_uclarin_basari_semasi_var(self):
        sema = sema_uret()

        # refresh uclari 202 doner (is kuyruga atildi), 200 degil.
        beklenen = [
            ('/api/v1/health/', 'get', '200'),
            ('/api/v1/status/', 'get', '200'),
            ('/api/v1/jobs/{job_id}/', 'get', '200'),
            ('/api/v1/refresh/', 'post', '202'),
            ('/api/v1/{section}/refresh/', 'post', '202'),
        ]
        for yol, yontem, kod in beklenen:
            with self.subTest(yol=yol):
                govde = sema['paths'][yol][yontem]['responses']
                self.assertIn(kod, govde, f'{yol} icin {kod} semasi yok')

    def test_status_semasi_operator_alanlarini_icermez(self):
        sema = sema_uret()

        metin = str(sema['components']['schemas'])
        # ADR-0006 karar 4: bunlar FetchRun'da ve admin'de yasar, /status/'ta degil
        for alan in ('by_provider', 'stopped_reason'):
            self.assertNotIn(alan, metin, f"{alan} dis semaya sizdi")

    def test_operation_id_degerleri_benzersiz(self):
        sema = sema_uret()

        kimlikler = [op['operationId']
                     for yol in sema['paths'].values()
                     for op in yol.values() if isinstance(op, dict) and 'operationId' in op]
        cakisan = {k for k in kimlikler if kimlikler.count(k) > 1}
        self.assertEqual(cakisan, set(), f'cakisan operationId: {cakisan}')

    def test_401_hata_sozlesmesi_belgelenir(self):
        sema = sema_uret()

        yanitlar = sema['paths']['/api/v1/cve/']['get']['responses']
        self.assertIn('401', yanitlar)

    def test_v1_read_throttle_scopeunu_paylasan_uclar_429_belgeler(self):
        sema = sema_uret()

        # V1APIView.throttle_scope = 'v1_read' (bkz. news/api_v1/views.py);
        # bu scope'u paylasan her uc gercekten 429 donebilir ve semada
        # belgelemelidir. HealthView ise throttle_classes = [] ile bilincli
        # olarak acik oldugundan 429 URETEMEZ ve semaya girmemelidir.
        v1_read_uclari = list(DELTA_YOLLARI.values()) + [
            '/api/v1/status/', '/api/v1/jobs/{job_id}/',
        ]
        for yol in v1_read_uclari:
            with self.subTest(yol=yol):
                yanitlar = sema['paths'][yol]['get']['responses']
                self.assertIn('429', yanitlar, f'{yol} icin 429 semasi yok')

        saglik_yanitlari = sema['paths']['/api/v1/health/']['get']['responses']
        self.assertNotIn('429', saglik_yanitlari,
                          'health tokensiz ve throttle\'suzdur, 429 belgelenmemeli')
