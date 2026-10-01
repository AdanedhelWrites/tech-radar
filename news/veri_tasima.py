"""Faz B1: SQLite <-> PostgreSQL kayipsiz veri tasima yardimcilari (spec 2.3-2.4, 5.3).

Django'nun hazir serilestiricileri kayiplidir: JSON datetime'i milisaniyeye
kirpar (v1 imleci mikrosaniye tasir), XML metin alanlarini strip eder ve CR'i
kaybeder. Burada yazim JSON'dur ama datetime isoformat() ile tam yazilir; yukleme
standart `loaddata`'dir (raw=True: auto_now updated_at'i ezmez; sequence'leri
kendisi sifirlar).

Ozet serilestiriciden bagimsizdir: iki veritabaninda ayni cikiyorsa tasima kayipsizdir.
"""
import hashlib
import json
from datetime import datetime

from django.apps import apps
from django.core import serializers
from django.core.serializers.json import DjangoJSONEncoder

# migrate'in kendisinin urettigi ya da tasinmasi anlamsiz tablolar
HARIC = frozenset({
    'contenttypes.contenttype', 'auth.permission', 'sessions.session', 'admin.logentry',
})


class TamHassasKodlayici(DjangoJSONEncoder):
    """DjangoJSONEncoder'in datetime'i milisaniyeye kirpmasini engeller."""

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)


def tasinacak_modeller():
    """Tasinacak modeller, yukleme sirasina gore (bagimlilar sonra)."""
    adaylar = [
        model for model in apps.get_models()
        if not model._meta.proxy and model._meta.managed
        and model._meta.label_lower not in HARIC
    ]
    return serializers.sort_dependencies([(None, adaylar)], allow_cycles=True)


def _kanonik(deger):
    if isinstance(deger, datetime):
        return deger.isoformat()
    if isinstance(deger, (dict, list)):
        # jsonb nesne anahtar sirasini korumaz; listeler sirayi korur
        return json.dumps(deger, sort_keys=True, ensure_ascii=False)
    return deger


def _hedef_kanonik(hedef):
    """M2M hedefi: dogal anahtar varsa o (Permission id'leri veritabanlari arasinda
    farklidir), yoksa pk."""
    if hasattr(hedef, 'natural_key'):
        return repr(hedef.natural_key())
    return repr(hedef.pk)


def ozet():
    """Model basina (etiket, satir sayisi, tum alanlarin sha256'si, delta sha256'si).

    Alan ozeti, otomatik olusan many-to-many iliskileri de kapsar (User.groups,
    User.user_permissions, Group.permissions): hedefler dogal anahtarla ozetlenir.
    Delta ozeti v1 imlec sirasidir: updated_at ASC, id ASC. updated_at alani
    olmayan modelde '-'.
    """
    satirlar = []
    for model in tasinacak_modeller():
        alanlar = [alan.attname for alan in model._meta.concrete_fields]
        alan_ozeti = hashlib.sha256()
        sayi = 0
        for satir in model._default_manager.order_by('pk').values_list(*alanlar).iterator():
            sayi += 1
            alan_ozeti.update(repr(tuple(_kanonik(v) for v in satir)).encode('utf-8'))
        for alan in model._meta.many_to_many:
            if not alan.remote_field.through._meta.auto_created:
                continue
            nesneler = model._default_manager.order_by('pk').prefetch_related(alan.name)
            for nesne in nesneler.iterator(chunk_size=500):
                hedefler = sorted(_hedef_kanonik(h) for h in getattr(nesne, alan.name).all())
                alan_ozeti.update(f'{nesne.pk}|{alan.name}|{hedefler};'.encode('utf-8'))
        delta = '-'
        if any(alan.name == 'updated_at' for alan in model._meta.concrete_fields):
            delta_ozeti = hashlib.sha256()
            sirali = model._default_manager.order_by('updated_at', 'id')
            for guncellendi, kimlik in sirali.values_list('updated_at', 'id').iterator():
                delta_ozeti.update(f'{guncellendi.isoformat()}|{kimlik};'.encode('utf-8'))
            delta = delta_ozeti.hexdigest()
        satirlar.append((model._meta.label, sayi, alan_ozeti.hexdigest(), delta))
    return satirlar


def yaz(akis):
    """Tasinacak tum modelleri `akis`'a tam hassasiyetli JSON olarak yazar.

    pk'ler aynen yazilir (dogal birincil anahtar kullanilmaz; auth.User pk'si
    korunur). Dogal yabanci anahtarlar ContentType/Permission referanslari
    icindir: hedefte bu tablolari migrate yeniden uretir.
    Donus: model etiketi -> yazilan nesne sayisi.
    """
    sayilar = {}

    def nesneler():
        for model in tasinacak_modeller():
            sayi = 0
            for nesne in model._default_manager.order_by('pk').iterator():
                sayi += 1
                yield nesne
            sayilar[model._meta.label] = sayi

    serializers.serialize(
        'json', nesneler(), stream=akis, cls=TamHassasKodlayici, indent=1,
        use_natural_foreign_keys=True, use_natural_primary_keys=False)
    return sayilar
