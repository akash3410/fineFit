from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.forms import inlineformset_factory
from django.views.decorators.http import require_http_methods

from .decorators import admin_access_required, superuser_required

from apps.catalog.models import Category, Subcategory, Product, ProductVariant, ProductImage, Event
from apps.dashboard.views import get_dashboard_context
from apps.inventory.exceptions import InvalidStockAdjustmentError
from apps.inventory.services import StockService


def staff_required(user):
    return user.is_active and user.is_staff


def sync_variant_inventory(request, variant, declared_stock):
    """
    Mirror the catalog form's stock value into the inventory ledger.

    The storefront cart trusts ``StockRecord`` only, so a variant saved with a
    stock quantity but no inventory balance would look available on the product
    page and then be refused when adding to the cart.
    """
    actor = request.user if request.user.is_authenticated else None
    try:
        StockService.sync_declared_stock(variant, declared_stock, actor=actor)
    except InvalidStockAdjustmentError as exc:
        messages.warning(
            request,
            f"Stock for variant {variant.sku} was saved but not synced to inventory: {exc}",
        )


@user_passes_test(admin_access_required)
def dashboard(request):
    context = get_dashboard_context()
    return render(request, 'admin_panel/dashboard/index.html', context)


@user_passes_test(admin_access_required)
def category_list(request):
    queryset = Category.objects.filter(is_deleted=False).order_by('-created_at')
    search = request.GET.get('q', '')
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(slug__icontains=search))
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/categories/index.html', {
        'page_obj': page_obj,
        'search': search,
    })


@user_passes_test(admin_access_required)
def category_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('status') == 'active'
        slug = request.POST.get('slug', '').strip()
        if not slug:
            from django.utils.text import slugify
            slug = slugify(name)
        if not name:
            messages.error(request, 'Name is required.')
        elif Category.objects.filter(slug=slug).exists():
            messages.error(request, 'Slug already exists.')
        else:
            category = Category.objects.create(
                name=name,
                slug=slug,
                description=description,
                is_active=is_active,
            )
            if request.FILES.get('image'):
                category.image = request.FILES['image']
                category.save(update_fields=['image'])
            messages.success(request, 'Category created successfully.')
            return redirect('admin_panel:category_list')
    return render(request, 'admin_panel/categories/form.html', {'action': 'Add'})


@user_passes_test(admin_access_required)
def category_view(request, pk):
    category = get_object_or_404(Category, pk=pk, is_deleted=False)
    subcategories = category.subcategories.filter(is_deleted=False)
    products = category.products.filter(is_deleted=False)[:10]
    return render(request, 'admin_panel/categories/view.html', {
        'category': category,
        'subcategories': subcategories,
        'products': products,
    })


@user_passes_test(admin_access_required)
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk, is_deleted=False)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('status') == 'active'
        slug = request.POST.get('slug', '').strip()
        if not slug:
            from django.utils.text import slugify
            slug = slugify(name)
        if not name:
            messages.error(request, 'Name is required.')
        elif Category.objects.filter(slug=slug).exclude(pk=pk).exists():
            messages.error(request, 'Slug already exists.')
        else:
            category.name = name
            category.slug = slug
            category.description = description
            category.is_active = is_active
            if request.FILES.get('image'):
                category.image = request.FILES['image']
            elif request.POST.get('clear_image') == 'on':
                category.image = None
            category.save()
            messages.success(request, 'Category updated successfully.')
            return redirect('admin_panel:category_list')
    return render(request, 'admin_panel/categories/form.html', {'category': category, 'action': 'Edit'})


@user_passes_test(admin_access_required)
@require_http_methods(["POST"])
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, is_deleted=False)
    # Check for dependencies
    if category.subcategories.filter(is_deleted=False).exists():
        messages.error(request, 'Cannot delete category with existing subcategories.')
        return redirect('admin_panel:category_list')
    if category.products.filter(is_deleted=False).exists():
        messages.error(request, 'Cannot delete category with existing products.')
        return redirect('admin_panel:category_list')
    category.is_deleted = True
    category.deleted_at = timezone.now()
    category.save()
    messages.success(request, 'Category deleted successfully.')
    return redirect('admin_panel:category_list')


@user_passes_test(admin_access_required)
def subcategory_list(request):
    queryset = Subcategory.objects.filter(is_deleted=False).select_related('category').order_by('-created_at')
    search = request.GET.get('q', '')
    category_id = request.GET.get('category')
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(slug__icontains=search))
    if category_id:
        queryset = queryset.filter(category_id=category_id)
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    categories = Category.objects.filter(is_deleted=False)
    return render(request, 'admin_panel/subcategories/index.html', {
        'page_obj': page_obj,
        'search': search,
        'categories': categories,
        'selected_category': category_id,
    })


