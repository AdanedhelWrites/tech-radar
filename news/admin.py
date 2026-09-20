from django.contrib import admin
from django.utils.html import format_html, format_html_join

from .models import (
    AINewsEntry, CVEEntry, DevToolsEntry, FetchRun, KubernetesEntry, NewsArticle, SREEntry,
)


class CeviriKarsilastirmaMixin:
    """Orijinal ve Turkce metni detay sayfasinda yan yana gosterir (spec 3.6).

    Anlam kaymasi hicbir otomatik kontrolle yakalanamaz (ADR-0003 bolum 11.5);
    bu yuzden gozle karsilastirma yolu acik tutulur. Turkce alanlar duzenlenebilir
    kalir, karsilastirma bloku salt okunurdur.
    """

    @admin.display(description='Orijinal / Turkce karsilastirma')
    def karsilastirma(self, kayit):
        satirlar = [
            ('Baslik', kayit.original_title or '', getattr(kayit, 'turkish_title', '') or ''),
            ('Aciklama', kayit.original_description or '', kayit.turkish_description or ''),
        ]
        hucreler = format_html_join(
            '',
            '<tr>'
            '<th style="text-align:left;vertical-align:top;padding:4px 8px;">{}</th>'
            '<td style="vertical-align:top;padding:4px 8px;width:45%;">{}</td>'
            '<td style="vertical-align:top;padding:4px 8px;width:45%;">{}</td>'
            '</tr>',
            satirlar)
        return format_html(
            '<table style="width:100%;border-collapse:collapse;">'
            '<tr><th></th><th style="text-align:left;">Orijinal</th>'
            '<th style="text-align:left;">Turkce</th></tr>{}</table>',
            hucreler)

    @admin.display(description='Turkce baslik')
    def baslik_onizleme(self, kayit):
        metin = getattr(kayit, 'turkish_title', '') or kayit.original_title or ''
        return metin[:80] + ('...' if len(metin) > 80 else '')


CEVIRI_FILTRELERI = ('needs_translation', 'translation_provider')


@admin.register(NewsArticle)
class NewsArticleAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    list_display = ('baslik_onizleme', 'source', 'translation_provider', 'date', 'created_at')
    list_filter = ('source', 'date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('turkish_title', 'original_title', 'turkish_description')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'date'


@admin.register(CVEEntry)
class CVEEntryAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    list_display = ('cve_id', 'source', 'severity', 'cvss_score', 'translation_provider', 'published_date', 'created_at')
    list_filter = ('source', 'severity', 'published_date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('cve_id', 'turkish_title', 'original_title', 'turkish_description')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'published_date'


@admin.register(KubernetesEntry)
class KubernetesEntryAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    list_display = ('baslik_onizleme', 'source', 'category', 'version', 'translation_provider', 'published_date', 'created_at')
    list_filter = ('source', 'category', 'published_date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('turkish_title', 'original_title', 'turkish_description', 'version')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'published_date'


@admin.register(SREEntry)
class SREEntryAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    list_display = ('baslik_onizleme', 'source', 'translation_provider', 'published_date', 'created_at')
    list_filter = ('source', 'published_date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('turkish_title', 'original_title', 'turkish_description')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'published_date'


@admin.register(DevToolsEntry)
class DevToolsEntryAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    # DevToolsEntry ayrica version ve entry_type tasir (models.py:130-152)
    list_display = ('baslik_onizleme', 'source', 'entry_type', 'version',
                    'translation_provider', 'published_date')
    list_filter = ('source', 'entry_type', 'published_date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('turkish_title', 'original_title', 'turkish_description', 'version')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'published_date'


@admin.register(AINewsEntry)
class AINewsEntryAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    list_display = ('baslik_onizleme', 'source', 'translation_provider', 'published_date', 'created_at')
    list_filter = ('source', 'published_date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('turkish_title', 'original_title', 'turkish_description')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'published_date'


@admin.register(FetchRun)
class FetchRunAdmin(admin.ModelAdmin):
    """Salt okunur teshis ekrani; satirlari sinyaller yazar (spec 3.3)."""
    list_display = ('section', 'status', 'trigger', 'started_at', 'sure',
                    'fetched_count', 'saved_count', 'total_after', 'stopped_reason')
    list_filter = ('section', 'status', 'trigger', 'started_at')
    search_fields = ('error',)
    date_hierarchy = 'started_at'

    @admin.display(description='Sure')
    def sure(self, kayit):
        if not kayit.finished_at:
            return 'devam ediyor'
        return f'{(kayit.finished_at - kayit.started_at).total_seconds():.0f} sn'

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
