# Plan: FineFit Homepage Shopping Experience Redesign

## Goal
Redesign the homepage (`/`) into six ordered sections:
1. Existing Hero Section (unchanged)
2. Brand Promise Strip (replaces the "Journey of Trust" 3D coverflow)
3. Events / Announcements
4. Shop by Category
5. Shop by Subcategory
6. Latest Products

Preserve the hero exactly. Use real backend data; no mocks. Remove dead components.

## Inspection Report

### Current homepage — `frontend/src/pages/Home.tsx`
- Renders `FashionHeroSlider` → `BrandPromiseGateway` (3D "Journey of Trust" coverflow, to be removed) → category pills → featured products grid.
- Data via `frontend/src/api/catalog.ts`: `getCategories()`, `getProducts({page_size:'8'})`, `getProduct(slug)`. Base `/api/v1`. Vite dev proxy: `/api` and `/media` → `http://127.0.0.1:8000`.
- Types in `frontend/src/types/catalog.ts`: `Category {id, name, slug, is_active, children}`, `ProductListItem {id, slug, title, base_price, category, primary_image, created_at}`.
- Links: category → `/shop?category=<slug>`; product → `/product/<slug>`.
- Stack: Vite + React 19 + TypeScript 5 + Tailwind CSS v4 + framer-motion + react-router-dom. Scripts: `build` = `tsc -b && vite build`, `lint` = `oxlint`. `node_modules` present; Node v26 available.

### Backend catalog API — `apps.catalog`
- `GET /api/v1/catalog/categories/` — `CategoryListView`, `AllowAny`, **no pagination**. Returns active top-level categories with nested `children`. `CategorySerializer` fields: `[id, name, slug, is_active, children]` — **`image` NOT exposed** though `Category.image` exists on the model.
- `GET /api/v1/catalog/products/` — `ProductListView`, `AllowAny`, `CatalogPagination` (PageNumberPagination: `page_size=12`, `page_size_query_param`, `max_page_size=100`), default ordering `-created_at` (newest first). Filters: `category`, `size`, `color`, `price_min`, `price_max`, `ordering`, `search`. Response shape: `{count, next, previous, results: [...]}`.
- `GET /api/v1/catalog/products/<slug>/` — `ProductDetailView`, `AllowAny`.
- `ProductListSerializer` fields: `[id, slug, title, base_price, category, primary_image, created_at]` — **no `discount_price`, no `stock`**.
- Management viewsets under `/api/v1/catalog/manage/` (model-permission gated, staff only).

### Models — `apps/catalog/models.py`
- `Category`: BigAuto PK, `name`, `slug`(unique), `image`(ImageField), `parent`(self FK), `children`, `is_active`, `is_deleted`, `created_at`. `objects.active()`.
- `Subcategory`: BigAuto PK, `category` FK, `name`, `slug`, `image`, `is_active`, `is_deleted`, `created_at`. `objects.active()`. **No API endpoint exists.**
- `Product`: UUID PK, `category` FK, `subcategory` FK (optional), `title`, `slug`, `base_price`, `discount_price`, `stock`, `is_published`, `is_featured`, `status`, `is_deleted`, `created_at` (Meta ordering `-created_at`). `objects.published()`.
- `ProductImage`: `image`, `alt_text`, `display_order`, `is_primary`, `variant`.

### Missing backend functionality (must be addressed before full frontend implementation)
1. **Category image not in API** — `CategorySerializer` omits `image`. Required for Section 4 gallery cards ("Use actual category images").
2. **No Subcategory API endpoint** — `Subcategory` model exists but no view/URL. Required for Section 5.
3. **No Event/Announcement model or endpoint** — none found in codebase (grep confirmed). Required for Section 3 real data.
4. **Product list lacks `discount_price`/`stock`** — needed for sale badges and availability in Section 6 (section works without; nice-to-have).

## Decisions (to be implemented by the execution agent)
- Icons: inline SVGs only (no new dependency).
- Animation: CSS-driven marquee/scroll for strips; JS only for pause-on-hover/focus and `prefers-reduced-motion` gating. No framer-motion for new sections.
- Data fetching: extend `api/catalog.ts` with native `fetch` wrappers (`getSubcategories`, `getEvents`); no TanStack Query (avoid new dependency). Loading/error/empty states per section.
- Links: category → `/shop?category=<slug>`; subcategory → `/shop?category=<parent-slug>&subcategory=<slug>`; product → `/product/<slug>`. Shop page must add `?subcategory=` filter support.
- Pagination: preserve `next`/`previous`; "Load More" increments `page`.
- Hero: untouched (`FashionHeroSlider` and related files unchanged).
- Remove `BrandPromiseGateway.tsx` and obsolete `.brand-promise-slider` CSS rules from `index.css`.

