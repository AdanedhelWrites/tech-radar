"""v1 OpenAPI semasinin tanimi.

Sema metadata'si bilincli olarak view'lardan ayri tutulur: views.py zaten
imlec, filtre, hata esleme ve Celery durum cevirisi tasiyor; her uca cok
satirli dekorator eklemek dosyayi okunmaz hale getirirdi. Burada toplandiginda
"dis sozlesme neye benziyor" sorusu tek dosya okunarak yanitlanir.

Uygulama urls.py'de extend_schema_view ile yapilir. DIKKAT: extend_schema_view
view sinifini YERINDE degistirir, yeni bir sinif dondurmez -- yani views.py
metinsel olarak degismese de calisma zamaninda siniflar dekore edilir.
"""

V1_ONEKI = '/api/v1/'


def yalniz_v1(endpoints):
    """Semayi /api/v1/ ile sinirlar (preprocessing hook).

    Eski /api/* uclari frontend'e hizmet eder ve ADR-0003 onlara dis sozlesme
    vermez. Bu filtre olmadan semaya 30 eski yol girer ve istemeden sozlesme
    haline gelirler.
    """
    return [dortlu for dortlu in endpoints if dortlu[0].startswith(V1_ONEKI)]
