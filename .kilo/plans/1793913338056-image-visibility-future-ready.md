# Image Visibility and Future-Ready Media Plan

## Goal
Make catalog images reliably visible in both backend admin and frontend UI, repair existing mismatched media files, and prevent recurrence with validation, consistent media serving, and frontend fallback handling.

## Root Causes
1. Three WebP files have `.jpeg` extensions, causing browsers to receive `image/jpeg` for WebP bytes and fail decoding.
2. Media is served by Django only behind `DEBUG=True`; with `DEBUG=False`, `/media/` returns 404.
3. Django admin lacks image previews for category/product images.
4. Database rows still reference old mismatched paths if files are renamed.
5. Frontend renders image URLs directly with no fallback for missing/broken media.
6. Upload validation does not reject extension/content mismatches, allowing recurrence.

## Scope
- Backend: `config/urls.py`, `config/settings/base.py`, `apps/catalog/admin.py`, catalog upload validators/services, tests.
- Frontend: image rendering components/hooks, Vite proxy already correct.
- Data repair: rename 3 mismatched files and update DB references transactionally.

## Implementation Steps
1. Audit DB records referencing the 3 mismatched filenames and capture image coverage metrics.
2. Rename mismatched files to `.webp` without overwriting originals; verify with `file`.
3. Update DB references in `transaction.atomic()` from `.jpeg` to `.webp`.
4. Serve media consistently:
   - Keep Django `static()` for development.
   - Add production media strategy: configure reverse proxy/WhiteNoise or dedicated media route behind `DEBUG=False`.
   - Ensure `MEDIA_URL` and `MEDIA_ROOT` remain `/media/` and `backend/media`.
5. Add admin previews:
   - `image_tag` methods on `CategoryAdmin`, `ProductImageAdmin`, and inline.
   - Add `image` to fieldsets/list displays.
6. Add upload-time validation:
   - Verify file content type via Pillow.
   - Reject extension/content mismatches.
   - Enforce allowed formats and dimensions.
7. Add backend tests:
   - MIME/extension mismatch rejection.
   - Media serving returns correct Content-Type.
   - Renamed DB references resolve to existing files.
8. Frontend hardening:
   - Add a typed image URL normalizer for relative `/media/...` URLs.
   - Add fallback placeholder for broken/missing images.
   - Ensure components use primary image with deterministic fallback.
9. Verification:
   - `manage.py check`, catalog tests, frontend typecheck/lint/build.
   - HTTP 200 and correct Content-Type for representative media.
   - Browser `naturalWidth > 0` for representative images.

## Data Safety
- No deletions or overwrites; rename only.
- DB updates wrapped in `transaction.atomic()`.
- No placeholder images committed as real data.

## Open Questions
- Should production media be served by Django, WhiteNoise, or external nginx? Recommend external nginx/reverse proxy for production and Django dev serving only for local.
- Should missing images receive a default placeholder from frontend or backend? Recommend frontend fallback plus backend 404 handling.

## Additional Root Cause: Absolute Media URLs
DRF currently serializes `ImageField` as absolute URLs using the request host (`http://127.0.0.1:8000/media/...`). This works only if that exact backend host/port is reachable from the browser. If the frontend is accessed through another host, HTTPS, a different port, or only Vite is running, every image request fails before Django can serve it.

## Additional Implementation Steps
10. Add a frontend image URL normalizer:
   - Convert absolute backend media URLs to `/media/...`.
   - Leave non-media URLs untouched.
   - Use it in all image `src` bindings.
11. Add a backend setting/env for canonical media base URL:
   - `MEDIA_BASE_URL` optional.
   - If set, serializers return that host; otherwise relative `/media/...`.
12. Make Vite proxy `/media` in all dev modes and document startup order.
13. Add frontend fallback for any failed image request.
14. Add a diagnostic endpoint/check script that verifies media URL resolution.
15. Run a browser-level smoke test against representative category/product images.