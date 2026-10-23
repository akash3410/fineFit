# Product Requirements Document (PRD)

## 1. Project Overview & Objectives

**Product Name**: FineFit E-Commerce Platform  
**Target Market**: Modern, high-fashion apparel and lifestyle retail  
**Architecture**: API-First Modular Monolith (Django REST Framework Backend + React/TypeScript/Tailwind CSS Frontend)  

The FineFit platform delivers an editorial-grade, lightning-fast, and secure shopping experience for fashion consumers across desktop and mobile devices, paired with an ergonomic operational dashboard for inventory managers and fulfillment staff.

---

## 2. User Personas

| Persona | Primary Goals | Key Capabilities |
| :--- | :--- | :--- |
| **Guest Shopper** | Discover fashion items, check availability, order quickly without forced registration | Browse catalog, filter variants (color/size), add to guest cart, complete Cash on Delivery (COD) checkout |
| **Registered Customer** | Track current and past orders, save delivery addresses, maintain persistent carts across devices | Register, login, manage profile/address book, view order status timeline |
| **Fulfillment / Store Staff** | Process incoming orders, verify COD confirmations, update fulfillment milestones | Order queue filtering, status transitions (Pending -> Confirmed -> Shipped -> Delivered), address verification |
| **Catalog & Inventory Admin** | Manage merchandise listings, image galleries, color/size variants, and stock balances | Create/edit products, manage variant matrices, update stock counts, view low-inventory alerts |

---

## 3. Agreed Functional Requirements

### 3.1 Authentication & User Management
- **Custom User Model**: Defined and configured (`AUTH_USER_MODEL = 'accounts.CustomUser'`) prior to running the first database migration.
- **Role-Based Access Control (RBAC)**: Group-based permissions separating standard customers, store staff, inventory managers, and superadmins using Django's built-in Groups and Permissions rather than a rigid role enum.
- **Session & CSRF Management**: Secure session authentication with HttpOnly cookies and CSRF protection (`/api/v1/auth/csrf/`, `/api/v1/auth/login/`, `/api/v1/auth/logout/`, `/api/v1/auth/me/`).
- **Customer Data Privacy**: Hard isolation preventing any user from accessing another user's cart, addresses, or order details.

### 3.2 Product Catalog & Variant Architecture
- **Hierarchical Categories**: Support for parent-child category relationships (e.g., `Women > Outerwear > Trench Coats`) with slug-based routing.
- **Product Entity**: Core metadata (title, slug, description, care instructions, base price, brand/collection, published status).
- **Variant Matrix**: Products support multiple variants based on attributes:
  - Size (e.g., XS, S, M, L, XL)
  - Color (e.g., Midnight Black, Emerald Green, with color codes/swatches)
  - SKU (Stock Keeping Unit) unique per variant
  - Variant-specific pricing override (optional)
- **Visual Assets**: Multi-image galleries per product and per variant with display order and primary thumbnail designations.

### 3.3 Inventory Management
- **Variant-Level Stock**: Quantity tracking managed strictly at the SKU/variant level.
- **Concurrency & Stock Integrity**: Stock verification and decrementing executed within atomic database transactions with row-level locks (`select_for_update`) to prevent overselling.
- **Inventory Thresholds**: Visual indicators for "Low Stock" and automatic disabling of "Add to Cart" for out-of-stock variants.

### 3.4 Shopping Cart
- **Dual Mode Support**:
  - **Guest Cart**: Stored via a secure token/session identifier.
  - **Authenticated Cart**: Linked directly to the customer account.
- **Cart Merge**: Seamless merge of guest cart items into customer cart upon registration or login.
- **Real-Time Validation**: Cart pricing and variant availability validated against current database state.

### 3.5 Checkout & Payments
- **Guest Checkout Support**: Customers can place orders with name, phone number, delivery address, and optional email without mandatory password creation.
- **Cash on Delivery (COD)**: First-class payment method supporting order placement, order verification, and COD collection tracking.
- **Price Freezing**: Order line items must store exact snapshot prices (unit price, item title, SKU, variant attributes) at the time of purchase, immutable against future catalog price changes.

### 3.6 Order Lifecycle & Management
- **Status Workflow**:
  ```mermaid
  stateDiagram-v2
      [*] --> Pending: Order Placed (COD)
      Pending --> Confirmed: Phone / Staff Verification
      Confirmed --> Processing: Packing & Warehousing
      Processing --> Shipped: Handed to Courier
      Shipped --> Delivered: Cash Collected
      Pending --> Cancelled: Customer/Staff Cancellation
      Confirmed --> Cancelled: Cancellation
      Delivered --> Returned: Return / Refund Processed
  ```
- **Order Tracking**: Customer-accessible order timeline tracking.

### 3.7 Staff & Operational Dashboard
- **Dedicated Operational Views**:
  - Order review queue with COD verification status toggles.
  - Variant stock adjustment and inventory inspection tools.
  - Catalog management interface for product and variant creation.
- **Permission Enforcement**: Dashboard endpoints protected by backend staff/role permission classes.

---

## 4. Non-Functional Requirements

- **Performance**:
  - API response latency under 200ms for catalog and cart endpoints.
  - Optimized database queries using Django's `select_related` and `prefetch_related` to eliminate N+1 query patterns.
- **Security**:
  - Strict customer data isolation across all endpoints.
  - Protection against CSRF, CORS origin validation, rate limiting on checkout and authentication endpoints.
  - Sanitization of all user inputs and media upload validation (file size, mime type, image dimensions).
- **Usability & Aesthetics**:
  - Mobile-first responsive design tailored for luxury/contemporary fashion browsing.
  - Touch-friendly product carousels, responsive filtering drawers, and streamlined checkout ergonomics.

---

## 5. Unresolved Business Decisions (Client Input Required)

To avoid inventing assumptions, the following operational requirements are identified as pending clarification:

1. **Cart Stock Reservation Policy**:
   - *Option A*: Stock is reserved immediately when an item is added to cart with an expiration timer (e.g., 15 minutes).
   - *Option B* (Standard): Stock is checked and reserved only at the moment of checkout order submission.
2. **Shipping & Delivery Fee Structure**:
   - Flat delivery fee vs. tier-based by city/region vs. free shipping threshold (e.g., free shipping over $X).
3. **Guest Account Post-Checkout Behavior**:
   - Should an account be automatically generated with an invitation email/SMS, or should guest orders remain completely unlinked unless manually claimed?
4. **COD Return & Refund Settlement**:
   - Policy for returns on Cash on Delivery orders (e.g., refund via bank transfer, store credit, or direct courier cash pickup).
5. **Notification Channels**:
   - Integration preference for order confirmations and status updates (Email via SendGrid/SES, SMS via Twilio/local gateway, or WhatsApp API).
