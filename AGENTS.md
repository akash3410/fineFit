# AGENTS.md - Development & AI Agent Operating Guide

## 1. Project Context & Purpose

This repository houses the codebase for a professional, production-oriented fashion e-commerce platform.
The platform is designed as an **API-first modular monolith** powering:
1. A fast, modern, mobile-friendly fashion customer storefront.
2. An intuitive, permission-controlled staff/admin operations dashboard.

> **Foundational Principle**: The initial demo and code artifacts must serve as the production foundation of the system, not a throwaway prototype. Every component, schema definition, and endpoint must be structured for maintainability, security, and testability from day one.

---

## 2. Technology Stack & Environment

| Component | Technology | Target Version / Baseline |
| :--- | :--- | :--- |
| **Backend Framework** | Django | 5.2.18 (Python 3.12 compatible) |
| **API Framework** | Django REST Framework (DRF) | 3.18.3 |
| **Database** | PostgreSQL | 16+ (using `psycopg` v3 adapter, `psycopg[binary]==3.3.6`) |
| **Authentication** | SessionAuth + CSRF / Custom User | Custom User mapped to `AUTH_USER_MODEL` before initial migration; Session authentication with CSRF protection for browser client |
| **Frontend Framework** | React + TypeScript | React 18.x / 19.x + TypeScript 5.x |
| **Frontend Tooling** | Vite | 5.x / 6.x |
| **Styling** | Tailwind CSS | Modern utility-first CSS |
| **API Versioning** | URL prefix | `/api/v1/` |

### Environment Verification Status
- **Host OS**: Ubuntu 24.04.5 LTS (Noble Numbat)
- **Host Python**: Python 3.12.3 installed (`/usr/bin/python3`, `virtualenv` available)
- **Host Node.js**: Not yet installed on system PATH (Node.js 20 LTS or 22 LTS required for frontend build tooling)
- **Host PostgreSQL**: PostgreSQL client/server to be configured (either local service or Dockerized PostgreSQL container)

---

## 3. System Architecture & Modular Layout

The repository follows a clean monolithic workspace structure separating backend services and frontend applications:

```
e_com/
├── AGENTS.md                  # Master agent instructions & operating manual
├── docs/                      # Architectural, business, and implementation specs
│   ├── PRD.md                 # Product Requirements Document
│   ├── ARCHITECTURE.md        # Technical architecture, schemas & API contracts
│   ├── IMPLEMENTATION_PLAN.md # Phased implementation roadmap & task tracking
│   └── DECISIONS.md           # Architecture Decision Records (ADRs) & pending decisions
├── backend/                   # Django REST Framework modular monolith
│   ├── manage.py
│   ├── config/                # Django project settings (base, local, production), wsgi, asgi, urls
│   │   ├── settings/
│   │   └── urls.py
│   └── apps/                  # Modular domain applications
│       ├── accounts/          # CustomUser, Roles, Permissions, Auth endpoints
│       ├── catalog/           # Categories, Products, Images, Attributes, Variants
│       ├── inventory/         # Variant-level stock, reservations, ledger
│       ├── cart/              # Session/Customer shopping cart & items
│       ├── orders/            # Orders, OrderItems, Status workflow, Guest checkout, COD
│       └── dashboard/         # Staff/Admin analytics & operations API
└── frontend/                  # React + TypeScript + Vite SPA
    ├── index.html
    ├── vite.config.ts
    ├── src/
    │   ├── api/               # API clients & type-safe endpoint wrappers (/api/v1/)
    │   ├── components/        # Shared UI components (Tailwind CSS)
    │   ├── features/          # Domain-driven features (catalog, cart, checkout, dashboard)
    │   ├── hooks/             # Custom reusable React hooks
    │   ├── types/             # Domain TypeScript definitions matching backend contracts
    │   └── routes/            # React Router / Page navigation
```

---

## 4. Coding Conventions & Standards

