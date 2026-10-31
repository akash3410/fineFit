"""
Tests for the seed_demo_catalog management command.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.catalog.models import Category, Product, ProductVariant


class SeedDemoCatalogCommandTest(TestCase):
    """Test the seed_demo_catalog management command."""

    def setUp(self):
        """Clear catalog data before each test."""
        ProductVariant.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()

    @override_settings(DEBUG=True)
    def test_seed_command_creates_data(self):
        """Test that seed command creates categories, products, and variants."""
        out = StringIO()
        call_command('seed_demo_catalog', stdout=out)
        
        self.assertTrue(Category.objects.filter(is_active=True).exists())
        self.assertGreaterEqual(Category.objects.count(), 4)
        self.assertTrue(Product.objects.filter(is_published=True).exists())
        self.assertGreaterEqual(Product.objects.count(), 8)
        self.assertTrue(ProductVariant.objects.filter(is_active=True).exists())
        self.assertGreaterEqual(ProductVariant.objects.count(), 20)
        output = out.getvalue()
        self.assertIn('Demo catalog seeded successfully', output)

    @override_settings(DEBUG=True)
    def test_seed_command_idempotent(self):
        """Test that running seed command twice doesn't create duplicates."""
        call_command('seed_demo_catalog')
        cats_count_1 = Category.objects.count()
        prods_count_1 = Product.objects.count()
        vars_count_1 = ProductVariant.objects.count()
        
        call_command('seed_demo_catalog')
        cats_count_2 = Category.objects.count()
        prods_count_2 = Product.objects.count()
        vars_count_2 = ProductVariant.objects.count()
        
        self.assertEqual(cats_count_1, cats_count_2)
        self.assertEqual(prods_count_1, prods_count_2)
        self.assertEqual(vars_count_1, vars_count_2)

    @override_settings(DEBUG=True)
    def test_seed_command_creates_valid_skus(self):
        """Test that SKUs are unique and follow pattern."""
        call_command('seed_demo_catalog')
        skus = list(ProductVariant.objects.values_list('sku', flat=True))
        self.assertEqual(len(skus), len(set(skus)))
        for sku in skus:
            self.assertTrue(sku.startswith('DEMO-'))

    @override_settings(DEBUG=True)
    def test_seed_command_publishes_products(self):
        """Test that products are published with active variants."""
        call_command('seed_demo_catalog')
        published_products = Product.objects.filter(is_published=True)
        self.assertGreater(published_products.count(), 0)
        for product in published_products:
            active_variants = product.variants.filter(is_active=True)
            self.assertGreater(active_variants.count(), 0)

    @override_settings(DEBUG=True)
    def test_seed_command_creates_hierarchical_categories(self):
        """Test that hierarchical categories are created correctly."""
        call_command('seed_demo_catalog')
        tops = Category.objects.filter(slug='tops').first()
        self.assertIsNotNone(tops)
        self.assertIsNotNone(tops.parent)
        self.assertEqual(tops.parent.slug, 'women')

    @override_settings(DEBUG=False)
    def test_seed_command_refuses_production(self):
        """Test that command refuses to run in production (DEBUG=False)."""
        with self.assertRaises(Exception) as cm:
            call_command('seed_demo_catalog')
        self.assertIn('Refusing to run', str(cm.exception))

    @override_settings(DEBUG=True, ENVIRONMENT='production')
    def test_seed_command_refuses_production_env(self):
        """Test that command refuses to run in production environment."""
        with self.assertRaises(Exception) as cm:
            call_command('seed_demo_catalog')
        self.assertIn('Refusing to run', str(cm.exception))
