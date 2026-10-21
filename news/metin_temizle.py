"""Kaynak metnini ceviriden once temizler (2026-10-16 uctan uca test bulgulari).

Ceviri saglayicilari bozuk girdiyi bozuk cevirir: yapisik kelimeler, cozulmemis HTML varliklari,
ham HTML, Python repr bloklari ve site kaliplari (kapanis satiri, "Related:" zinciri, yazar biyografisi)
Turkce metne aynen tasiniyordu. Uzun metin de Gemini sinirini (GEMINI_MAX_CHARS) asip yukseltmeyi
her turda reddettiriyordu.
"""
import ast
import html
import re

# Gemini siniri (12000) altinda; isaret ve ceviri genislemesi icin pay birakir
MAKALE_MAX_KARAKTER = 10000
KISALTMA_ISARETI = ' […]'

_NOKTALAMA_ONCESI = re.compile(r'\s+([,.;:!?)])')
_PARANTEZ_SONRASI = re.compile(r'\(\s+')
# Satir ici bosluk dizilerine dokunulmaz: kod/YAML ornekleri girinti ve hizalamayla anlam tasir
_OZEL_BOSLUK = re.compile(r'[\xa0  ]')
_SATIR_SONU_BOSLUK = re.compile(r'[ \t]+\n')
_FAZLA_SATIR = re.compile(r'\n{3,}')

# Yalniz noktali virgulle biten varliklar: html.unescape "&param2" icindeki "&para"yi "¶" yapar
_VARLIK = re.compile(r'&(?:#\d{1,7}|#[xX][0-9a-fA-F]{1,6}|[a-zA-Z][a-zA-Z0-9]{1,31});')

# Sayfa bileseni dokumu (MarkTechPost): class/id/style ozellikli bilesen etiketleri. Guvenlik metinlerinde
# ornek olarak gecen <a>, <meta ...>, <script> gibi etiketler konunun kendisidir; dokunulmaz.
_BILESEN_ETIKETI = re.compile(
    r'<(?:div|span|button|svg|section|canvas|input|label|select|figure|nav|ul)\b[^<>]*\b(?:class|id|style)=',
    re.I)
BILESEN_ESIGI = 3
_ATILAN_ETIKETLER = ('script', 'style', 'svg', 'noscript', 'iframe', 'canvas')

# SANS ISC tablolarindaki CVE makrosu: %%cve:2026-70201%%
_SANS_CVE = re.compile(r'%%cve:(\d{4}-\d{4,})%%', re.I)

# Google Cloud blogu (Wagtail) kod bloklarini Python repr olarak yayinlar
_REPR_BASI = 'code_block <ListValue:'
_REPR_SONU = ')])]>'
_REPR_KOD = re.compile(r"\('code', ('(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")\)", re.S)

# WordPress akis kapanisi: "The post <baslik> appeared first on MarkTechPost ."
_WP_KAPANIS = re.compile(r'\s*The post .{1,400}? appeared first on [^\n]{1,80}$', re.S)
# SecurityWeek "Related: <baslik>" baglantilari: ayni satirda baslik varsa satir sonuna kadar
# (markdown "Related:\n- ..." basligi liste icerigidir, dokunulmaz)
_RELATED = re.compile(r'[ \t]*\bRelated:[ \t]*(?=\S)[^\n]*')
# Son paragraftaki yazar biyografisi ("X is an international correspondent for SecurityWeek.")
_YAZAR_BIYO = re.compile(
    r'^[A-Z][^.\n]{0,80}\b(?:is|was) (?:an?|the) [^.\n]{0,80}\b(?:at|for) SecurityWeek\b')


def _bosluk_duzelt(metin):
    metin = _OZEL_BOSLUK.sub(' ', metin.replace('\r\n', '\n'))
    metin = _SATIR_SONU_BOSLUK.sub('\n', metin)
    return _FAZLA_SATIR.sub('\n\n', metin).strip()


