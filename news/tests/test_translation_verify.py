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


UZUN_METIN = ('The researchers published a detailed report describing how the '
              'vulnerability can be exploited remotely.')  # 103 karakter


class CeviriDogrulamaTests(TranslationGateMixin, TestCase):
    """Guvenilmez ceviri: metin orijinal kalir, sayac artar, Google'a tekrar
    gidilmez ve devre kesici acilmaz."""

    def _cevir(self, metin, google_cevabi):
        cevirmen = self.use_translator(FakeTranslator(default=google_cevabi))
        return tu.translate_text(metin), cevirmen

    def _basarisiz_sayildi(self, sonuc, metin, cevirmen):
        self.assertEqual(sonuc, metin)
        self.assertEqual(tu.consume_translation_failures(), 1)
        self.assertEqual(len(cevirmen.calls), 1, 'Dogrulama hatasi yeniden deneme tetiklememeli')
        self.assertFalse(tu._gate.cooldown_active(), 'Dogrulama hatasi devre kesiciyi acmamali')

    def test_yanki_basarisiz_sayilir(self):
        metin = 'Attackers exploited the flaw to steal session cookies.'
        sonuc, cevirmen = self._cevir(metin, metin)
        self._basarisiz_sayildi(sonuc, metin, cevirmen)

    def test_yanki_bosluk_ve_buyuk_harf_farkini_yok_sayar(self):
        metin = 'Attackers exploited the flaw to steal session cookies.'
        sonuc, cevirmen = self._cevir(metin, '  ' + metin.upper() + ' ')
        self._basarisiz_sayildi(sonuc, metin, cevirmen)

    def test_dort_kelimeden_kisa_yanki_basari_sayilir(self):
        sonuc, _ = self._cevir('Security patch released', 'Security patch released')
        self.assertEqual(sonuc, 'Security patch released')
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_terimlerden_olusan_yanki_basari_sayilir(self):
        """Yer tutucular kelime sayilmaz: 'Kubernetes v1.31.0' cevrilecek kelime icermez."""
        metin = 'Kubernetes v1.31.0'
        korunmus, _ = tu._protect_terms(metin)
        sonuc, _ = self._cevir(metin, korunmus)
        self.assertEqual(sonuc, 'Kubernetes v1.31.0')
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_terim_agirlikli_metin_yanki_basari_sayilir(self):
        metin = 'kubectl apply on Windows nodes'  # cevrilecek kelime: apply, on
        korunmus, _ = tu._protect_terms(metin)
        self._cevir(metin, korunmus)
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_kirpilma_basarisiz_sayilir(self):
        sonuc, cevirmen = self._cevir(UZUN_METIN, 'Araştırmacılar rapor yayımladı.')
        self._basarisiz_sayildi(sonuc, UZUN_METIN, cevirmen)

    def test_kisa_metinde_kisalma_basari_sayilir(self):
        sonuc, _ = self._cevir('The fix is available now for all users.', 'Düzeltme hazır.')
        self.assertEqual(sonuc, 'Düzeltme hazır.')
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_normal_uzun_ceviri_basari_sayilir(self):
        ceviri = ('Araştırmacılar, güvenlik açığının uzaktan nasıl istismar '
                  'edilebileceğini anlatan ayrıntılı bir rapor yayımladı.')
        sonuc, _ = self._cevir(UZUN_METIN, ceviri)
        self.assertEqual(sonuc, ceviri)
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_eksik_yer_tutucu_basarisiz_sayilir(self):
        """Google bir yer tutucuyu dusururse korunan terim Turkce metinden sessizce kaybolurdu."""
        metin = 'Upgrade Kubernetes before applying the Helm chart changes.'
        _, esleme = tu._protect_terms(metin)
        kube = next(kod for kod, deger in esleme.items() if deger == 'Kubernetes')
        sonuc, cevirmen = self._cevir(
            metin, f'Grafik değişikliklerini uygulamadan önce {kube} sürümünü yükseltin.')
        self._basarisiz_sayildi(sonuc, metin, cevirmen)

    def test_geri_konamayan_yer_tutucu_basarisiz_sayilir(self):
        """Son emniyet kontrolu: geri koyma herhangi bir sebeple eksik kalirsa kayit 'cevrildi' sayilmaz."""
        metin = 'Upgrade Kubernetes before applying the Helm chart changes.'
        korunmus, esleme = tu._protect_terms(metin)
        google = korunmus.replace('Upgrade', 'Yükseltin:').replace('before applying the', 'önce').replace('chart changes', 'değişiklikleri')
        with mock.patch.object(tu, '_restore_terms', side_effect=lambda metin_, esleme_: metin_):
            sonuc, _ = self._cevir(metin, google)
        self.assertEqual(sonuc, metin)
        self.assertEqual(tu.consume_translation_failures(), 1)

    def test_dis_katmanin_yer_tutuculari_kalinti_sayilmaz(self):
        """k8s_scraper metni kendisi korumaya alip verir; o kodlari dis katman geri koyar."""
        metin = 'XTRM0007X crashes when XTRM0008X is restarted on the host machine.'
        ceviri = 'XTRM0007X, ana makinede XTRM0008X yeniden başlatıldığında çöküyor.'
        sonuc, _ = self._cevir(metin, ceviri)
        self.assertEqual(sonuc, ceviri)
        self.assertEqual(tu.consume_translation_failures(), 0)


class VerifyTranslationTests(SimpleTestCase):
    """Saf fonksiyon: sebep metinleri loglarda gorunur, sozlesmenin parcasidir."""

    def test_sebepler(self):
        self.assertIsNone(tu.verify_translation('Hello world', 'Merhaba dünya', []))
        self.assertEqual(tu.verify_translation('a XTRM0001X b', 'a b', ['XTRM0001X']), 'eksik yer tutucu (1)')
        self.assertEqual(tu.verify_translation('one two three four', 'One two three four', []), 'yanki')
        self.assertEqual(tu.verify_translation(UZUN_METIN, 'Kısa.', []), 'kirpilma')
