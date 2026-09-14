"""v1 serializer'lari.

Alanlar tek tek yazilir; fields = '__all__' kullanilmaz. Boylece modele alan
eklendiginde dis sozlesme kendiliginden degismez.

Dil varyantlari ic ice verilir (title.original / title.tr). Tuketici
`title.tr || title.original` yazarak ceviri bekleyen kayitlarda otomatik
olarak Ingilizceye duser.
"""
from rest_framework import serializers

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)

# Veritabani siddeti Turkce saklar; dis sozlesme makine dostu kod kullanir.
SEVERITY_TR_TO_CODE = {
    'Kritik': 'critical',
    'Yüksek': 'high',
    'Orta': 'medium',
    'Düşük': 'low',
}
SEVERITY_CODE_TO_TR = {kod: tr for tr, kod in SEVERITY_TR_TO_CODE.items()}

# Dusukten yuksege; min_severity filtresi bu siralamayi kullanir.
SEVERITY_ORDER = ['low', 'medium', 'high', 'critical']


class BaseEntrySerializer(serializers.ModelSerializer):
    """Alti bolumun ortak alanlari."""

    entry_type_name = None  # alt siniflar doldurur

    type = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    translation_provider = serializers.SerializerMethodField()

    ORTAK_ALANLAR = [
        'id', 'type', 'source', 'title', 'description', 'link',
        'published_date', 'needs_translation', 'updated_at', 'translation_provider',
    ]

    def get_type(self, obj):
        return self.entry_type_name

    def get_title(self, obj):
        return {'original': obj.original_title, 'tr': obj.turkish_title}

    def get_description(self, obj):
        return {'original': obj.original_description, 'tr': obj.turkish_description}

    def get_translation_provider(self, obj):
        # 'google', 'libretranslate' veya ceviri yoksa null. Tuketici
        # 'libretranslate' icin "makine cevirisi" etiketi gosterebilir.
        return obj.translation_provider or None


class NewsArticleV1Serializer(BaseEntrySerializer):
    entry_type_name = 'news'
    # NewsArticle tarih alanini `date` olarak tutar; sozlesmede published_date olur.
    published_date = serializers.DateField(source='date', read_only=True)
    summary_tr = serializers.CharField(source='turkish_summary', read_only=True)

    class Meta:
        model = NewsArticle
        fields = BaseEntrySerializer.ORTAK_ALANLAR + ['summary_tr', 'original_date']


class CVEEntryV1Serializer(BaseEntrySerializer):
    entry_type_name = 'cve'
    severity = serializers.SerializerMethodField()

    class Meta:
        model = CVEEntry
        fields = BaseEntrySerializer.ORTAK_ALANLAR + [
            'cve_id', 'severity', 'cvss_score', 'cwe_ids', 'references',
            'affected_products', 'modified_date',
        ]

    def get_severity(self, obj):
        return {'code': SEVERITY_TR_TO_CODE.get(obj.severity), 'label': obj.severity}


class KubernetesEntryV1Serializer(BaseEntrySerializer):
    entry_type_name = 'kubernetes'

    class Meta:
        model = KubernetesEntry
        fields = BaseEntrySerializer.ORTAK_ALANLAR + ['category', 'version']


class SREEntryV1Serializer(BaseEntrySerializer):
    entry_type_name = 'sre'

    class Meta:
        model = SREEntry
        fields = BaseEntrySerializer.ORTAK_ALANLAR


class DevToolsEntryV1Serializer(BaseEntrySerializer):
    entry_type_name = 'devtools'

    class Meta:
        model = DevToolsEntry
        fields = BaseEntrySerializer.ORTAK_ALANLAR + ['entry_type', 'version']


class AINewsEntryV1Serializer(BaseEntrySerializer):
    entry_type_name = 'ai'

    class Meta:
        model = AINewsEntry
        fields = BaseEntrySerializer.ORTAK_ALANLAR
