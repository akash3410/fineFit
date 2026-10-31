# FineFit Storefront Verification Plan

## Objective
Verify the current React + TypeScript + Tailwind storefront implementation, test integration with the Django backend, check data readiness, and produce a complete report as specified.

## Current State (Confirmed)
- **Frontend**: React 19 + TypeScript + Vite 8 + Tailwind v4, routes `/`, `/shop`, `/product/:slug` implemented
- **API client**: Uses relative `/api/v1/` paths with Vite proxy to `http://127.0.0.1:8000` for `/api` and `/media`
- **Pages**: Home, Shop, ProductDetail in `frontend/src/pages/` with loading/error/empty states
- **Currency**: BDT formatting utility added
- **Backend**: Django 5.2.18 with DRF 3.18.3, PostgreSQL configured, catalog app implemented with public endpoints

## Verification Tasks

### Task 1: Inspect Current Implementation ✓ (In Progress)
- [x] Read AGENTS.md, ARCHITECTURE.md, IMPLEMENTATION_PLAN.md
- [x] Inspect frontend package.json, vite.config.ts, tsconfig.json
- [x] Inspect API client, types, pages, components
- [x] Inspect backend catalog views/serializers/urls

### Task 2: Run Frontend Checks
**Commands to run from `frontend/` directory:**

1. **Production build**: `npm run build` (runs `tsc -b && vite build`)
2. **TypeScript check**: `npx tsc --noEmit` or use project config with `tsc -p tsconfig.app.json --noEmit`
3. **Lint**: `npm run lint` (oxlint configured)
4. **Tests**: Check if test script exists in package.json - currently no test script defined

**Expected issues to check:**
- Type errors (Vite build does transpile but may miss some type issues)
- Unused imports/variables
- Missing types
- Import/export issues

### Task 3: Verify Frontend-to-Backend Integration
**API Endpoints (from backend):**
- `GET /api/v1/catalog/categories/` → Returns `CategorySerializer` tree (top-level roots with nested children, active only)
- `GET /api/v1/catalog/products/` → Paginated list via `CatalogPagination` (page_size=12, max 100). Filters: `category` (slug, includes descendants), `size`, `color` (iexact), `price_min`, `price_max`. Search: `search` (title, description). Ordering: `ordering` (base_price, created_at, title), default `-created_at`
- `GET /api/v1/catalog/products/{slug}/` → Product detail with images and active variants (by default). Management context includes all variants.

**Response shapes:**
- Categories: Array of root categories with `children` array (recursive). Each has `id`, `name`, `slug`, `is_active`, `children`
- Products list: Paginated response with `results` array containing ProductListItem (id, slug, title, base_price, category slug, primary_image, created_at)
- Product detail: ProductDetail with nested category, images array, variants array (with effective_price)

**Image handling:**
- Images served from Django media (configured in vite proxy for `/media`)
- ProductImage has `image` (URL), `alt_text`, etc.
- Primary image determined by `is_primary` flag, else first image

**Verification steps:**
1. Check if Django server can start and if DB has data
2. Test API endpoints directly or through proxy
3. Verify frontend handles actual response shapes (note: frontend currently handles both array and `{results:...}` for categories, and `{results:...}` for products - need to confirm actual format)
4. Check if images load

### Task 4: Check Demo Readiness
- Inspect PostgreSQL database for published products and categories
- Check if any management commands or fixtures exist for seeding data
- Report findings without auto-seeding

### Task 5: Final Report
Must include all items specified by user.

## Implementation Notes
- Frontend already has pages and routing set up
- Need to verify types match actual API responses
- May need to fix minor issues found during checks
- Currency display updated to BDT
- Do NOT implement cart/checkout/payments/dashboard
