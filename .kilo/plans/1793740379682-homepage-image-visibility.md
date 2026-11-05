# Homepage Image Visibility Investigation Plan (Refined)

## Confirmed Findings (code-level)
- Frontend: Vite proxy `/api` and `/media` -> http://127.0.0.1:8000
- Backend: MEDIA_URL=/media/, MEDIA_ROOT=backend/media; media served only if DEBUG via static()
- Media files exist on disk (categories and products)
- CategorySerializer exposes `image`; ProductListSerializer uses primary_image -> ProductImageReadSerializer.image
- Frontend CategoryGallery uses cat.image; LatestProducts uses product.primary_image.image
- CSS: images absolutely positioned, object-fit cover; overlay opacity 0 by default

## Unconfirmed / Limitations
- No runtime process inspection or browser access performed (bash restricted, no curl)
- Cannot verify actual HTTP responses, Content-Type, dimensions, or browser rendering
- Actual user browser verification unavailable

## Category-Specific
- Category image path: category_image_upload_path -> catalog/categories/<pk or uuid>/<uuid>.ext
- Serializer field `image` returns URL via DRF (absolute if request context present)

## Product-Specific
- Product images: ProductImage.image, upload_to product_image_upload_path
- primary_image selection: first is_primary or first image

## Shared Infrastructure
- Vite proxy, Django media serving, DEBUG flag, CORS

## Recommended Fix Plan
1. Confirm backend running with DEBUG=True; test media URL via browser.
2. Verify Vite proxy active and frontend origin.
3. Inspect browser network/console for actual failures.
4. Only then adjust URL/proxy if proven.

## Verification Plan
- Real browser: check img src/currentSrc/naturalWidth, network status/content-type.
- Compare direct backend media URL vs proxied.

## Status
Investigation code-level complete; runtime/browser verification pending user.
" filePath">
/home/md-arifuzzaman-akash/Desktop/myDir/fineFit/project/e_com/.kilo/plans/1793740379682-homepage-image-visibility.md