@user_passes_test(admin_access_required)
def subcategory_add(request):
    categories = Category.objects.filter(is_deleted=False)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('status') == 'active'
        slug = request.POST.get('slug', '').strip()
        if not slug:
            from django.utils.text import slugify
            slug = slugify(name)
        if not name or not category_id:
            messages.error(request, 'Name and Category are required.')
        else:
            category = get_object_or_404(Category, pk=category_id, is_deleted=False)
            if Subcategory.objects.filter(category=category, slug=slug).exists():
                messages.error(request, 'Slug already exists for this category.')
            elif Subcategory.objects.filter(category=category, name=name).exists():
                messages.error(request, 'Subcategory name already exists for this category.')
            else:
                subcategory = Subcategory.objects.create(
                    category=category,
                    name=name,
                    slug=slug,
                    description=description,
                    is_active=is_active,
                )
                if request.FILES.get('image'):
                    subcategory.image = request.FILES['image']
                    subcategory.save(update_fields=['image'])
                messages.success(request, 'Subcategory created successfully.')
                return redirect('admin_panel:subcategory_list')
    return render(request, 'admin_panel/subcategories/form.html', {'categories': categories, 'action': 'Add'})


@user_passes_test(admin_access_required)
def subcategory_view(request, pk):
    subcategory = get_object_or_404(Subcategory, pk=pk, is_deleted=False)
    products = subcategory.products.filter(is_deleted=False)[:10]
    return render(request, 'admin_panel/subcategories/view.html', {
        'subcategory': subcategory,
        'products': products,
    })


@user_passes_test(admin_access_required)
def subcategory_edit(request, pk):
    subcategory = get_object_or_404(Subcategory, pk=pk, is_deleted=False)
    categories = Category.objects.filter(is_deleted=False)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        description = request.POST.get('description', '').strip()
        is_active = request.POST.get('status') == 'active'
        slug = request.POST.get('slug', '').strip()
        if not slug:
            from django.utils.text import slugify
            slug = slugify(name)
        if not name or not category_id:
            messages.error(request, 'Name and Category are required.')
        else:
            category = get_object_or_404(Category, pk=category_id, is_deleted=False)
            if Subcategory.objects.filter(category=category, slug=slug).exclude(pk=pk).exists():
                messages.error(request, 'Slug already exists for this category.')
            elif Subcategory.objects.filter(category=category, name=name).exclude(pk=pk).exists():
                messages.error(request, 'Subcategory name already exists for this category.')
            else:
                subcategory.name = name
                subcategory.category = category
                subcategory.slug = slug
                subcategory.description = description
                subcategory.is_active = is_active
                if request.FILES.get('image'):
                    subcategory.image = request.FILES['image']
                elif request.POST.get('clear_image') == 'on':
                    subcategory.image = None
                subcategory.save()
                messages.success(request, 'Subcategory updated successfully.')
                return redirect('admin_panel:subcategory_list')
    return render(request, 'admin_panel/subcategories/form.html', {'subcategory': subcategory, 'categories': categories, 'action': 'Edit'})


@user_passes_test(admin_access_required)
@require_http_methods(["POST"])
def subcategory_delete(request, pk):
    subcategory = get_object_or_404(Subcategory, pk=pk, is_deleted=False)
    if subcategory.products.filter(is_deleted=False).exists():
        messages.error(request, 'Cannot delete subcategory with existing products.')
        return redirect('admin_panel:subcategory_list')
    subcategory.is_deleted = True
    subcategory.deleted_at = timezone.now()
    subcategory.save()
    messages.success(request, 'Subcategory deleted successfully.')
    return redirect('admin_panel:subcategory_list')


@user_passes_test(admin_access_required)
def product_list(request):
    queryset = (
        Product.objects.filter(is_deleted=False)
        .select_related('category', 'subcategory')
        .prefetch_related('images')
        .order_by('-created_at')
    )
    search = request.GET.get('q', '')
    category_id = request.GET.get('category')
    subcategory_id = request.GET.get('subcategory')
    if search:
        queryset = queryset.filter(Q(title__icontains=search) | Q(sku__icontains=search))
    if category_id:
        queryset = queryset.filter(category_id=category_id)
    if subcategory_id:
        queryset = queryset.filter(subcategory_id=subcategory_id)
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    for product in page_obj:
        imgs = list(product.images.all())
        product.primary_image_obj = next((i for i in imgs if i.is_primary), imgs[0] if imgs else None)
    categories = Category.objects.filter(is_deleted=False)
    subcategories = Subcategory.objects.filter(is_deleted=False)
    return render(request, 'admin_panel/products/index.html', {
        'page_obj': page_obj,
        'search': search,
        'categories': categories,
        'subcategories': subcategories,
        'selected_category': category_id,
        'selected_subcategory': subcategory_id,
    })


