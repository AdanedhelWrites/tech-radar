"""Django'nun kendisinin eklemedigi guvenlik basliklari (ZAP 10063, 90004; GUVENLIK-PLANI 2026-10-08).

SecurityMiddleware zaten X-Content-Type-Options, Referrer-Policy ve Cross-Origin-Opener-Policy'yi,
XFrameOptionsMiddleware X-Frame-Options'i, django-csp Content-Security-Policy'yi ekler. Burada kalan uc:

- Permissions-Policy: uygulama hicbir tarayici ozelligi (kamera, mikrofon, konum, odeme, USB...) kullanmaz;
  hepsi kapali. Tek kaynak bu modul; degistirmek icin listeyi duzenleyin.
- Cross-Origin-Resource-Policy: same-origin. Yanitlar (API JSON, admin, statik) yalniz ayni origin'den ve
  frontend proxy'sinden (Vite / Nginx, tarayici icin ayni origin) tuketilir.
- Cross-Origin-Embedder-Policy: require-corp. Sayfalar yalniz kendi origin'inden kaynak yukler
  (Swagger UI sidecar /static altinda); cross-origin gomme yok.

Mevcut bir baslik ezilmez: bir view bilerek farkli deger vermisse o kalir.
"""

KAPALI_OZELLIKLER = (
    'accelerometer', 'autoplay', 'camera', 'display-capture', 'geolocation', 'gyroscope',
    'magnetometer', 'microphone', 'midi', 'payment', 'picture-in-picture', 'publickey-credentials-get',
    'screen-wake-lock', 'usb', 'xr-spatial-tracking',
)

PERMISSIONS_POLICY = ', '.join(f'{ozellik}=()' for ozellik in KAPALI_OZELLIKLER)

BASLIKLAR = {
    'Permissions-Policy': PERMISSIONS_POLICY,
    'Cross-Origin-Resource-Policy': 'same-origin',
    'Cross-Origin-Embedder-Policy': 'require-corp',
}


class GuvenlikBasliklariMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        for ad, deger in BASLIKLAR.items():
            if not response.has_header(ad):
                response[ad] = deger
        return response
