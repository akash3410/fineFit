from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.db.models import Count, Sum, F
from apps.catalog.models import Category, Product, ProductVariant, Subcategory, ProductImage
from apps.inventory.models import StockRecord


def dashboard_view(request):
    # Category stats
    total_categories = Category.objects.filter(is_deleted=False).count()
    total_subcategories = Subcategory.objects.filter(is_deleted=False).count()
    
    # Product stats
    total_products = Product.objects.filter(is_deleted=False).count()
    active_products = Product.objects.filter(is_deleted=False, status=True).count()
    
    # Stock stats
    out_of_stock_products = Product.objects.filter(
        is_deleted=False,
        variants__stock=0
    ).distinct().count()
    
    low_stock_products = Product.objects.filter(
        is_deleted=False,
        variants__stock__gt=0,
        variants__stock__lte=10
    ).distinct().count()
    
    # Calculate total inventory value
    total_inventory_value = 0
    for product in Product.objects.filter(is_deleted=False):
        for variant in product.variants.all():
            if variant.price_override:
                total_inventory_value += variant.price_override * variant.stock
            else:
                total_inventory_value += product.price * variant.stock
    
    # Recently added products
    recent_products = Product.objects.filter(is_deleted=False).order_by('-created_at')[:10]
    
    context = {
        'total_categories': total_categories,
        'total_subcategories': total_subcategories,
        'total_products': total_products,
        'active_products': active_products,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'total_inventory_value': total_inventory_value,
        'recent_products': recent_products,
    }
    
    return render(request, 'admin/dashboard.html', context)


def get_dashboard_context():
    # Category stats
    total_categories = Category.objects.filter(is_deleted=False).count()
    total_subcategories = Subcategory.objects.filter(is_deleted=False).count()
    
    # Product stats
    total_products = Product.objects.filter(is_deleted=False).count()
    active_products = Product.objects.filter(is_deleted=False, status=True).count()
    
    # Stock stats
    out_of_stock_products = Product.objects.filter(
        is_deleted=False,
        variants__stock=0
    ).distinct().count()
    
    low_stock_products = Product.objects.filter(
        is_deleted=False,
        variants__stock__gt=0,
        variants__stock__lte=10
    ).distinct().count()
    
    # Calculate total inventory value
    total_inventory_value = 0
    for product in Product.objects.filter(is_deleted=False):
        for variant in product.variants.all():
            if variant.price_override:
                total_inventory_value += variant.price_override * variant.stock
            else:
                total_inventory_value += product.price * variant.stock
    
    # Recently added products
    recent_products = Product.objects.filter(is_deleted=False).order_by('-created_at')[:10]
    
    return {
        'total_categories': total_categories,
        'total_subcategories': total_subcategories,
        'total_products': total_products,
        'active_products': active_products,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'total_inventory_value': total_inventory_value,
        'recent_products': recent_products,
    }


# Dashboard admin integration placeholder