@user_passes_test(admin_access_required)
def product_add(request):
    categories = Category.objects.filter(is_deleted=False)
    subcategories = Subcategory.objects.filter(is_deleted=False)
    if request.method == 'POST':
        from django.utils.text import slugify
        title = request.POST.get('title', '').strip()
        sku = request.POST.get('sku', '').strip() or None
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory') or None
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price') or 0
        discount_price = request.POST.get('discount_price') or None
        stock = request.POST.get('stock') or 0
        status = request.POST.get('status') == 'active'
        is_published = request.POST.get('is_published') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        slug = slugify(title)
        if not title or not category_id:
            messages.error(request, 'Title and Category are required.')
        else:
            category = get_object_or_404(Category, pk=category_id, is_deleted=False)
            subcategory = None
            if subcategory_id:
                subcategory = get_object_or_404(Subcategory, pk=subcategory_id, is_deleted=False)
                if subcategory.category_id != category.id:
                    messages.error(request, 'Subcategory must belong to selected category.')
                    return render(request, 'admin_panel/products/form.html', {'categories': categories, 'subcategories': subcategories, 'action': 'Add'})
            if Product.objects.filter(slug=slug).exists():
                slug = f"{slug}-{timezone.now().timestamp()}"
            try:
                from decimal import Decimal
                product = Product.objects.create(
                    title=title,
                    slug=slug,
                    sku=sku,
                    category=category,
                    subcategory=subcategory,
                    description=description,
                    price=Decimal(price),
                    discount_price=Decimal(discount_price) if discount_price else None,
                    stock=int(stock),
                    status=status,
                    is_published=is_published,
                    is_featured=is_featured,
                )
                # Handle variants
                variant_skus = request.POST.getlist('variant_sku')
                variant_sizes = request.POST.getlist('variant_size')
                variant_colors = request.POST.getlist('variant_color')
                variant_stocks = request.POST.getlist('variant_stock')
                variant_prices = request.POST.getlist('variant_price')
                for i in range(len(variant_skus)):
                    if variant_skus[i]:
                        v_stock = int(variant_stocks[i]) if i < len(variant_stocks) and variant_stocks[i] else 0
                        variant = ProductVariant.objects.create(
                            product=product,
                            sku=variant_skus[i],
                            size=variant_sizes[i] if i < len(variant_sizes) else '',
                            color_name=variant_colors[i] if i < len(variant_colors) else '',
                            stock=v_stock,
                            price_override=Decimal(variant_prices[i]) if i < len(variant_prices) and variant_prices[i] else None,
                        )
                        sync_variant_inventory(request, variant, v_stock)
                # Handle images
                main_image_idx = request.POST.get('main_image')
                for idx, img in enumerate(request.FILES.getlist('images')):
                    is_main = main_image_idx == str(idx) if main_image_idx is not None else idx == 0
                    ProductImage.objects.create(
                        product=product,
                        image=img,
                        alt_text=title,
                        display_order=idx,
                        is_primary=is_main,
                    )
                messages.success(request, 'Product created successfully.')
                return redirect('admin_panel:product_list')
            except Exception as e:
                messages.error(request, f'Error creating product: {e}')
    return render(request, 'admin_panel/products/form.html', {'categories': categories, 'subcategories': subcategories, 'action': 'Add'})


@user_passes_test(admin_access_required)
def product_view(request, pk):
    product = get_object_or_404(Product, pk=pk, is_deleted=False)
    variants = product.variants.all()
    images = product.images.all().order_by('display_order')
    return render(request, 'admin_panel/products/view.html', {
        'product': product,
        'variants': variants,
        'images': images,
    })


