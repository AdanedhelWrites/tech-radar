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
