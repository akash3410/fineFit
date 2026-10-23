# Implementation Plan

## 1. Execution Philosophy

To build a robust production foundation rather than a disposable prototype, development is structured into strictly ordered, test-verified phases.
- **Rule 1**: No phase begins until the preceding phase's tests pass and data models are validated.
- **Rule 2**: Database migrations are strictly managed: `CustomUser` must be created and registered in `settings.py` before executing the first database migration.
- **Rule 3**: Environment prerequisites (Python virtual environment, PostgreSQL database, Node.js) are established before code scaffolding.

---

## 2. Phased Roadmap

### Phase 0: Environment & Infrastructure Readiness
- [x] Create Python virtual environment (`.venv`) using Python 3.12.3.
- [x] Pin and install backend dependencies in `backend/requirements.txt` (Django 5.2.18, DRF 3.18.3, `psycopg[binary]==3.3.6`, `django-cors-headers==4.9.0`, `django-environ==0.14.0`, `pytest==8.4.2`, `pytest-django==4.14.0`).
- [x] Verify test runner and environment sanity with pytest.
- [ ] Configure PostgreSQL instance (database: `finefit_db`, user: `finefit_user`) - *Pending host service/container start*.
- [ ] Install Node.js (v20 or v22 LTS) on the development environment for frontend build tooling.

### Phase 1: Backend Foundation & Authentication (`apps.accounts`)
- [x] Initialize Django project structure: `backend/config/` and `backend/apps/`.
- [x] Configure environment-based settings split (`base.py`, `local.py`, `production.py`) with explicit CORS and CSRF settings for Vite origin.
- [x] Implement `apps.accounts.models.CustomUser` based on `AbstractUser` with UUID primary key, `username = None`, and unique `email`.
- [x] Implement `apps.accounts.managers.CustomUserManager` with validated `create_user` and `create_superuser`.
- [x] Define `AUTH_USER_MODEL = 'accounts.CustomUser'` in settings.
- [x] Generate initial migration (`backend/apps/accounts/migrations/0001_initial.py`).
- [ ] Run database migration `migrate` (*Pending PostgreSQL availability*).
- [x] Implement session authentication and CSRF endpoints (`/api/v1/auth/csrf/`, `/api/v1/auth/login/`, `/api/v1/auth/logout/`, `/api/v1/auth/me/`).
- [x] Write automated tests for user creation, superuser creation, email uniqueness, UUID primary key, and model auth configuration (14 passed).

### Phase 2: Catalog & Variant Data Architecture (`apps.catalog`)
- [ ] Implement `Category` model with hierarchical parent-child relationships and slug generators.
- [ ] Implement `Product` and `ProductVariant` models (supporting size, color, SKU, and price overrides).
- [ ] Implement `ProductImage` with primary flags, ordering, and variant association.
- [ ] Configure Django admin with inline variant and image editors.
- [ ] Create DRF serializers: `CategorySerializer`, `ProductListSerializer`, `ProductDetailSerializer` (optimized querysets using `prefetch_related`).
- [ ] Implement public catalog endpoints:
  - `GET /api/v1/catalog/categories/`
  - `GET /api/v1/catalog/products/` (filtering by category, size, color, price)
  - `GET /api/v1/catalog/products/{slug}/`
- [ ] Write automated unit/integration tests for catalog query performance and filtering.

### Phase 3: Inventory Management & Atomic Concurrency (`apps.inventory`)
- [ ] Implement `StockRecord` model with foreign key to `ProductVariant`.
- [ ] Create `StockService` providing atomic check, reserve, and decrement operations using `select_for_update()`.
- [ ] Implement inventory alert signals for low-stock thresholds.
- [ ] Write concurrency tests verifying that simultaneous checkout attempts do not oversell remaining stock.

### Phase 4: Shopping Cart & Guest Checkout (`apps.cart` & `apps.orders`)
- [ ] Implement `Cart` and `CartItem` models supporting both authenticated users and guest sessions.
- [ ] Create cart management endpoints: add item, update quantity, remove item, retrieve active cart.
- [ ] Implement guest cart to user cart merge service on customer login.
- [ ] Implement `Order` and `OrderItem` models with immutable price and product snapshot fields.
- [ ] Build checkout service supporting **Cash on Delivery (COD)** and guest checkout (capturing name, phone, shipping address).
- [ ] Implement order status transition engine (Pending -> Confirmed -> Processing -> Shipped -> Delivered -> Cancelled).
- [ ] Write integration tests for guest cart creation, checkout submission, and order history security.

### Phase 5: Staff Operations Dashboard API (`apps.dashboard`)
- [ ] Define role-based permission classes (`IsStaffUser`, `CanManageOrders`, `CanManageInventory`).
- [ ] Create staff endpoints:
  - `GET /api/v1/dashboard/orders/` (filtering by status, date, payment method, customer search)
  - `PATCH /api/v1/dashboard/orders/{id}/status/` (validated status transitions)
  - `PATCH /api/v1/dashboard/inventory/{variant_id}/` (stock balance updates)
- [ ] Write automated tests verifying that standard customers cannot access dashboard endpoints (HTTP 403).

### Phase 6: Frontend Storefront Application (`frontend/`)
- [ ] Initialize Vite + React + TypeScript application with Tailwind CSS.
- [ ] Establish design tokens (modern editorial typography, neutral luxury palette, responsive layout).
- [ ] Build core UI components (Navbar, Mobile Drawer, Product Card, Badge, Modal, Form Inputs).
- [ ] Implement Catalog Views:
  - Home / Featured collections.
  - Category product grid with live filtering (Size, Color, Price).
  - Product Detail Page with image gallery, color swatches, size selector, and real-time stock indicator.
- [ ] Implement Cart Drawer / Cart Page with real-time total updates.
- [ ] Implement streamlined Checkout Page supporting Guest Checkout and Cash on Delivery.
- [ ] Implement Order Confirmation & Status Tracking view.

### Phase 7: Staff Dashboard Frontend
- [ ] Build staff login and role verification flow.
- [ ] Create operational order queue with quick status progression actions (Confirm COD, Mark Shipped).
- [ ] Create inventory adjustment table with instant stock count updates.

### Phase 8: Testing, Hardening & Production Preparation
- [ ] Perform full regression test suite (backend pytest + frontend Vitest).
- [ ] Configure CORS, CSP, CSRF, and secure cookie headers.
- [ ] Prepare Dockerfile and `docker-compose.yml` for reproducible production deployment.
- [ ] Document developer onboarding and production deployment manual in `docs/`.
