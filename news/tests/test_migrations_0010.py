"""Migration 0010: translation_provider secenegine 'gemini' eklenir; sema ve veri degismez."""
from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)


class GeminiSecenegiTests(TestCase):

    def test_alti_modelde_gemini_secenegi_var(self):
        for model in (AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry):
            secenekler = [kod for kod, _ in model._meta.get_field('translation_provider').choices]
            self.assertEqual(secenekler, ['google', 'libretranslate', 'gemini'], model.__name__)

    def test_migration_eksigi_yok(self):
        cikti = StringIO()
        call_command('makemigrations', 'news', '--check', '--dry-run', stdout=cikti)
        self.assertIn('No changes detected', cikti.getvalue())
