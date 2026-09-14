"""Ceviri saglayici zinciri testleri icin sahte saglayicilar. Ag erisimi yok."""
from unittest import mock

from news import translation_providers as tp


class SahteSaglayici:
    """Saglayici arayuzunu uygular.

    cevap: korunmus metni alan bir fonksiyon, sozluk (bilinmeyen anahtara None)
    veya sabit bir deger. None, saglayicinin erisilemedigi anlamina gelir.
    """

    def __init__(self, name, cevap=None, hazir=True):
        self.name = name
        self._cevap = cevap
        self.hazir = hazir
        self.cagrilar = []

    def available(self):
        return self.hazir

    def translate(self, protected):
        self.cagrilar.append(protected)
        if callable(self._cevap):
            return self._cevap(protected)
        if isinstance(self._cevap, dict):
            return self._cevap.get(protected)
        return self._cevap


class SaglayiciZinciriMixin:

    def saglayicilari_ayarla(self, *saglayicilar):
        yama = mock.patch.object(tp, 'SAGLAYICILAR', tuple(saglayicilar))
        yama.start()
        self.addCleanup(yama.stop)
        return saglayicilar