@user_passes_test(admin_access_required)
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk, is_deleted=False)
    categories = Category.objects.filter(is_deleted=False)
    subcategories = Subcategory.objects.filter(is_deleted=False)
    variants = product.variants.all()
    images = product.images.all().order_by('display_order')
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        sku = request.POST.get('sku', '').strip() or None
        category_id = request.POST.get('category')
        subcategory_id = request.POST.get('subcategory') or None
        description = request.POST.get('description', '').strip()
        price = request.POST.get('price') or 0
        discount_price = request.POST.get('discount_price') or None
        stock = request.POST.get('stock') or 0
        status = request.POST.get('status') == 'active'
        is_published = request.POST.get('is_published') == 'on'
        is_featured = request.POST.get('is_featured') == 'on'
        if not title or not category_id:
            messages.error(request, 'Title and Category are required.')
        else:
            category = get_object_or_404(Category, pk=category_id, is_deleted=False)
            subcategory = None
            if subcategory_id:
                subcategory = get_object_or_404(Subcategory, pk=subcategory_id, is_deleted=False)
                if subcategory.category_id != category.id:
                    messages.error(request, 'Subcategory must belong to selected category.')
                    return render(request, 'admin_panel/products/form.html', {'product': product, 'categories': categories, 'subcategories': subcategories, 'variants': variants, 'images': images, 'action': 'Edit'})
            try:
                from decimal import Decimal
                from django.db import transaction

                with transaction.atomic():
                    product.title = title
                    product.sku = sku
                    product.category = category
                    product.subcategory = subcategory
                    product.description = description
                    product.price = Decimal(price)
                    product.discount_price = Decimal(discount_price) if discount_price else None
                    product.stock = int(stock)
                    product.status = status
                    product.is_published = is_published
                    product.is_featured = is_featured
                    product.save()
                    # Handle variants
                    variant_ids = request.POST.getlist('variant_id')
                    variant_skus = request.POST.getlist('variant_sku')
                    variant_sizes = request.POST.getlist('variant_size')
                    variant_colors = request.POST.getlist('variant_color')
                    variant_stocks = request.POST.getlist('variant_stock')
                    variant_prices = request.POST.getlist('variant_price')
                    # Track which variant IDs are submitted to handle deletions if needed
                    submitted_ids = []
                    for i in range(len(variant_skus)):
                        if variant_skus[i]:
                            variant_id = variant_ids[i] if i < len(variant_ids) and variant_ids[i] else None
                            v_sku = variant_skus[i]
                            v_size = variant_sizes[i] if i < len(variant_sizes) else ''
                            v_color = variant_colors[i] if i < len(variant_colors) else ''
                            v_stock = int(variant_stocks[i]) if i < len(variant_stocks) and variant_stocks[i] else 0
                            v_price = Decimal(variant_prices[i]) if i < len(variant_prices) and variant_prices[i] else None
                            if variant_id:
                                try:
                                    var = ProductVariant.objects.get(id=variant_id, product=product)
                                    var.sku = v_sku
                                    var.size = v_size
                                    var.color_name = v_color
                                    var.stock = v_stock
                                    var.price_override = v_price
                                    var.save()
                                    submitted_ids.append(var.id)
                                    sync_variant_inventory(request, var, v_stock)
                                except ProductVariant.DoesNotExist:
                                    var = ProductVariant.objects.create(
                                        product=product,
                                        sku=v_sku,
                                        size=v_size,
                                        color_name=v_color,
                                        stock=v_stock,
                                        price_override=v_price,
                                    )
                                    submitted_ids.append(var.id)
                                    sync_variant_inventory(request, var, v_stock)
                            else:
                                var = ProductVariant.objects.create(
                                    product=product,
                                    sku=v_sku,
                                    size=v_size,
                                    color_name=v_color,
                                    stock=v_stock,
                                    price_override=v_price,
                                )
                                submitted_ids.append(var.id)
                                sync_variant_inventory(request, var, v_stock)
                    # Handle images: upload new files and update primary selection
                    from django.db.models import Max
                    main_image_existing = (request.POST.get('main_image_existing') or '').strip()
                    new_images = request.FILES.getlist('images')
                    max_order = product.images.aggregate(m=Max('display_order')).get('m')
                    next_order = (max_order + 1) if max_order is not None else 0
                    if main_image_existing:
                        product.images.update(is_primary=False)
                        product.images.filter(pk=main_image_existing).update(is_primary=True)
                    for idx, img in enumerate(new_images):
                        is_primary = False
                        if not main_image_existing and idx == 0 and not product.images.filter(is_primary=True).exists():
                            is_primary = True
                        ProductImage.objects.create(
                            product=product,
                            image=img,
                            alt_text=title,
                            display_order=next_order + idx,
                            is_primary=is_primary,
                        )
                    if not product.images.filter(is_primary=True).exists():
                        first = product.images.order_by('display_order', 'id').first()
                        if first:
                            first.is_primary = True
                            first.save(update_fields=['is_primary'])
                messages.success(request, 'Product updated successfully.')
                return redirect('admin_panel:product_list')
            except Exception as e:
                messages.error(request, f'Error updating product: {e}')
    return render(request, 'admin_panel/products/form.html', {'product': product, 'categories': categories, 'subcategories': subcategories, 'variants': variants, 'images': images, 'action': 'Edit'})