### 4.1 Backend (Python / Django)
- **Python Version**: Strictly target Python 3.12+. Use modern type annotations (`typing` / built-in `list`, `dict`, `int | None`).
- **Domain Logic Separation**:
  - Keep models rich with data integrity rules and querysets.
  - Implement business workflows in dedicated service layers (`services.py`) or selector functions (`selectors.py`), avoiding bloated serializers and monolithic views.
- **API Serializers**:
  - Separate Read/List serializers from Write/Create serializers where domain logic warrants it.
  - Never allow direct mass-assignment of sensitive fields (e.g., `is_staff`, `is_superuser`, `role`).
- **Database Migrations**:
  - Never modify applied migrations in production environments.
  - Always give descriptive names to migration files.
  - Never execute initial migrations before `AUTH_USER_MODEL = 'accounts.CustomUser'` is in place.
- **Transactions & Concurrency**:
  - Use `transaction.atomic()` for all multi-step state alterations (e.g., order placement, stock deduction).
  - Use `select_for_update()` on variant inventory rows during checkout to avoid overselling race conditions.

### 4.2 Frontend (React / TypeScript / Tailwind CSS)
- **Strict TypeScript**: Avoid `any`. Define clear interfaces and types corresponding to backend API schemas.
- **Component Design**: Build modular, accessible, mobile-first components.
- **State Management**: Utilize lightweight server-state management (e.g., TanStack Query or native typed hooks with caching) to minimize unnecessary client synchronization bugs.
- **Styling**: Adhere to Tailwind CSS design tokens (colors, spacing, typography) with responsive breakpoints (`sm`, `md`, `lg`, `xl`).

---

## 5. Security Rules & Data Isolation

1. **Authentication & Authorization**:
   - Authentication must use secure, standard protocols (Session authentication with HttpOnly cookies + CSRF protection for web clients).
   - Roles and permissions must be verified on every API request. Do not rely on frontend route guards for security.
2. **Identifier Predictability vs. Authorization**:
   - UUID primary keys make entity identifiers less predictable and prevent trivial sequential enumeration attacks (e.g. iterating `/orders/1`, `/orders/2`).
   - **Crucial Rule**: UUIDs do **NOT** replace authentication, authorization, object-level permission checks, or customer data isolation. Knowing or obtaining a UUID must never grant access to a resource; every endpoint and QuerySet must enforce tenant/ownership filtering (`filter(user=request.user)`) and strict permission verification.
3. **Customer Data Isolation**:
   - Queries for customer orders, cart items, or profile data must always filter by `request.user` (or session key for guest carts). Never expose customer record identifiers without tenant/ownership checks.
4. **Secrets Management**:
   - Never commit `.env` files, API keys, database credentials, or secret keys to source control.
   - Use `django-environ` or `pydantic-settings` to parse configuration from environment variables.
5. **Input Validation & Sanitization**:
   - Validate all external inputs at the serializer layer.
   - Sanitize rich text inputs and handle user file uploads (product images) with rigorous file-type and extension validation.

---

## 6. Operating Rules for AI Coding Tasks

When working on this codebase in future iterations, all AI agents must follow these mandatory principles:

1. **Step-by-Step Incrementalism**:
   - Focus on one logical phase or application slice at a time.
   - Do not attempt to generate large swathes of untested code across multiple subsystems in a single turn.
2. **Review Environment & Dependencies Before Executing**:
   - Check if virtual environments, package managers, and runtimes are active before installing packages or running commands.
3. **Zero Untested Code**:
   - Every service, API endpoint, and business constraint must be accompanied by unit or integration tests (using `pytest` / `pytest-django` or Django `TestCase`).
4. **No Disposable Prototypes**:
   - Write clean, maintainable, properly commented code adhering to production standards. Avoid hardcoded mock data in production pathways.
5. **Update Documentation**:
   - When introducing architectural changes, schema updates, or resolving business decisions, update `docs/ARCHITECTURE.md`, `docs/PRD.md`, and `docs/DECISIONS.md`.
