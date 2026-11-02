# Plan: Product/Catalog System Improvements & Next Steps

## Goal
Address data consistency issues in the product/catalog system, complete missing functionality, and prepare for production readiness while following the project's architecture principles.

## Current State Assessment

### What exists (good)
- **Product** (UUID): Core entity with category/subcategory, pricing, status/publishing flags, soft deletes
- **ProductVariant** (UUID): Size/color combinations with SKU, price overrides, per-variant stock
- **ProductImage**: Multiple images per product with primary/main flags, variant association
- **Category/Subcategory**: Hierarchical taxonomy with soft deletes and images (just added)
- **Inventory**: Properly separated into `apps.inventory` with StockRecord/StockMovement, one-to-one with ProductVariant
- **Admin**: Full CRUD for products/categories/subcategories with variants and images
- **API/Serializers**: Read/write serializers with validation

### Issues to address
1. **Stock duplication**: `Product.stock` vs `ProductVariant.stock` vs `StockRecord` in inventory app - risk of drift
2. **Image flag duplication**: `is_primary` and `is_main` both exist with sync logic
3. **SKU clarity**: Product.sku exists but variants have unique SKUs; unclear which is source of truth
4. **Missing API coverage**: Need to check if catalog API endpoints are fully implemented
5. **Validation gaps**: Published products should have variants/images? Need business rules

## Prioritized Plan

### Phase 1: Fix Data Model Inconsistencies (Critical)
**Priority: High - Prevents data drift**

1. **Consolidate stock tracking**
   - Make `Product.stock` a computed property that sums variant stocks, or deprecate it
   - Ensure `StockRecord` remains the source of truth for inventory operations (per architecture)
   - Update admin views to not set Product.stock directly; compute from variants
   - Add migration if removing field, or make it read-only/computed

2. **Remove redundant image flag**
   - Keep only `is_primary` on ProductImage, remove `is_main`
   - Update clean() method to not sync both
   - Update serializers/admin/views to use only `is_primary`
   - Create migration to drop `is_main` column

3. **Clarify SKU strategy**
   - Determine if Product.sku is needed; if variants are sellable units, consider deprecating or making it optional
   - If keeping, add uniqueness constraint and documentation
   - Update admin/UI accordingly

### Phase 2: Strengthen Business Rules & Validation
**Priority: High**

1. **Product publishing validation**
   - Prevent publishing products without active variants
   - Prevent publishing products without at least one image
   - Add validation in clean() or serializers

2. **Variant/stock consistency**
   - Ensure ProductVariant.stock aligns with StockRecord (or use StockRecord exclusively)
   - Add signals or service layer to sync when needed

3. **Price validation**
   - Ensure discount_price validation works correctly with variants
   - Consider variant-level discounts

### Phase 3: API & Frontend Readiness
**Priority: Medium**

1. **Complete catalog API**
   - Review `apps/catalog/views.py` and `urls.py` for completeness
   - Ensure all endpoints work with new models/fields
   - Add filtering/pagination/search
   - Update serializers for categories with images

2. **Admin UX improvements**
   - Show inventory status from StockRecord in product admin
   - Better variant management UI
   - Image ordering/management improvements

### Phase 4: Testing & Documentation
**Priority: Medium**

1. **Add/update tests**
   - Test variant duplication constraints
   - Test image primary constraints
   - Test stock calculations
   - Test publishing validations

2. **Update documentation**
   - Update ARCHITECTURE.md with any model changes
   - Document stock management flow (ProductVariant → StockRecord)

## Implementation Order
1. Fix stock duplication first (highest risk)
2. Fix image flag duplication
3. Add business rule validations
4. API/serializer updates
5. Tests

## Notes
- Follow the principle that Inventory app owns stock (StockRecord is source of truth)
- Product.stock may need to be computed or removed to avoid confusion
- Keep changes backward compatible where possible
- All migrations must be created and applied
- Update serializers in catalog app for new fields (category/subcategory images)
