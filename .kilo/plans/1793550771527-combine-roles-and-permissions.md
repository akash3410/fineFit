# Plan: Combine Roles and Permissions

## Goal
Unify Roles and Permissions into a single, easier-to-manage interface. Instead of jumping between two separate pages, admins should be able to manage "who can do what" from one place.

## Current State
- **Roles page** (`/admin/roles/`): Lists groups/roles with their assigned permissions (comma-separated). Can create/edit/delete roles and assign permissions via checkboxes.
- **Permissions page** (`/admin/permissions/`): Read-only flat list of all Django permissions with name, codename, and content type. No way to see which roles have them or manage assignments.
- **Navigation**: Separate "Roles" and "Permissions" links in the sidebar (superuser only).
- **Model**: Uses Django's built-in `auth.Group` (roles) and `auth.Permission` with many-to-many relationship. No schema changes needed.

## Recommended Approach: Tabbed "Access Control" Page
The cleanest approach is to create a single **Access Control** page with tabs. This keeps existing role-management flows intact while adding a powerful matrix view.

### UI Structure
```
/admin/access-control/
├── Tab 1: Roles (default)
│   ├── Role list with permission count
│   ├── Quick "Manage Permissions" action per role
│   └── Create/Edit role buttons
├── Tab 2: Permission Matrix
│   ├── Roles as columns, permissions as rows
│   ├── Grouped by app (accounts, catalog, orders, etc.)
│   ├── Checkboxes to assign/revoke permissions
│   └── Bulk actions (select all per app/role)
└── Tab 3: All Permissions
    ├── Searchable/filterable list
    ├── Grouped by app/model
    └── Shows which roles use each permission
```

## Implementation Plan

### Phase 1: Create the Unified View & Route
1. **Add view in `apps/admin_panel/role_views.py`**
   - Create `access_control(request)` view that handles all three tabs
   - For matrix tab: build a structure like `{permissions_by_app: {app_label: [(permission, [role_ids_that_have_it])]}, roles: [...]}`
   - Handle POST for matrix updates (assign/revoke permissions)
   - Reuse existing permission/role queries

2. **Add URL in `apps/admin_panel/urls.py`**
   - Add `path("access-control/", role_views.access_control, name="access_control")`
   - Keep existing `/admin/roles/` and `/admin/permissions/` URLs working (optionally redirect to new page with appropriate tab)

### Phase 2: Build the Template
1. **Create `templates/admin_panel/roles/access_control.html`**
   - Bootstrap tabs for Roles / Permission Matrix / All Permissions
   - Preserve existing role list UI in the "Roles" tab (or enhance it)
   - Build matrix table with sticky headers/columns for usability
   - Add search/filter for permissions and roles
   - Group permissions by `content_type.app_label` with collapsible sections

2. **Matrix interactions**
   - Check/uncheck permissions and submit to update role permissions
   - "Select all" per app section
   - Show visual feedback on save
   - Consider AJAX for smoother UX (optional but nice)

### Phase 3: Update Navigation
1. **Update `templates/admin_panel/includes/sidebar.html`**
   - Replace separate "Roles" and "Permissions" links with single "Roles & Permissions" linking to `access_control`
   - Or keep both but make "Roles" point to access-control with `?tab=roles` (cleaner to consolidate)
   - Only show for superusers (keep existing permission check)

2. **Update existing templates/links**
   - Update any references to `role_list` or `permission_list` to point to the new unified page where appropriate
   - Role edit/create can still exist as modal or separate pages, or be integrated into tabs

## Technical Details

### View Logic (Matrix Updates)
```python
# Handle POST for permission matrix
if request.method == 'POST' and request.POST.get('action') == 'update_matrix':
    # Clear and rebuild permissions for affected roles
    for role in roles:
        perm_ids = request.POST.getlist(f'perms_{role.id}')
        role.permissions.set(perm_ids)
    messages.success(request, 'Permissions updated successfully.')
```

### Template Considerations
- Use `request.GET.tab` to determine active tab
- For large permission sets, use horizontal scroll on matrix
- Group by app label with section headers
- Show permission count per role in Roles tab
- Make matrix responsive

## Pros & Cons

### Pros
- **Better UX**: See entire permission structure at a glance
- **Faster management**: Assign permissions across roles without navigating back and forth
- **Less clutter**: One menu item instead of two
- **Discoverability**: Easy to spot missing/wrong permissions
- **Leverages existing models**: No migrations needed

### Cons
- **More complex template**: Matrix can get wide with many roles/permissions
- **Performance**: Loading all permissions and roles at once (can be optimized with prefetching)
- **Learning curve**: Matrix view might be overwhelming for new admins

## Recommendation
**Go with the tabbed "Access Control" approach.** Make the Permission Matrix the star feature (Tab 2) since it's the most useful for RBAC management. Keep the Roles tab for quick role CRUD, and move the detailed permissions list to Tab 3 as a reference view.

Start with Phase 1-2, keep old URLs functional via redirects to maintain backward compatibility.
