"""Proje test calistiricisi.

Testler API konteynerinde kosar. O konteynerde LIBRETRANSLATE_URL tanimlidir ve
Redis canli devre kesici anahtarlarini tasir. Bu calistirici iki garanti verir:

1. Hicbir test gercek LibreTranslate'e gitmez: LIBRETRANSLATE_URL testler boyunca
   bostur. LibreTranslate testleri adresi override_settings ile kendileri verir ve
   HTTP'yi mock'lar.
2. Hicbir test canli ceviri devre kesicisini okumaz veya acmaz: kapilar surec
   icidir. Aksi halde Google canlida kisitliyken test sonuclari degisirdi.
"""
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class GuvenliTestRunner(DiscoverRunner):

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._libretranslate_kapali = override_settings(LIBRETRANSLATE_URL='')
        self._libretranslate_kapali.enable()

        from news import translation_utils as tu
        tu._gate = tu._LocalGate()

        from news import translation_providers as tp
        tp._lt_gate = tu._LocalGate()

    def teardown_test_environment(self, **kwargs):
        self._libretranslate_kapali.disable()
        super().teardown_test_environment(**kwargs)
