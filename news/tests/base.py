"""v1 view testleri icin ortak taban ve yardimcilar.

V1TestCase iki sorunu cozer:

1. Throttle sayaclari canli Redis'e yazilmaz. Test veritabani kullanici
   id'lerini 1'den baslatir; sayaclar canli Redis'e yazilsaydi gercek
   kullanicilarla (id 1 adanedhel, id 2 entegrasyon) cakisir ve onlari
   hiz sinirina takabilirdi.
2. WhiteNoise yuklenmez. Her test istemcisi middleware'i yeniden kurar ve
   WhiteNoise kurulurken staticfiles/ altindaki ~2000 dosyayi tarar; bind
   mount uzerinden bu test basina ~2 sn ekliyordu. v1 statik dosya sunmaz.
"""
import os
import uuid

import redis
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token

LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
TEST_MIDDLEWARE = [m for m in settings.MIDDLEWARE if 'whitenoise' not in m.lower()]


def test_redis_client():
    """Canli Redis sunucusuna dogrudan istemci.

    Locmem cache override altinda django_redis.get_redis_connection kullanilamaz.
    Bu istemciyle yazilan her anahtar benzersiz bir onek tasimali ve test
    sonunda silinmelidir; FLUSHDB kesinlikle kullanilmaz (db 0 canli cache'tir).
    """
    return redis.Redis.from_url(os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0'))


@override_settings(CACHES=LOCMEM_CACHE, MIDDLEWARE=TEST_MIDDLEWARE)
class V1TestCase(TestCase):
    """v1 HTTP testlerinin tabani."""

    def setUp(self):
        super().setUp()
        # Locmem cache surec boyunca yasar; throttle sayaclari testten teste tasinmasin
        cache.clear()

    def token_basligi(self):
        """Yeni bir kullanici ve token olusturup istek basligini dondurur."""
        kullanici = User.objects.create_user(f'test-{uuid.uuid4().hex[:10]}')
        token = Token.objects.create(user=kullanici)
        return {'HTTP_AUTHORIZATION': f'Token {token.key}'}
