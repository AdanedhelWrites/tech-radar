from django.db import models

class NewsArticle(models.Model):
    """Haber modeli"""
    source = models.CharField(max_length=100, verbose_name='Kaynak')
    original_title = models.TextField(verbose_name='Orijinal Baslik')
    turkish_title = models.TextField(verbose_name='Turkce Baslik')
    original_description = models.TextField(verbose_name='Orijinal Aciklama', blank=True)
    turkish_description = models.TextField(verbose_name='Turkce Aciklama', blank=True)
    turkish_summary = models.TextField(verbose_name='Turkce Ozet', blank=True)
    link = models.URLField(verbose_name='Link')
    date = models.DateField(verbose_name='Tarih')
    original_date = models.CharField(max_length=100, verbose_name='Orijinal Tarih')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Olusturulma Tarihi')
    
    class Meta:
        verbose_name = 'Haber'
        verbose_name_plural = 'Haberler'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return self.turkish_title[:100]


class CVEEntry(models.Model):
    """CVE (Common Vulnerabilities and Exposures) modeli"""
    cve_id = models.CharField(max_length=50, unique=True, verbose_name='CVE ID')
    source = models.CharField(max_length=100, verbose_name='Kaynak')
    original_title = models.TextField(verbose_name='Orijinal Baslik')
    turkish_title = models.TextField(verbose_name='Turkce Baslik', blank=True)
    original_description = models.TextField(verbose_name='Orijinal Aciklama')
    turkish_description = models.TextField(verbose_name='Turkce Aciklama', blank=True)
    severity = models.CharField(max_length=20, verbose_name='Siddet', blank=True)
    cvss_score = models.FloatField(null=True, blank=True, verbose_name='CVSS Skoru')
    published_date = models.DateField(verbose_name='Yayinlanma Tarihi')
    modified_date = models.DateField(null=True, blank=True, verbose_name='Guncelleme Tarihi')
    link = models.URLField(verbose_name='Link')
    cwe_ids = models.JSONField(default=list, blank=True, verbose_name='CWE IDleri')
    references = models.JSONField(default=list, blank=True, verbose_name='Referanslar')
    affected_products = models.TextField(blank=True, verbose_name='Etkilenen Urunler')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Olusturulma Tarihi')
    
    class Meta:
        verbose_name = 'CVE Kaydi'
        verbose_name_plural = 'CVE Kayitlari'
        ordering = ['-published_date', '-created_at']
    
    def __str__(self):
        return f"{self.cve_id} - {self.turkish_title[:50] if self.turkish_title else self.original_title[:50]}"


class KubernetesEntry(models.Model):
    """Kubernetes haber/guncelleme modeli"""
    CATEGORY_CHOICES = [
        ('release', 'Release'),
        ('security', 'Security'),
        ('feature', 'Feature'),
        ('ecosystem', 'Ecosystem'),
        ('blog', 'Blog'),
    ]

    source = models.CharField(max_length=100, verbose_name='Kaynak')
    original_title = models.TextField(verbose_name='Orijinal Baslik')
    turkish_title = models.TextField(verbose_name='Turkce Baslik', blank=True)
    original_description = models.TextField(verbose_name='Orijinal Aciklama')
    turkish_description = models.TextField(verbose_name='Turkce Aciklama', blank=True)
    link = models.URLField(verbose_name='Link', unique=True)
    published_date = models.DateField(verbose_name='Yayinlanma Tarihi')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='blog', verbose_name='Kategori')
    version = models.CharField(max_length=30, blank=True, verbose_name='Surum')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Olusturulma Tarihi')

    class Meta:
        verbose_name = 'Kubernetes Haberi'
        verbose_name_plural = 'Kubernetes Haberleri'
        ordering = ['-published_date', '-created_at']

    def __str__(self):
        return f"[{self.category}] {self.turkish_title[:60] if self.turkish_title else self.original_title[:60]}"


class SREEntry(models.Model):
    """SRE (Site Reliability Engineering) haber modeli"""
    source = models.CharField(max_length=100, verbose_name='Kaynak')
    original_title = models.TextField(verbose_name='Orijinal Baslik')
    turkish_title = models.TextField(verbose_name='Turkce Baslik', blank=True)
    original_description = models.TextField(verbose_name='Orijinal Aciklama')
    turkish_description = models.TextField(verbose_name='Turkce Aciklama', blank=True)
    link = models.URLField(verbose_name='Link', max_length=500, unique=True)
    published_date = models.DateField(verbose_name='Yayinlanma Tarihi')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Olusturulma Tarihi')

    class Meta:
        verbose_name = 'SRE Haberi'
        verbose_name_plural = 'SRE Haberleri'
        ordering = ['-published_date', '-created_at']

    def __str__(self):
        return self.turkish_title[:100] if self.turkish_title else self.original_title[:100]


class DevToolsEntry(models.Model):
    """DevTools (Altyapi Araclari) guncelleme modeli"""
    ENTRY_TYPE_CHOICES = [
        ('release', 'Release'),
        ('blog', 'Blog'),
        ('news', 'News'),
    ]

    source = models.CharField(max_length=100, verbose_name='Kaynak')
    original_title = models.TextField(verbose_name='Orijinal Baslik')
    turkish_title = models.TextField(verbose_name='Turkce Baslik', blank=True)
    original_description = models.TextField(verbose_name='Orijinal Aciklama')
    turkish_description = models.TextField(verbose_name='Turkce Aciklama', blank=True)
    link = models.URLField(verbose_name='Link', max_length=500, unique=True)
    published_date = models.DateField(verbose_name='Yayinlanma Tarihi')
    version = models.CharField(max_length=100, blank=True, verbose_name='Surum')
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES, default='release', verbose_name='Tur')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Olusturulma Tarihi')

    class Meta:
        verbose_name = 'DevTools Guncellemesi'
        verbose_name_plural = 'DevTools Guncellemeleri'
        ordering = ['-published_date', '-created_at']

    def __str__(self):
        return f"[{self.source}] {self.turkish_title[:60] if self.turkish_title else self.original_title[:60]}"


class AINewsEntry(models.Model):
    """Yapay Zeka (AI) haber ve benchmark modeli"""
    source = models.CharField(max_length=100, verbose_name='Kaynak')
    original_title = models.TextField(verbose_name='Orijinal Baslik')
    turkish_title = models.TextField(verbose_name='Turkce Baslik', blank=True)
    original_description = models.TextField(verbose_name='Orijinal Aciklama')
    turkish_description = models.TextField(verbose_name='Turkce Aciklama', blank=True)
    link = models.URLField(verbose_name='Link', max_length=500, unique=True)
    published_date = models.DateField(verbose_name='Yayinlanma Tarihi')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Olusturulma Tarihi')

    class Meta:
        verbose_name = 'AI Haberi'
        verbose_name_plural = 'AI Haberleri'
        ordering = ['-published_date', '-created_at']

    def __str__(self):
        return self.turkish_title[:100] if self.turkish_title else self.original_title[:100]
