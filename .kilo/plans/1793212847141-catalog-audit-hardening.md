# Plan: Initialize React Storefront Connected to Catalog API

## Goal
Create a read-only Vite React TypeScript storefront in `frontend/`, connected to existing Django catalog API through a dev proxy. No cart, checkout, auth, inventory, or dashboard work.

## Environment
- Node.js v26 and npm are available (verified earlier).
- PostgreSQL is available and catalog migrations applied.
- No existing `frontend/` directory should be overwritten without inspection.

## Implementation Steps
1. Inspect git status, frontend absence, `.gitignore`, Django settings/media config, catalog serializers/endpoints.
2. Initialize Vite React TypeScript app in `frontend/`.
3. Configure Tailwind CSS 4 via official Vite plugin.
4. Add React Router routes: `/`, `/shop`, `/products/:slug`.
5. Implement API client:
   - Relative `/api/v1/` paths.
   - Vite proxy to Django dev server.
   - Media proxy as needed.
   - TypeScript types matching real serializer responses.
   - Loading/error/empty/success states.
6. Implement components:
   - Navbar, Footer, Hero, ProductCard, ProductGrid, Filters, VariantSelector, ImageGallery.
7. Implement pages:
   - Home with categories/products from API.
   - Shop with product grid, category filter, sorting, empty/error states.
   - Product detail with images, title, description, price, variants, availability.
8. Add frontend lint/build/test scripts where supported.
9. Update `.gitignore` for frontend artifacts.
10. Update docs/IMPLEMENTATION_PLAN.md only for verified frontend tasks.
11. Run frontend build, lint, tests, backend checks if backend unchanged.

## Risks
- CORS/CSRF/session settings must remain intact.
- No fake product data; use real API data only.
- Product availability should rely only on verified API fields (`is_active`, published status, variant active state).
- Media URLs must resolve through proxy.

## Validation
- `npm run build`
- `npm run lint` if configured
- `npm run test` if configured
- Django system checks if backend touched
- Catalog/accounts tests if backend touched

## Recommended Next Milestone
After storefront verification, implement cart/checkout in a later phase.
