"""Proje test calistiricisi.

Testler API konteynerinde kosar. O konteynerde LIBRETRANSLATE_URL tanimlidir ve
Redis canli devre kesici anahtarlarini tasir. Bu calistirici iki garanti verir:

1. Hicbir test gercek LibreTranslate'e gitmez: LIBRETRANSLATE_URL testler boyunca
   bostur. LibreTranslate testleri adresi override_settings ile kendileri verir ve
   HTTP'yi mock'lar.
2. Hicbir test canli ceviri devre kesicisini okumaz veya acmaz: kapilar surec
   icidir. Aksi halde LibreTranslate/Gemini devre kesicisi acikken test sonuclari degisirdi.
3. Hicbir test gercek Gemini/OpenRouter/DeepL'e gitmez: GEMINI_API_KEY, OPENROUTER_API_KEY ve
   DEEPL_API_KEY bos, kapi/butce surec ici; testler anahtari override_settings ile verir ve HTTP'yi mock'lar.
"""
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class GuvenliTestRunner(DiscoverRunner):

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._libretranslate_kapali = override_settings(LIBRETRANSLATE_URL='')
        self._libretranslate_kapali.enable()

        from news import translation_utils as tu

        from news import translation_providers as tp
        tp._lt_gate = tu._LocalGate()

        # Hicbir test gercek Gemini/OpenRouter/DeepL'e gitmez: anahtarlar bos, kapi ve butce surec ici.
        self._gemini_kapali = override_settings(GEMINI_API_KEY='', OPENROUTER_API_KEY='', DEEPL_API_KEY='')
        self._gemini_kapali.enable()
        from news import gemini
        gemini._gate = tu._LocalGate()
        gemini._butce = gemini._LocalButce()
        from news import kayit_cevirmenleri
        for cevirmen in kayit_cevirmenleri.YEDEKLER:
            cevirmen._gate = tu._LocalGate()
            cevirmen._butce = gemini._LocalButce()
        # Canli .env'deki GEMINI_FALLBACK_MODEL testlere sizmasin (CI'da bos; konteynerde dolu oldugu
        # icin bir retranslate testi yalniz yerelde dusuyordu, 2026-11-07). Yedegi isteyen test kendisi yamalar.
        kayit_cevirmenleri.GEMINI_FALLBACK_MODEL = ''
        kayit_cevirmenleri.GEMINI2.model = ''

        # NVD hiz siniri araligi testlerde beklemesin (istekler zaten mock'lanir)
        from news import cve_scraper
        cve_scraper.NVD_ISTEK_ARALIGI = 0

    def teardown_test_environment(self, **kwargs):
        self._libretranslate_kapali.disable()
        self._gemini_kapali.disable()
        super().teardown_test_environment(**kwargs)
