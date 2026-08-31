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


class FetchNewsRequestSerializer(serializers.Serializer):
    """Haber çekme isteği serializer"""
    days = serializers.IntegerField(default=7, min_value=1, max_value=30)
    sources = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )


class FetchCVERequestSerializer(serializers.Serializer):
    """CVE çekme isteği serializer"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=90)
    sources = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )


class KubernetesEntrySerializer(serializers.ModelSerializer):
    """Kubernetes serializer"""

    class Meta:
        model = KubernetesEntry
        fields = '__all__'


class FetchK8sRequestSerializer(serializers.Serializer):
    """Kubernetes haber cekme istegi serializer"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=90)
    sources = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )


class SREEntrySerializer(serializers.ModelSerializer):
    """SRE serializer"""

    class Meta:
        model = SREEntry
        fields = '__all__'


class FetchSRERequestSerializer(serializers.Serializer):
    """SRE haber cekme istegi serializer"""
    days = serializers.IntegerField(default=30, min_value=1, max_value=90)
    sources = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )


class DevToolsEntrySerializer(serializers.ModelSerializer):
    """DevTools serializer"""

    class Meta:
        model = DevToolsEntry
        fields = '__all__'


class FetchDevToolsRequestSerializer(serializers.Serializer):
    """DevTools guncelleme cekme istegi serializer"""
    days = serializers.IntegerField(default=60, min_value=1, max_value=120)
    sources = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )


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
    sources = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )
