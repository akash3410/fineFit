# Architecture Decision Records (ADRs) & Decisions Log

This document records the rationale behind key technical choices, trade-offs evaluated, and pending business decisions requiring client confirmation.

---

## 1. Architectural Decisions Log (ADRs)

### ADR-001: API-First Modular Monolith
- **Status**: Accepted
- **Context**: The platform requires a top-tier modern fashion storefront (React/Vite) and operational backoffice dashboards, starting as an initial release that evolves into a full-scale production system.
- **Decision**: Adopt an API-first modular monolith built with Django REST Framework and a decoupled React SPA. Structure the Django backend into cleanly bounded domain apps (`accounts`, `catalog`, `inventory`, `cart`, `orders`, `dashboard`).
- **Consequences**:
  - *Positive*: Single repository deployment simplicity, shared database transactional guarantees, clean separation of concerns, flexibility to evolve frontend or add mobile apps via `/api/v1/` without rewriting backend logic.
  - *Trade-off*: Requires disciplined interface boundaries between internal Django apps to avoid circular dependencies.

---

### ADR-002: CustomUser Defined Before Initial Migration
- **Status**: Accepted
- **Context**: Django's default `auth.User` model cannot be cleanly substituted after the first `migrate` command is executed without complex and hazardous schema surgery.
- **Decision**: Define `apps.accounts.models.CustomUser` extending `AbstractUser` with UUID primary key, `username = None`, and `email` as the unique authentication identifier. Set `AUTH_USER_MODEL = 'accounts.CustomUser'` before running any database migrations. Staff authorization is founded on Django's built-in Groups and Permissions rather than a rigid single-role enum.
- **Consequences**:
  - *Positive*: Ensures future-proof authentication, supports role-based access control (RBAC), preserves standard permission tooling, and makes primary keys unguessable against sequential enumeration.
  - *Security Clarification*: UUIDs make identifiers less predictable but do NOT replace authentication, authorization, object-level permission checks, or customer data isolation. Tenant filtering (`filter(user=request.user)`) and backend permission classes remain mandatory.
  - *Trade-off*: Requires creating the custom user and authentication setup prior to any other model creation.

---

### ADR-003: Modern PostgreSQL Driver (`psycopg` v3)
- **Status**: Accepted
- **Context**: The system runs Python 3.12 on Ubuntu 24.04 with Django 5.2.18. Legacy `psycopg2` can encounter compilation issues on modern Python versions and lacks native support for newer asynchronous and connection pooling capabilities.
- **Decision**: Use `psycopg[binary]==3.3.6` (psycopg 3) as the PostgreSQL adapter for Django 5.2.18.
- **Consequences**:
  - *Positive*: Full Python 3.12 compatibility, improved performance, native type adaptation for PostgreSQL data types without external C compiler build dependencies.
  - *Trade-off*: Configuration syntax in `DATABASES['default']['ENGINE']` uses `django.db.backends.postgresql` which auto-detects `psycopg` v3.

---

### ADR-004: Variant-Level Inventory & Pessimistic Row Locking (`select_for_update`)
- **Status**: Accepted
- **Context**: High-demand fashion drops can trigger flash purchases where multiple shoppers attempt to buy the last unit of a specific color/size simultaneously.
- **Decision**: Stock is tracked strictly at the `ProductVariant` level via `StockRecord`. During checkout processing, inventory rows are queried within `transaction.atomic()` using `select_for_update()` to enforce row-level database locks during quantity verification and deduction.
- **Consequences**:
  - *Positive*: Guarantees zero overselling race conditions under concurrent checkouts without needing complex external distributed locks.
  - *Trade-off*: Locks are held for milliseconds during the transaction; requires transactions to remain brief and strictly scoped.

---

### ADR-005: Dual-Mode Cart with Merge Strategy
- **Status**: Accepted
- **Context**: Shoppers often add items as guests and subsequently authenticate or register before final checkout.
- **Decision**: The `Cart` entity supports both an optional `user` foreign key and an indexed `session_key`. When a guest customer logs in, a dedicated merge service transfers unauthenticated cart items into their primary user cart.
- **Consequences**:
  - *Positive*: Maximizes conversion by reducing friction for guest browsing while retaining cart persistence upon login.
  - *Trade-off*: Requires deduplication logic when merging if the same SKU exists in both the guest and user carts.

---

### ADR-006: Order Immutability & Price Snapshotting
- **Status**: Accepted
- **Context**: Catalog prices, product descriptions, or variant options may be modified or deleted post-purchase. An order represents a legal financial agreement.
- **Decision**: `OrderItem` records store deep snapshots of unit prices, product titles, variant SKUs, size, and color names directly on the row at the time of checkout. Foreign keys to `ProductVariant` are nullable with `on_delete=models.SET_NULL`.
- **Consequences**:
  - *Positive*: Historical orders remain 100% accurate and auditable even if products are edited or archived.
  - *Trade-off*: Slight storage redundancy across order rows, fully justified for financial integrity.

---

### ADR-007: Cash on Delivery (COD) as First-Class Payment Method
- **Status**: Accepted
- **Context**: The platform targets markets where Cash on Delivery is a dominant, high-trust payment channel.
- **Decision**: Implement a full order lifecycle supporting Cash on Delivery (`Pending -> Confirmed -> Shipped -> Delivered [Paid]`) with staff verification workflows.
- **Consequences**:
  - *Positive*: Immediate market-fit without early hard dependencies on third-party payment gateway approvals.
  - *Trade-off*: Operational overhead requiring staff order confirmation calls or automated SMS verification to reduce Return-to-Origin (RTO) rates.

---

### ADR-008: React + TypeScript + Vite + Tailwind CSS Frontend
- **Status**: Accepted
- **Context**: Contemporary fashion e-commerce demands instant page transitions, fluid filtering, responsive image carousels, and design refinement.
- **Decision**: Build the client application using React 18/19 with TypeScript, Vite for lightning-fast build tooling, and Tailwind CSS for bespoke editorial design control.
- **Consequences**:
  - *Positive*: Fast development iteration, type safety matching backend serializers, zero CSS bloat, and highly customizable UI tokens.
  - *Trade-off*: Decoupled deployment requires managing CORS and secure API communication.

---

### ADR-009: Session Authentication with CSRF Protection for Web Clients
- **Status**: Accepted
- **Context**: The primary user client is a single-page web storefront and staff operations dashboard running in desktop and mobile web browsers. Stateless bearer tokens (such as JWT stored in localStorage or sessionStorage) are vulnerable to XSS token exfiltration and require complex refresh mechanics.
- **Decision**: Employ Django's battle-tested `SessionAuthentication` with HttpOnly session cookies, `SameSite=Lax`, and standard CSRF protection (`csrftoken` cookie read by client and submitted in `X-CSRFToken` headers) as the primary authentication mechanism for the web application. Token-based authentication (such as SimpleJWT) is deliberately omitted by default and will only be evaluated if dedicated native mobile applications (iOS/Android) or external third-party integrations require stateless bearer tokens in future phases.
- **Consequences**:
  - *Positive*: Seamless protection against XSS token exfiltration, native integration with Django Groups and Permissions, out-of-the-box session lifecycle management, and built-in CSRF defenses.
  - *Trade-off*: Requires explicit CORS credentials configuration (`CORS_ALLOW_CREDENTIALS = True`) and exact origin trust lists (`CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`) without wildcards.

---

### ADR-010: Decoupled Inventory Reservation Architecture & Unresolved Policy
- **Status**: Accepted
- **Context**: Retail fashion platforms must manage high contention during sales drops. However, the client has not finalized whether stock should be reserved upon adding an item to the shopping cart (with expiration) or only upon final checkout submission.
- **Decision**: Architect `apps.inventory` and `StockService` with generic, reusable primitive operations:
  1. `reserve_stock(variant, quantity, ...)`: Increments `quantity_reserved` and decrements derived `available_quantity` while preserving on-hand stock.
  2. `release_reservation(variant, quantity, ...)`: Decrements `quantity_reserved` and restores `available_quantity`.
  3. `decrease_stock(..., from_reserved=True/False)`: Supports fulfillment whether items were pre-reserved or directly decremented at checkout.
  4. Multi-variant lock sorting: Enforces deterministic UUID order when calling `select_for_update()` to prevent PostgreSQL deadlocks.
  Do not couple reservation mechanics to Cart or Checkout until the client decides between Option A and Option B.
- **Consequences**:
  - *Positive*: Full flexibility to adopt either cart-reservation or checkout-only reservation without altering the inventory core or database schema. Zero business assumptions hardcoded.
  - *Trade-off*: Both workflows must be maintained and verified in unit tests.

---

### ADR-011: Cash-on-Delivery Checkout in `apps.orders`
- **Status**: Accepted
- **Context**: The storefront bag had no way to become an order. The platform needs a first, straightforward purchase path before payment gateways are evaluated, and the COD decision (see unresolved decision 4 for returns) is a prerequisite for any gateway integration.
- **Decision**: Implement `apps.orders` with `Order` + `OrderItem` exactly as specified in ARCHITECTURE.md §2.5, supporting **cash on delivery only** (`payment_method='COD'`). Checkout is a single atomic transaction that locks the cart's `StockRecord`s in deterministic UUID order, re-validates catalog visibility, prices and stock server-side, snapshots line items (title/SKU/size/colour/unit price), deducts stock via `StockService` with `ORDER_CHECKOUT` ledger movements, and clears the cart. Guest orders are bound to the Django session key; authenticated orders to the customer. Order lookups always filter by owner. `shipping_fee` is stored as `0.00` until the shipping-fee policy is decided.
- **Consequences**:
  - *Positive*: Real orders can be placed today with no third-party dependency, no card data in scope, an immutable audit trail of every sale, and no overselling race (row locks + availability re-check).
  - *Trade-off*: Staff must confirm/fulfil orders manually; adding a payment gateway later requires a payment-state model rather than a schema change to `Order`. Until shipping-fee policy is set, the storefront shows no delivery charge and the total equals the subtotal.

---

### ADR-012: Staff Order Management in the Custom Admin Panel
- **Status**: Accepted
- **Context**: Orders placed by guests are attached to a browser session, so staff had no way to find them in the custom dashboard; only Django admin exposed the raw rows. Fulfilment also needs a safe way to cancel an order without losing the sold units.
- **Decision**: Add an **Orders** section to the custom admin panel (`/admin/orders/`) with status/search filters, a detail page showing customer, delivery address, line snapshots and totals, and a status form. All status changes go through `OrderService.update_status()`, which locks the order and its stock records, and **returns the outstanding units to stock** through `StockService` (`ORDER_CANCELLED` / `RETURN` movements) when an order is cancelled or returned. `CANCELLED` and `RETURNED` are terminal: they cannot be reopened, which guarantees stock is restored exactly once.
- **Audit trail**: Every status transition writes an append-only `OrderStatusChange` row (`previous_status`, `new_status`, `changed_by`, `note`, `created_at`), shown as *Status & Return History* on the order page. Staff actions record the logged-in account; guest/system activity has a null actor.
- **Line-level returns**: `OrderItem.returned_quantity` (DB-constrained to `<= quantity`) plus `OrderService.return_items()` let staff return individual units per line with an optional reason. Returns are allowed only after confirmation (`CONFIRMED`…`DELIVERED`), restock exactly the returned units, and mark the order `RETURNED` once every line is fully returned. Cancellation restocks only outstanding units, so a partially returned order is never restocked twice.
- **Consequences**:
  - *Positive*: Staff can see and action every order regardless of guest/registered ownership, inventory stays consistent with sales, cancellations and partial returns, and every status/return event is attributable to a dated actor.
  - *Trade-off*: Returns are restocked straight into available stock (no per-unit condition grading, refund accounting or damaged-vs-resellable split); those belong with the unresolved refund policy (decision 4).

---

### ADR-013: Customer Return Requests & Order Tracking
- **Status**: Accepted
- **Context**: Returns existed only as a staff action in the dashboard. Customers had no order history page and no way to see what happened to an order, so every return had to be arranged by phone or message and staff had to re-key the request.
- **Decision**: Add a customer-facing return-request flow plus order tracking:
  - `ReturnRequest` (+`ReturnRequestItem`) records per-line quantities a customer wants to return, with an optional reason. `POST /api/v1/orders/{order_number}/returns/` is ownership-scoped exactly like order lookup (guest session or `user=request.user`, 404 otherwise) and only accepts **delivered** orders, at most one open request per order, and quantities within `OrderItem.remaining_quantity`.
  - A request is **intent, not stock movement**: units only return to inventory when staff approve, because the goods must physically arrive first.
  - Staff review requests on the dashboard order page (`approve_return` / `decline_return`). `OrderService.review_return_request()` delegates approval to `OrderService.return_items()`, so restocking, `RETURN` ledger movements, the `returned_quantity` update and the audit entry are identical to a staff-recorded return. A request can be reviewed exactly once; declines store a staff note.
  - Order detail now returns `status_history` (audit entries with staff identities stripped), `return_requests` and `can_request_return`. The storefront renders a tracking timeline, the request statuses and the per-line return form on `/order/{order_number}`, and lists every owned order at `/orders`.
- **Consequences**:
  - *Positive*: Customers can self-serve returns and track progress without contacting staff; staff get a reviewed, attributable record instead of verbal requests; stock still only changes on approval, so inventory cannot be inflated by an unapproved claim.
  - *Trade-off*: There is no customer-facing cancel of a pending request and no automatic expiry window; refunds remain out of scope until the COD refund policy (decision 4) is settled.

---

## 2. Unresolved Business Decisions (Client Clarification Needed)

The following items are documented as open decisions and must not be assumed without client/stakeholder agreement:

| Topic | Options Under Consideration | Business Impact |
| :--- | :--- | :--- |
| **1. Cart Reservation Window** | (A) Reserve stock on Add to Cart with 15-minute countdown.<br>(B) Reserve stock only upon Order submission. | Option A prevents cart sniping but risks cart abandonment tying up inventory. Option B is simpler and standard for retail fashion. |
| **2. Shipping & Delivery Fees** | (A) Flat delivery fee across all orders.<br>(B) Free shipping above a specified order total (e.g., $100).<br>(C) Region-specific courier rates. | Influences checkout calculation logic and order total serializer fields. |
| **3. Guest Checkout Account Linking** | (A) Silently create inactive customer account using the provided email/phone.<br>(B) Leave guest orders detached; invite user to set password post-purchase. | Affects customer onboarding friction and order tracking experience. |
| **4. COD Return & Refund Policy** | (A) Store credit voucher only.<br>(B) Bank account/mobile wallet payout upon return inspection.<br>(C) No returns on final sale items. | Governs refund operations and staff dashboard return workflows. |
| **5. Order Notification Providers** | (A) Email only (SendGrid / AWS SES).<br>(B) SMS / WhatsApp OTP & updates (Twilio / local SMS gateway).<br>(C) Multi-channel. | Directs integration setup for third-party communication services. |
