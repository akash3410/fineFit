# FineFit Image System Repair Plan (Implementation-Ready)

## Pre-Change Audit (Completed via Read-Only Inspection)

### Media Files Verified on Disk

**Category images** (`backend/media/catalog/categories/`): 6 directories, 6 files:
| Path | Format | Dimensions | Valid | Ext Match |
|------|--------|------------|-------|-----------|
| `1/eb8c1d7b69de4f4d8c9cbb388995b1d0.png` | PNG | 279x181 | Yes | Yes |
| `17e89bcbeb094ee5a8952815726cfe2a/2420f46f2b9b4df086d898930026eb4b.png` | PNG | 10x10 | Yes | Yes |
| `2b1b6b0604ce4c8da61030aee96d8035/9e8f25afb58d4c89a3fb1f5daa3a34c7.png` | PNG | 400x500 | Yes | Yes |
| `4/6758427e801c4f69b7c868c2272075d2.jpeg` | **WebP** | unknown | Yes | **NO** |
| `7/cdb097a2a6674913b9e3082d152ea445.webp` | WebP | unknown | Yes | Yes |
| `707013bf82cf427eb1d3fc7502a167fb/4cebeddb9c004858a84d86af5b9a462e.png` | PNG | 200x200 | Yes | Yes |

**Product images** (`backend/media/catalog/products/`): 45 directories, ~50+ files:
- Most: 100x100 PNG (valid, ext matches)
- Some: JPEG (valid, ext matches)
- Some: WebP with `.webp` ext (valid, ext matches)
- 2 mismatches: WebP content with `.jpeg` ext (listed below)

### Three MIME/Extension Mismatches (Confirmed via `file` command)

1. `backend/media/catalog/categories/4/6758427e801c4f69b7c868c2272075d2.jpeg` — RIFF WebP, extension `.jpeg`
2. `backend/media/catalog/products/09e18800-6d07-46ce-a6b3-3c5b65ccdbaa/a017743ac26b46f9aec1b81c7087be0c.jpeg` — RIFF WebP, extension `.jpeg`
3. `backend/media/catalog/products/1ab8ce93-e383-461b-af37-b28e9ef074db/fdc6eb1e2caf46758ee4fced739ae439.jpeg` — RIFF WebP, extension `.jpeg`

### Root Causes

1. **MIME/extension mismatches**: Django serves Content-Type based on file extension. Browser receives `image/jpeg` with WebP bytes → fails to decode → `naturalWidth=0`.

2. **Media serving only under `DEBUG=True`**: `backend/config/urls.py:20-21` wraps `static(settings.MEDIA_URL, ...)` inside `if settings.DEBUG:`. When DEBUG=False, `/media/` is never served by Django.

3. **Django Admin has no image previews**: `CategoryAdmin`, `ProductImageInline`, `ProductImageAdmin` do not render image thumbnails. Unfold does not auto-render `ImageField` previews.

4. **Database references**: After renaming files, DB `image` fields still point to old `.jpeg` paths. Must be updated.

### Configuration Facts (No Change Needed Unless Noted)

- `MEDIA_URL = "/media/"`, `MEDIA_ROOT = BASE_DIR / "media"` → `backend/media` — correct
- Vite proxies `/media` → `http://127.0.0.1:8000` — correct for dev
- API base is `/api/v1` (relative), proxied to Django — correct
- DRF `ImageField` serializer returns relative URLs (e.g., `/media/...`) with request context — correct
- No Cloudinary/S3/storage backend — local filesystem only — correct

## Implementation Steps

### Step 1: Database Audit (Read-Only, First)

Query the database to find all records referencing the 3 mismatched files:

```python
# Via Django shell or manage.py dbshell
from apps.catalog.models import Category, ProductImage

# Find categories referencing the mismatched file
Category.objects.filter(image__contains="6758427e801c4f69b7c868c2272075d2")

# Find product images referencing mismatched files
ProductImage.objects.filter(image__contains="a017743ac26b46f9aec1b81c7087be0c")
ProductImage.objects.filter(image__contains="fdc6eb1e2caf46758ee4fced739ae439")
```

Also capture:
- Total categories: `Category.objects.count()`
- Categories with images: `Category.objects.exclude(image__isnull=True).exclude(image="").count()`
- Total products: `Product.objects.count()`
- Products with images: count distinct products with ProductImage records
- Products with primary images: `ProductImage.objects.filter(is_primary=True).values('product').distinct().count()`

