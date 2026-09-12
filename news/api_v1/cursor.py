"""Imlec (cursor) kodlama ve cozme.

Imlec, (updated_at, id) ikilisinin base64url ile kodlanmis halidir. Tuketici
acisindan opaktir: icini acmamali, yalnizca saklayip geri gondermelidir. Boylece
ic bicimi ileride degistirebiliriz.

Neden sadece zaman damgasi yetmez: ayni mikrosaniyede yazilmis iki kayit varsa
tek basina updated_at ile sayfalama bunlardan birini atlar. id ikinci anahtar
olarak bu belirsizligi kaldirir.
"""
import base64
import json
from datetime import datetime

from django.db.models import Q
from django.utils.dateparse import parse_datetime


class InvalidCursor(ValueError):
    """Imlec cozulemedi."""


def encode_cursor(updated_at: datetime, pk: int) -> str:
    """(updated_at, id) ikilisini opak bir metne cevirir."""
    yuk = json.dumps({'u': updated_at.isoformat(), 'i': int(pk)}, separators=(',', ':'))
    kodlu = base64.urlsafe_b64encode(yuk.encode('utf-8')).decode('ascii')
    return kodlu.rstrip('=')


def decode_cursor(value: str):
    """Imleci (updated_at, id) ikilisine cevirir. Cozulemezse InvalidCursor firlatir."""
    if not value:
        raise InvalidCursor('Imlec bos olamaz.')
    dolgulu = value + '=' * (-len(value) % 4)
    try:
        yuk = json.loads(base64.urlsafe_b64decode(dolgulu.encode('ascii')))
        moment = parse_datetime(yuk['u'])
        pk = int(yuk['i'])
    except Exception as hata:
        raise InvalidCursor(f'Imlec cozulemedi: {hata}')
    if moment is None:
        raise InvalidCursor('Imlec icindeki tarih cozulemedi.')
    return moment, pk


def apply_cursor(queryset, moment: datetime, pk: int):
    """Imlecten sonraki kayitlari birakir (keyset sayfalama).

    (updated_at, id) > (moment, pk) kosulunun ORM karsiligi. Satir karsilastirmasi
    yerine Q kullaniliyor; bu bicim hem SQLite hem PostgreSQL'de calisir.
    """
    return queryset.filter(Q(updated_at__gt=moment) | Q(updated_at=moment, id__gt=pk))
