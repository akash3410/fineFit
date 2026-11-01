# RBAC Admin System Implementation Plan (Detailed)

## Goal
Implement a robust Role-Based Access Control (RBAC) system for the admin panel with Django Groups/Permissions, supporting admin user management, role management, phone/email login, and granular permissions. Only Super Admin can manage admins/roles/permissions. Preserve all existing customer functionality.

## Current State Analysis
- **CustomUser**: UUID PK, email as USERNAME_FIELD, phone_number optional, groups/user_permissions present
- **Admin Panel**: Django server-rendered admin at `/admin/` (separate from Django's built-in admin at `/admin/` routes? Actually config/urls.py shows `path("admin/", include(...admin_panel))` so the custom admin panel is mounted at `/admin/`. The sidebar has a link to `/admin/` which goes to Django admin - need to check if both exist)
- **Auth**: Session auth with email/password only currently
- **Permissions**: All admin panel views use `@user_passes_test(staff_required)` where `staff_required` just checks `is_active and (is_staff or is_superuser)`. No granular permissions.
- **Sidebar**: Static links, no permission-based visibility

## Requirements Summary
- Use Django Groups as Roles, Permissions as capabilities
- Add admin user CRUD (only Super Admin)
- Add role CRUD with permission assignment (only Super Admin) 
- Extend login to accept identifier (email or phone)
- Enforce permissions on every admin module/backend
- Prevent privilege escalation
- Handle duplicate phone numbers safely
- Preserve existing customer auth/functionality
- Follow existing codebase patterns

## Implementation Steps

### Phase 1: Authentication Enhancements (Email/Phone Login)
**Files to modify:**
- `apps/accounts/models.py` - Add unique constraint for phone_number when not null? Django allows multiple nulls in unique, but need to be careful about duplicates. Also need to ensure phone format normalization
- `apps/accounts/managers.py` - May need helper for phone lookup
- `apps/accounts/views.py` - Modify `SessionLoginView` to accept `identifier` (or keep backward compat with `email`) and look up by email or phone
- `apps/accounts/authentication.py` (new) - Custom authentication backend for email/phone
- `config/settings/base.py` - Add `AUTHENTICATION_BACKENDS`

**Details:**
1. Create custom auth backend that tries email lookup (case-insensitive) then phone lookup
2. Update SessionLoginView to accept `identifier` field, fallback to `email` for backward compatibility
3. Handle phone normalization (strip spaces, etc.)
4. For duplicate phone numbers - need to define behavior. Plan says "Phone login must handle duplicate phone numbers safely" - safest is to not allow login by phone if multiple users have same phone, or require disambiguation. Better to add unique constraint on phone_number where not null and also handle in lookup.

### Phase 2: Permission Infrastructure
**Files to modify/create:**
- `apps/admin_panel/decorators.py` (new) - Custom permission decorators
- `apps/admin_panel/views.py` - Replace `staff_required` with permission-based checks
- `apps/admin_panel/utils.py` (new) - Permission helpers

**Custom Permissions:** Need to define permissions. Django auto-creates add/change/delete/view permissions per model. For app-level permissions like `access_dashboard`, can use `Meta.permissions` in models or create via migrations/data migrations.

Also need to map each admin view to required permission:
- Dashboard: need `access_dashboard` or general staff access with specific perm
- Categories: view/add/change/delete_category (or model perms)
- Products: similar
- Subcategories: similar
- Admin users management: superuser only
- Roles/permissions: superuser only

### Phase 3: Admin User Management (Superuser Only)
**Files to create/modify:**
- `apps/admin_panel/admin_user_views.py` (new) or add to views.py
- `apps/admin_panel/forms.py` (new) - Forms for creating/editing admin users
- `apps/admin_panel/urls.py` - Add routes for admins CRUD
- `templates/admin_panel/admins/*` (new templates)
- `templates/admin_panel/includes/sidebar.html` - Add Admins, Roles & Permissions links (visible to superuser)

**Features:**
- List admin users (filter by role, search)
- Create admin user: name, email, phone, password, assign roles (groups). Must set is_staff=True
- Edit admin user: update details, change roles, toggle active status
- Delete/deactivate admin user
- Prevent self-deletion
- Prevent deleting last superuser
- Only superusers can access these views

### Phase 4: Role & Permission Management (Superuser Only)
**Files to create/modify:**
- `apps/admin_panel/role_views.py` (new)
- `apps/admin_panel/forms.py` - Role forms
- `apps/admin_panel/urls.py` - Add role routes
- `templates/admin_panel/roles/*` (new)
- API endpoint to get permission catalog grouped by app/model

**Features:**
- List roles (Groups)
- Create role with name and description (maybe via RoleProfile model? Plan says "If descriptions needed, create RoleProfile (OneToOne Group) later. Keep out of scope to avoid duplication." But sidebar says "Roles & Permissions" - maybe just groups is fine)
- Edit role: assign/remove permissions
- Delete role (with safeguards)
- Permission catalog view grouped by app

### Phase 5: Frontend Integration (if needed)
The plan says "Update sidebar + frontend pages" - but looking at structure, admin panel is Django templates. Frontend/ is separate React app. Maybe the "frontend" in plan refers to the admin panel UI (templates). The React frontend might have admin features? Let us look up frontend structure.

Also need to update CurrentUserView serializer to include permissions/groups for frontend to use? Plan says "Expose permissions in `CurrentUserView` serializer for frontend."

### Phase 6: Testing & Validation
Run tests after each major stage. Write tests for auth, permissions, escalation prevention.

## Key Constraints & Safeguards
1. **Existing customer auth unchanged** - only extend, don't break
2. **Only Super Admin** can create admins, manage roles/permissions
3. **Prevent privilege escalation** - non-superuser cannot create/edit superuser or assign perms they don't have
4. **Phone login duplicate handling** - if multiple users share phone, don't allow phone login or require disambiguation
5. **Backend permission enforcement on every module**
6. **Follow existing patterns** - don't rewrite unnecessarily

## Files to Modify/Create Summary
**Create:**
- `apps/accounts/authentication.py`
- `apps/admin_panel/decorators.py`
- `apps/admin_panel/forms.py`
- `apps/admin_panel/admin_user_views.py` or integrate into views.py
- `apps/admin_panel/role_views.py`
- `apps/admin_panel/utils.py`
- Templates under `templates/admin_panel/admins/` and `templates/admin_panel/roles/`
- Migration for phone uniqueness and possibly custom permissions

## Implementation Order
1. **Auth**: Register backend in settings, update SessionLoginView to accept identifier (email/phone), handle duplicates safely
2. **Permissions**: Create `apps/admin_panel/decorators.py` with superuser/permission checks, add permission enforcement to admin views
3. **Admin Users**: Create forms/views/urls/templates for admin user CRUD (superuser only) with safeguards
4. **Roles**: Create forms/views/urls/templates for role/permission management (Groups) (superuser only)
5. **UI**: Update sidebar with Admins/Roles links, update serializers to expose permissions/groups
6. **Test**: Validate all flows and safeguards

## Key Safeguards
- Only superusers can create/manage admins, roles, permissions
- Prevent self-deletion and deletion of last superuser
- Non-superusers cannot assign roles/permissions or create superusers
- Backend enforces all permissions (frontend hiding is UX only)
- Duplicate phone numbers: backend returns None on auth if count != 1 (prevents login ambiguity)
- Customer auth unchanged
- Preserve existing functionality

## Plan Status
Implementation-ready.
