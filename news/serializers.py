from rest_framework import serializers
from .models import NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry


class NewsArticleSerializer(serializers.ModelSerializer):
    """Haber serializer"""
    
    class Meta:
        model = NewsArticle
        fields = '__all__'


class CVEEntrySerializer(serializers.ModelSerializer):
    """CVE serializer"""
    
    class Meta:
        model = CVEEntry
        fields = '__all__'


def _kaynak_listesi():
    """Eski fetch uclarinin kaynak secimi. Bilinmeyen adlari scraper'lar zaten eler;
    burada yalnizca boyut sinirlanir (anonim istek, 2026-09-30)."""
    return serializers.ListField(
        child=serializers.CharField(max_length=100),
        required=False,
        allow_empty=True,
        max_length=20,
    )


class FetchNewsRequestSerializer(serializers.Serializer):
    """Haber çekme isteği serializer"""
    days = serializers.IntegerField(default=7, min_value=1, max_value=30)
    sources = _kaynak_listesi()


class FetchCVERequestSerializer(serializers.Serializer):
    """CVE çekme isteği serializer"""
    # Varsayilan 7: fetch_cves'in eski davranisi ve fetch_cve_task varsayilani ile ayni
    days = serializers.IntegerField(default=7, min_value=1, max_value=90)
    sources = _kaynak_listesi()


class KubernetesEntrySerializer(serializers.ModelSerializer):
    """Kubernetes serializer"""

    class Meta:
        model = KubernetesEntry
        fields = '__all__'


class FetchK8sRequestSerializer(serializers.Serializer):
    """Kubernetes haber cekme istegi serializer"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=90)
    sources = _kaynak_listesi()


class SREEntrySerializer(serializers.ModelSerializer):
    """SRE serializer"""

    class Meta:
        model = SREEntry
        fields = '__all__'


class FetchSRERequestSerializer(serializers.Serializer):
    """SRE haber cekme istegi serializer"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=90)
    sources = _kaynak_listesi()


class DevToolsEntrySerializer(serializers.ModelSerializer):
    """DevTools serializer"""

    class Meta:
        model = DevToolsEntry
        fields = '__all__'


class FetchDevToolsRequestSerializer(serializers.Serializer):
    """DevTools guncelleme cekme istegi serializer"""
    days = serializers.IntegerField(default=60, min_value=1, max_value=120)
    sources = _kaynak_listesi()


class StatsSerializer(serializers.Serializer):
    """Istatistikler serializer"""
    total = serializers.IntegerField()
    by_source = serializers.DictField(child=serializers.IntegerField())
    last_update = serializers.DateTimeField(allow_null=True)
    cached = serializers.BooleanField()


class AINewsEntrySerializer(serializers.ModelSerializer):
    """AI Haber serializer"""

    class Meta:
        model = AINewsEntry
        fields = '__all__'


class FetchAINewsRequestSerializer(serializers.Serializer):
    """AI Haber cekme istegi serializer"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=90)
    sources = _kaynak_listesi()