### Step 2: Rename Mismatched Files (No Overwrite)

Rename only — do not copy, do not delete originals:

| Old Path | New Path |
|----------|----------|
| `media/catalog/categories/4/6758427e801c4f69b7c868c2272075d2.jpeg` | `media/catalog/categories/4/6758427e801c4f69b7c868c2272075d2.webp` |
| `media/catalog/products/09e18800-6d07-46ce-a6b3-3c5b65ccdbaa/a017743ac26b46f9aec1b81c7087be0c.jpeg` | `media/catalog/products/09e18800-6d07-46ce-a6b3-3c5b65ccdbaa/a017743ac26b46f9aec1b81c7087be0c.webp` |
| `media/catalog/products/1ab8ce93-e383-461b-af37-b28e9ef074db/fdc6eb1e2caf46758ee4fced739ae439.jpeg` | `media/catalog/products/1ab8ce93-e383-461b-af37-b28e9ef074db/fdc6eb1e2caf46758ee4fced739ae439.webp` |

Verify after rename: `file` command should report correct MIME for each new path.

### Step 3: Update Database References

Within `transaction.atomic()`, update each affected record's `image` field from `.jpeg` to `.webp`:

```python
from django.db import transaction

with transaction.atomic():
    # Category
    Category.objects.filter(image__endswith="6758427e801c4f69b7c868c2272075d2.jpeg").update(
        image=models.F("image").__class__  # Use RawSQL or direct string replace
    )
    # Better: fetch instances, modify field, save
    for cat in Category.objects.filter(image__contains="6758427e801c4f69b7c868c2272075d2"):
        cat.image = cat.image.replace(".jpeg", ".webp")
        cat.save()

    # ProductImage records
    for img in ProductImage.objects.filter(image__contains="a017743ac26b46f9aec1b81c7087be0c"):
        img.image = img.image.replace(".jpeg", ".webp")
        img.save()
    for img in ProductImage.objects.filter(image__contains="fdc6eb1e2caf46758ee4fced739ae439"):
        img.image = img.image.replace(".jpeg", ".webp")
        img.save()
```

### Step 4: Fix `backend/config/urls.py`

Move media URL serving outside the DEBUG guard:

```python
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### Step 5: Add Django Admin Image Previews

Edit `backend/apps/catalog/admin.py`:

**CategoryAdmin**: Add `image_tag` method, add `image` to fieldsets, add `image_tag` to readonly_fields, add `image_tag` to list_display.

**ProductImageInline**: Add `image_tag` to fields and readonly_fields.

**ProductImageAdmin**: Add `image_tag` method, add to list_display.

Pattern:
```python
def image_tag(self, obj):
    if obj.image:
        return format_html('<img src="{}" width="60" height="60" style="object-fit:cover;" />', obj.image.url)
    return "-"
image_tag.short_description = "Image"
```

### Step 6: Frontend Review (No URL Normalization Needed)

Relative image URLs (`/media/...`) work correctly because:
- Vite proxies `/media` → Django at 127.0.0.1:8000
- DRF `ImageField` returns relative URLs that the browser resolves against the current origin

No frontend code changes required for image URL correctness. Components already render `cat.image`, `product.primary_image?.image`, `hero.image` directly as `src`.

### Step 7: Verification

Backend:
- `manage.py check` — Django system checks
- `pytest apps/catalog/tests/` — catalog tests (includes test_images.py)
- Verify renamed files: `file` command reports WebP, not mislabeled JPEG
- Database integrity: all image references resolve to existing files

Frontend:
- `tsc -b` — TypeScript check
- `oxlint` — ESLint
- `vite build` — production build

Media delivery:
- Each media URL returns HTTP 200
- Content-Type matches actual format (image/webp for renamed files)
- `naturalWidth > 0` and `naturalHeight > 0` for representative images

## Data Safety

- No database records deleted
- No media files deleted or overwritten (rename only)
- No fake or placeholder images
- No destructive migrations
- Database updates wrapped in `transaction.atomic()`

## Remaining Issues (Post-Implementation)

- Some images are 10x10 or 100x100 px — technically valid but visually small; these exist by design in the current data, not a bug
- Database records referencing missing files (not the 3 mismatched ones) require manual image upload — report exact records after database audit
- Production deployment: media serving behind DEBUG=False requires a production web server (nginx/Apache) or WhiteNoise configured to serve `MEDIA_ROOT` at `MEDIA_URL` — outside scope of code changes