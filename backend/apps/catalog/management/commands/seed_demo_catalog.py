"""
Seed demo catalog data for local development.

This command creates a small, realistic fictional fashion catalog using the
existing schema. It is idempotent and will not create duplicates. It will
refuse to run in production settings. It does not create ProductImage records
or download images - images must be added separately if needed.
"""

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Category, Product, ProductVariant


class Command(BaseCommand):
    help = "Seed demo catalog data for local development (idempotent)"

    def handle(self, *args, **options):
        # Restrict to development environment by default
        if getattr(settings, 'ENVIRONMENT', '').lower() == 'production':
            raise CommandError(
                "Refusing to run seed_demo_catalog in production environment."
            )
        # Check if explicitly set to False
        if getattr(settings, 'DEBUG') is False:
            raise CommandError(
                "Refusing to run seed_demo_catalog in production settings (DEBUG=False)."
            )

        self.stdout.write(self.style.SUCCESS("Seeding demo catalog data..."))

        with transaction.atomic():
            # Create categories
            categories_data = [
                {"name": "Men", "slug": "men"},
                {"name": "Women", "slug": "women"},
                {"name": "Tops", "slug": "tops", "parent_slug": "women"},
                {"name": "Bottoms", "slug": "bottoms", "parent_slug": "women"},
                {"name": "Outerwear", "slug": "outerwear", "parent_slug": "men"},
            ]

            category_map = {}
            for cat_data in categories_data:
                parent = None
                if cat_data.get("parent_slug"):
                    parent = category_map.get(cat_data["parent_slug"])
                    if not parent:
                        parent = Category.objects.filter(slug=cat_data["parent_slug"]).first()
                
                category, created = Category.objects.get_or_create(
                    slug=cat_data["slug"],
                    defaults={
                        "name": cat_data["name"],
                        "parent": parent,
                        "is_active": True,
                    },
                )
                category_map[cat_data["slug"]] = category
                if created:
                    self.stdout.write(f"  Created category: {category.name}")
                else:
                    self.stdout.write(f"  Found existing category: {category.name}")

            # Create products
            products_data = [
                {"title": "Aurora Wool Overcoat", "slug": "aurora-wool-overcoat", "description": "Classic wool overcoat.", "base_price": Decimal("8999.99"), "category_slug": "outerwear", "is_published": True},
                {"title": "Luna Cotton T-Shirt", "slug": "luna-cotton-t-shirt", "description": "Soft organic cotton t-shirt.", "base_price": Decimal("1299.99"), "category_slug": "tops", "is_published": True},
                {"title": "Nova Denim Jeans", "slug": "nova-denim-jeans", "description": "High-waisted straight-leg denim jeans.", "base_price": Decimal("3499.99"), "category_slug": "bottoms", "is_published": True},
                {"title": "Stella Silk Blouse", "slug": "stella-silk-blouse", "description": "Luxurious silk blouse.", "base_price": Decimal("4999.99"), "category_slug": "tops", "is_published": True},
                {"title": "Atlas Chino Pants", "slug": "atlas-chino-pants", "description": "Versatile chino pants.", "base_price": Decimal("2799.99"), "category_slug": "men", "is_published": True},
                {"title": "Mila Knit Sweater", "slug": "mila-knit-sweater", "description": "Cozy oversized knit sweater.", "base_price": Decimal("3799.99"), "category_slug": "tops", "is_published": True},
                {"title": "Orion Leather Jacket", "slug": "orion-leather-jacket", "description": "Genuine leather jacket.", "base_price": Decimal("12999.99"), "category_slug": "outerwear", "is_published": True},
                {"title": "Cora Midi Skirt", "slug": "cora-midi-skirt", "description": "Elegant midi skirt.", "base_price": Decimal("2999.99"), "category_slug": "bottoms", "is_published": True},
                {"title": "Phoenix Polo Shirt", "slug": "phoenix-polo-shirt", "description": "Classic pique polo shirt.", "base_price": Decimal("1999.99"), "category_slug": "men", "is_published": True},
                {"title": "Vera Linen Dress", "slug": "vera-linen-dress", "description": "Breathable linen dress.", "base_price": Decimal("4499.99"), "category_slug": "women", "is_published": True},
            ]

            product_map = {}
            for prod_data in products_data:
                category = category_map.get(prod_data["category_slug"])
                if not category:
                    category = Category.objects.filter(slug=prod_data["category_slug"]).first()
                
                product, created = Product.objects.get_or_create(
                    slug=prod_data["slug"],
                    defaults={
                        "title": prod_data["title"],
                        "description": prod_data["description"],
                        "category": category,
                        "base_price": prod_data["base_price"],
                        "is_published": prod_data["is_published"],
                    },
                )
                product_map[prod_data["slug"]] = product
                if created:
                    self.stdout.write(f"  Created product: {product.title}")
                else:
                    self.stdout.write(f"  Found existing product: {product.title}")

            # Create variants
            variants_data = [
                {"product_slug": "aurora-wool-overcoat", "sku": "DEMO-AWO-M-BLK", "size": "M", "color_name": "Black", "color_code": "#000000"},
                {"product_slug": "aurora-wool-overcoat", "sku": "DEMO-AWO-L-BLK", "size": "L", "color_name": "Black", "color_code": "#000000"},
                {"product_slug": "aurora-wool-overcoat", "sku": "DEMO-AWO-M-NAV", "size": "M", "color_name": "Navy", "color_code": "#001f3f"},
                {"product_slug": "aurora-wool-overcoat", "sku": "DEMO-AWO-L-NAV", "size": "L", "color_name": "Navy", "color_code": "#001f3f"},
                {"product_slug": "luna-cotton-t-shirt", "sku": "DEMO-LCT-S-WHT", "size": "S", "color_name": "White", "color_code": "#ffffff"},
                {"product_slug": "luna-cotton-t-shirt", "sku": "DEMO-LCT-M-WHT", "size": "M", "color_name": "White", "color_code": "#ffffff"},
                {"product_slug": "luna-cotton-t-shirt", "sku": "DEMO-LCT-M-BLK", "size": "M", "color_name": "Black", "color_code": "#000000"},
                {"product_slug": "luna-cotton-t-shirt", "sku": "DEMO-LCT-L-BLK", "size": "L", "color_name": "Black", "color_code": "#000000"},
                {"product_slug": "nova-denim-jeans", "sku": "DEMO-NDJ-28-BLU", "size": "28", "color_name": "Blue", "color_code": "#4169e1"},
                {"product_slug": "nova-denim-jeans", "sku": "DEMO-NDJ-30-BLU", "size": "30", "color_name": "Blue", "color_code": "#4169e1"},
                {"product_slug": "nova-denim-jeans", "sku": "DEMO-NDJ-32-BLU", "size": "32", "color_name": "Blue", "color_code": "#4169e1"},
                {"product_slug": "stella-silk-blouse", "sku": "DEMO-SSB-S-IVY", "size": "S", "color_name": "Ivory", "color_code": "#fffff0"},
                {"product_slug": "stella-silk-blouse", "sku": "DEMO-SSB-M-IVY", "size": "M", "color_name": "Ivory", "color_code": "#fffff0"},
                {"product_slug": "stella-silk-blouse", "sku": "DEMO-SSB-M-BLK", "size": "M", "color_name": "Black", "color_code": "#000000"},
                {"product_slug": "atlas-chino-pants", "sku": "DEMO-ACP-30-KHK", "size": "30", "color_name": "Khaki", "color_code": "#f0e68c"},
                {"product_slug": "atlas-chino-pants", "sku": "DEMO-ACP-32-KHK", "size": "32", "color_name": "Khaki", "color_code": "#f0e68c"},
                {"product_slug": "atlas-chino-pants", "sku": "DEMO-ACP-32-NAV", "size": "32", "color_name": "Navy", "color_code": "#001f3f"},
                {"product_slug": "mila-knit-sweater", "sku": "DEMO-MKS-M-GRY", "size": "M", "color_name": "Gray", "color_code": "#808080"},
                {"product_slug": "mila-knit-sweater", "sku": "DEMO-MKS-L-GRY", "size": "L", "color_name": "Gray", "color_code": "#808080"},
                {"product_slug": "mila-knit-sweater", "sku": "DEMO-MKS-M-CRM", "size": "M", "color_name": "Cream", "color_code": "#fffdd0"},
                {"product_slug": "orion-leather-jacket", "sku": "DEMO-OLJ-M-BLK", "size": "M", "color_name": "Black", "color_code": "#000000"},
                {"product_slug": "orion-leather-jacket", "sku": "DEMO-OLJ-L-BLK", "size": "L", "color_name": "Black", "color_code": "#000000"},
                {"product_slug": "orion-leather-jacket", "sku": "DEMO-OLJ-L-BRN", "size": "L", "color_name": "Brown", "color_code": "#8b4513"},
                {"product_slug": "cora-midi-skirt", "sku": "DEMO-CMS-S-BLK", "size": "S", "color_name": "Black", "color_code": "#000000"},
                {"product_slug": "cora-midi-skirt", "sku": "DEMO-CMS-M-BLK", "size": "M", "color_name": "Black", "color_code": "#000000"},
                {"product_slug": "cora-midi-skirt", "sku": "DEMO-CMS-M-NAV", "size": "M", "color_name": "Navy", "color_code": "#001f3f"},
                {"product_slug": "phoenix-polo-shirt", "sku": "DEMO-PPS-M-WHT", "size": "M", "color_name": "White", "color_code": "#ffffff"},
                {"product_slug": "phoenix-polo-shirt", "sku": "DEMO-PPS-L-WHT", "size": "L", "color_name": "White", "color_code": "#ffffff"},
                {"product_slug": "phoenix-polo-shirt", "sku": "DEMO-PPS-M-NAV", "size": "M", "color_name": "Navy", "color_code": "#001f3f"},
                {"product_slug": "vera-linen-dress", "sku": "DEMO-VLD-S-BEG", "size": "S", "color_name": "Beige", "color_code": "#f5f5dc"},
                {"product_slug": "vera-linen-dress", "sku": "DEMO-VLD-M-BEG", "size": "M", "color_name": "Beige", "color_code": "#f5f5dc"},
                {"product_slug": "vera-linen-dress", "sku": "DEMO-VLD-M-WHT", "size": "M", "color_name": "White", "color_code": "#ffffff"},
            ]

            for var_data in variants_data:
                product = product_map.get(var_data["product_slug"])
                if not product:
                    product = Product.objects.filter(slug=var_data["product_slug"]).first()
                
                variant, created = ProductVariant.objects.get_or_create(
                    sku=var_data["sku"],
                    defaults={
                        "product": product,
                        "size": var_data["size"],
                        "color_name": var_data["color_name"],
                        "color_code": var_data["color_code"],
                        "is_active": True,
                        "price_override": None,
                    },
                )
                if created:
                    self.stdout.write(f"  Created variant: {variant.sku}")
                else:
                    self.stdout.write(f"  Found existing variant: {variant.sku}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDemo catalog seeded successfully!\n"
                f"Categories: {Category.objects.count()}, "
                f"Products: {Product.objects.count()}, "
                f"Variants: {ProductVariant.objects.count()}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "\nNote: No ProductImage records created. Original/properly licensed "
                "local demo product images are needed to display product images."
            )
        )
