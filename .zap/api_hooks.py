"""ZAP API taramasi kancasi (zap-api-scan.py --hook). Token'i /zap/wrk/.zap/api-token.txt'den okur
ve her istege Authorization basligi ekler (replacer). Dosya yoksa kasten patlar: token'siz tarama
401'lerle "yesil" gorunurdu (P5-c, 2026-10-14). Token degeri hicbir yere basilmaz.
"""
TOKEN_DOSYASI = '/zap/wrk/.zap/api-token.txt'


def zap_started(zap, target):
    with open(TOKEN_DOSYASI, encoding='utf-8') as dosya:
        token = dosya.read().strip()
    if not token:
        raise RuntimeError('api-token.txt bos: v1 taramasi token olmadan calismaz')
    zap.replacer.add_rule(description='v1-token', enabled=True, matchtype='REQ_HEADER',
                          matchregex=False, matchstring='Authorization',
                          replacement='Token ' + token, initiators='')