## Backend changes required (minimal, proposed)
A. `apps/catalog/serializers.py` `CategorySerializer`: add read-only `image` field (media URL).
B. `apps/catalog/serializers.py` `ProductListSerializer`: add `discount_price`, `stock`.
C. `apps/catalog/views.py` + `urls.py`: add `SubcategoryListView` (`AllowAny`, active subcategories, optional `?category=<slug>` or `?category=<id>`, paginated) at `GET /api/v1/catalog/subcategories/`.
D. `apps/catalog/`: add `Event` model (`title`, `slug`, `announcement`, `image`, `start_at`, `end_at`, `is_active`, `cta_label`, `cta_link`, `created_at`) + migration + `EventListView` (`AllowAny`, active & within date range) at `GET /api/v1/catalog/events/`. Implement now (not deferred). Frontend hides Section 3 when no active events returned.
E. Create/apply migrations; add tests for new endpoints.
F. `apps/catalog/views.py` `ProductListView.get_queryset`: add `?subcategory=<slug>` or `?subcategory=<id>` filter so Shop can filter products by subcategory (needed for subcategory cards linking to `/shop?category=&subcategory=`).

## Proposed frontend component structure
- `frontend/src/components/homepage/BrandPromiseStrip.tsx` — looping promise-card marquee (icon + name), glassmorphism, pause on hover/focus, reduced-motion, touch-friendly.
- `frontend/src/components/homepage/EventsAnnouncement.tsx` — single active event carousel (fade/slide), indicators, hide when empty.
- `frontend/src/components/homepage/CategoryGallery.tsx` — editorial asymmetric grid (large/medium/small cards), category image + name + arrow, image zoom on hover, View All/Load More.
- `frontend/src/components/homepage/SubcategoryStrip.tsx` — horizontal scroll of rounded pill cards (name + thumbnail), clickable → filtered listing.
- `frontend/src/components/homepage/LatestProducts.tsx` — responsive product grid, newest-first via server ordering, Load More preserving `next`/`prev`, loading/empty/error states, retry.
- Update `frontend/src/pages/Home.tsx`: assemble sections in order; remove `BrandPromiseGateway`.
- Update `frontend/src/api/catalog.ts`: add `getSubcategories`, `getEvents`.
- Update `frontend/src/types/catalog.ts`: `Category.image?: string`; `ProductListItem.discount_price?: string | null`, `stock?: number`; add `Subcategory`, `Event` types.
- Styles in `frontend/src/index.css`; remove obsolete brand-promise rules.

## Implementation stages (ordered)
1. Backend prep (backend agent): items A–E; verify endpoint response shapes.
2. Frontend: types + API service additions.
3. Frontend: BrandPromiseStrip replaces BrandPromiseGateway in Home (hero unchanged, no vertical gap).
4. Frontend: EventsAnnouncement (hide-if-empty).
5. Frontend: CategoryGallery (pagination/View All).
6. Frontend: SubcategoryStrip.
7. Frontend: LatestProducts (Load More, loading/empty/error).
8. Polish: responsive checks, reduced-motion, a11y (focus states, labels), lint + typecheck + build.

## Verification
- `tsc -b` (typecheck), `vite build` (production build), `oxlint` (lint).
- Pagination preserved (`next`/`previous`); Load More appends without duplicates for subcategories/products.
- Newest products first via server `-created_at` (no browser sort).
- Every card/CTA clickable; keyboard accessible; visible focus states.
- Empty/loading/error states for each data-driven section.
- Desktop/tablet/mobile; no horizontal overflow; hero unchanged.
- Reduced-motion: marquee pauses; event transitions respect `prefers-reduced-motion`.
- Report every modified file and any backend migration/API changes.

## Resolved decisions (closed)
- Subcategory link target: Shop page adds `?subcategory=` filter support; subcategory cards link to `/shop?category=<parent-slug>&subcategory=<slug>`.
- Event backend: implement now (item D). Section 3 hides gracefully when no active events returned.

## Files to modify / create
**Modify:**
- `frontend/src/pages/Home.tsx`
- `frontend/src/pages/Shop.tsx` (add `?subcategory=` filter support)
- `frontend/src/api/catalog.ts`
- `frontend/src/types/catalog.ts`
- `frontend/src/index.css`
**Delete:**
- `frontend/src/components/BrandPromiseGateway.tsx`
**Create:**
- `frontend/src/components/homepage/BrandPromiseStrip.tsx`
- `frontend/src/components/homepage/EventsAnnouncement.tsx`
- `frontend/src/components/homepage/CategoryGallery.tsx`
- `frontend/src/components/homepage/SubcategoryStrip.tsx`
- `frontend/src/components/homepage/LatestProducts.tsx`
**Backend (proposed):**
- `backend/apps/catalog/serializers.py` (Category image; ProductList discount_price/stock)
- `backend/apps/catalog/views.py` + `urls.py` (SubcategoryListView, EventListView)
- `backend/apps/catalog/models.py` + new migration (Event model)
- `backend/apps/catalog/tests/` (new endpoint tests)