def paragraf_metni(p):
    """<p> etiketinin kendi metni: satir ici etiket sinirlarinda bosluk korunur (get_text(strip=True)
    "detailedICS-Sniper" gibi yapisik kelime uretiyordu); ic ice <p> torunlari atlanir."""
    parcalar = [s for s in p.find_all(string=True) if s.find_parent('p') is p]
    metin = ' '.join(' '.join(parcalar).split())
    metin = _NOKTALAMA_ONCESI.sub(r'\1', metin)
    return _PARANTEZ_SONRASI.sub('(', metin)


def _unescape(metin):
    # Cift kacis (&amp;quot;) icin sabitlenene kadar; varlik zinciri kisa oldugundan 3 tur yeter
    for _ in range(3):
        cozulmus = _VARLIK.sub(lambda m: html.unescape(m.group(0)), metin)
        if cozulmus == metin:
            break
        metin = cozulmus
    return metin


def _repr_bloklari(metin):
    while True:
        bas = metin.find(_REPR_BASI)
        if bas < 0:
            return metin
        son = metin.find(_REPR_SONU, bas)
        if son < 0:
            # Kirpilmis blok (akis 8000 karakterde kesilmis): geri kalani anlamsiz repr
            return metin[:bas]
        kodlar = []
        for literal in _REPR_KOD.findall(metin[bas:son]):
            try:
                kodlar.append(ast.literal_eval(literal).replace('\r\n', '\n'))
            except (ValueError, SyntaxError):
                continue
        ara = '\n\n' + '\n\n'.join(k.strip() for k in kodlar if k.strip()) + '\n\n' if kodlar else ' '
        metin = metin[:bas] + ara + metin[son + len(_REPR_SONU):]


def _html_ayikla(metin):
    if len(_BILESEN_ETIKETI.findall(metin)) < BILESEN_ESIGI:
        return metin
    import warnings
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(metin, 'html.parser')
    for tag in soup.find_all(_ATILAN_ETIKETLER):
        tag.decompose()
    return soup.get_text(' ')


def _paragraf_kaliplari(metin):
    paragraflar = []
    for p in metin.split('\n\n'):
        p = _RELATED.sub('', p).strip()
        if p:
            paragraflar.append(p)
    if paragraflar and len(paragraflar[-1]) <= 600 and _YAZAR_BIYO.match(paragraflar[-1]):
        paragraflar.pop()
    return '\n\n'.join(paragraflar)


def temizle(metin):
    """Kaynak aciklamasini ceviriye hazirlar. Paragraf sinirlari (\\n\\n) ve satir sonlari korunur."""
    if not metin:
        return ''
    metin = _unescape(metin)
    metin = _repr_bloklari(metin)
    metin = _html_ayikla(metin)
    metin = _SANS_CVE.sub(r'CVE-\1', metin)
    metin = _bosluk_duzelt(metin)
    metin = _WP_KAPANIS.sub('', metin)
    return _bosluk_duzelt(_paragraf_kaliplari(metin))


def kisalt(metin, sinir=MAKALE_MAX_KARAKTER):
    """Siniri asan metni paragraf, olmazsa cumle, olmazsa kelime sinirinda keser ve isaret ekler."""
    if not metin or len(metin) <= sinir:
        return metin or ''
    pay = sinir - len(KISALTMA_ISARETI)
    parca = metin[:pay]
    for ayrac in ('\n\n', '. ', ' '):
        kesim = parca.rfind(ayrac)
        if kesim > pay // 2:
            parca = parca[:kesim + (1 if ayrac == '. ' else 0)]
            break
    return parca.rstrip() + KISALTMA_ISARETI


def baslik(metin):
    """Baslik: varliklar cozulur, bosluklar teklenir."""
    return ' '.join(_unescape(metin or '').split())


def kayit_hazirla(kayit, baslik_alani='title', aciklama_alani='description', kisaltma=True):
    """Scraper kaydini (dict) yerinde temizler; ceviriden hemen once cagrilir."""
    if kayit.get(baslik_alani):
        kayit[baslik_alani] = baslik(kayit[baslik_alani])
    if kayit.get(aciklama_alani):
        temiz = temizle(kayit[aciklama_alani])
        kayit[aciklama_alani] = kisalt(temiz) if kisaltma else temiz
    return kayit
