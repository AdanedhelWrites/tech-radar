"""Ceviri dogrulugu testleri (spec bolum 9, A3 plani H5/H6).

2026-09-12'de 19 CVE kaydi 'cevrildi' isaretliyken Turkce aciklamasinda ham
XTRM yer tutucusu tasiyordu. Bu testler o iki hatayi ve yeni dogrulama
kurallarini korur. Google hicbir testte cagrilmaz.
"""
import re
from unittest import mock

from django.test import SimpleTestCase, TestCase

from news import translation_utils as tu
from news.tests.test_translation import FakeTranslator, TranslationGateMixin

KALINTI = re.compile(r'XTRM\d{4}X')


class YerTutucuGeriKoymaTests(SimpleTestCase):

    def setUp(self):
        tu.consume_translation_failures()

    def test_ic_ice_yer_tutucu_tamamen_geri_konur(self):
        """URL deseni onceden korunmus bir kod parcasinin yer tutucusunu yutabilir (H5)."""
        metin = 'Update the image at https://example.com/`v1.2` before rollout.'
        korunmus, esleme = tu._protect_terms(metin)
        self.assertTrue(any(KALINTI.search(deger) for deger in esleme.values()),
                        'On kosul: bu girdi ic ice yer tutucu uretmeli')

        self.assertEqual(tu._restore_terms(korunmus, esleme), metin)

    def test_bozuk_donen_yer_tutucu_onarilip_geri_konur(self):
        """Google 'xtrm 0001x' dondurebilir; onarma geri koymadan ONCE yapilmali (H6)."""
        metin = 'The Kubernetes scheduler crashed today.'
        with mock.patch.object(tu, '_translate_via_google',
                               return_value='xtrm 0001x zamanlayıcısı bugün çöktü.'):
            sonuc = tu.translate_text(metin)

        self.assertEqual(sonuc, 'Kubernetes zamanlayıcısı bugün çöktü.')
        self.assertIsNone(KALINTI.search(sonuc))
        self.assertEqual(tu.consume_translation_failures(), 0)