@user_passes_test(admin_access_required)
@require_http_methods(["POST"])
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, is_deleted=False)
    product.is_deleted = True
    product.deleted_at = timezone.now()
    product.save()
    messages.success(request, 'Product deleted successfully.')
    return redirect('admin_panel:product_list')


@user_passes_test(admin_access_required)
def event_list(request):
    queryset = Event.objects.filter(is_deleted=False).order_by('-created_at')
    search = request.GET.get('q', '')
    if search:
        queryset = queryset.filter(Q(title__icontains=search) | Q(slug__icontains=search))
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/events/index.html', {
        'page_obj': page_obj,
        'search': search,
    })


@user_passes_test(admin_access_required)
def event_add(request):
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        slug = request.POST.get('slug', '').strip()
        announcement = request.POST.get('announcement', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        start_at = request.POST.get('start_at', '').strip()
        end_at = request.POST.get('end_at', '').strip()
        cta_label = request.POST.get('cta_label', '').strip() or 'Explore Event'
        cta_link = request.POST.get('cta_link', '').strip()
        if not slug:
            from django.utils.text import slugify
            slug = slugify(title)
        if not title or not start_at or not end_at:
            messages.error(request, 'Title, start date and end date are required.')
        elif Event.objects.filter(slug=slug).exists():
            messages.error(request, 'Slug already exists.')
        else:
            event = Event.objects.create(
                title=title,
                slug=slug,
                announcement=announcement,
                is_active=is_active,
                start_at=start_at,
                end_at=end_at,
                cta_label=cta_label,
                cta_link=cta_link or None,
            )
            if request.FILES.get('image'):
                event.image = request.FILES['image']
                event.save(update_fields=['image'])
            messages.success(request, 'Event created successfully.')
            return redirect('admin_panel:event_list')
    return render(request, 'admin_panel/events/form.html', {'action': 'Add'})


@user_passes_test(admin_access_required)
def event_view(request, pk):
    event = get_object_or_404(Event, pk=pk, is_deleted=False)
    return render(request, 'admin_panel/events/view.html', {
        'event': event,
    })


@user_passes_test(admin_access_required)
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk, is_deleted=False)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        slug = request.POST.get('slug', '').strip()
        announcement = request.POST.get('announcement', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        start_at = request.POST.get('start_at', '').strip()
        end_at = request.POST.get('end_at', '').strip()
        cta_label = request.POST.get('cta_label', '').strip() or 'Explore Event'
        cta_link = request.POST.get('cta_link', '').strip()
        if not slug:
            from django.utils.text import slugify
            slug = slugify(title)
        if not title or not start_at or not end_at:
            messages.error(request, 'Title, start date and end date are required.')
        elif Event.objects.filter(slug=slug).exclude(pk=pk).exists():
            messages.error(request, 'Slug already exists.')
        else:
            event.title = title
            event.slug = slug
            event.announcement = announcement
            event.is_active = is_active
            event.start_at = start_at
            event.end_at = end_at
            event.cta_label = cta_label
            event.cta_link = cta_link or None
            if request.FILES.get('image'):
                event.image = request.FILES['image']
            elif request.POST.get('clear_image') == 'on':
                event.image = None
            event.save()
            messages.success(request, 'Event updated successfully.')
            return redirect('admin_panel:event_list')
    return render(request, 'admin_panel/events/form.html', {'event': event, 'action': 'Edit'})


@user_passes_test(admin_access_required)
@require_http_methods(["POST"])
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk, is_deleted=False)
    event.is_deleted = True
    event.deleted_at = timezone.now()
    event.save()
    messages.success(request, 'Event deleted successfully.')
    return redirect('admin_panel:event_list')


@user_passes_test(admin_access_required)
def get_subcategories_ajax(request, category_id):
    subcategories = Subcategory.objects.filter(category_id=category_id, is_deleted=False)
    data = [{'id': s.id, 'name': s.name} for s in subcategories]
    return JsonResponse({'subcategories': data})
