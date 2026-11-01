# Add Admins/Roles Menu Links to Sidebar

## Goal
Expose existing admin user and role management pages in the admin panel sidebar, visible only to superusers.

## Current State
- URLs exist: `/admin/admins/`, `/admin/roles/`, `/admin/permissions/`
- Views are superuser-guarded via `superuser_required`
- Sidebar (`backend/templates/admin_panel/includes/sidebar.html`) lacks links to these pages

## Plan
1. Add conditional sidebar section (superuser only) with links:
   - Admin Users → `/admin/admins/`
   - Roles → `/admin/roles/`
   - Permissions → `/admin/permissions/`
2. Use `{% if request.user.is_superuser %}` guard
3. Keep existing styling/icons

## Validation
- Non-superuser staff does not see links
- Superuser sees and can navigate to pages
