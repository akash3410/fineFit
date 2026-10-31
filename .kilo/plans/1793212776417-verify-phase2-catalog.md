# Plan: Verify and Finalize Phase 2 (Catalog)

## Goal
Confirm the already-scaffolded catalog implementation satisfies Phase 2 requirements, run full verification, and update docs/status.

## Steps
1. Run Django system checks: `python manage.py check`
2. Run catalog tests: `pytest apps/catalog`
3. Run accounts tests: `pytest apps/accounts`
4. Run `makemigrations --check` and `migrate --plan`
5. Apply catalog migration to verified PostgreSQL dev DB: `python manage.py migrate`
6. Update `docs/IMPLEMENTATION_PLAN.md` Phase 2 checkboxes to complete.
7. Update `docs/ARCHITECTURE.md` if any deviation from documented schema (note: ProductImage id is BigAutoField vs doc; ProductVariant id UUID; Category id BigAutoField; matches).
8. Update `docs/DECISIONS.md` if new decisions (none expected).

## Known limitations to verify
- CategorySerializer exposes is_active on public endpoint (doc says active only); acceptable.
- ProductImageReadSerializer includes variant id.
- Ensure no stock fields in ProductVariant (confirmed).

## Validation
- All tests pass on PostgreSQL.
- makemigrations --check clean.
