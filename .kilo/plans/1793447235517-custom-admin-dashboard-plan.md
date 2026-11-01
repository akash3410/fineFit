# Custom E-commerce Admin Dashboard - Implementation Plan

## 1. Existing Project Inspection

### Current State Analysis
The project has been partially implemented with Django Unfold, and we have the following:

**Apps Structure:**
- `apps.accounts` - CustomUser (email-based auth), roles/permissions
- `apps.catalog` - Categories, Subcategories, Products, ProductVariant, ProductImage (with soft-delete and enhanced fields)
- `apps.inventory` - Stock management (StockRecord, StockMovement)
- `apps.cart` - Shopping cart functionality
- `apps.dashboard` - Basic dashboard app created

**Current Models (in apps.catalog):**
- `Category`: name, slug, description, is_active, is_deleted, deleted_at, parent (self-referential), timestamps
- `Subcategory`: category (FK), name, slug, description, is_active, is_deleted, deleted_at, timestamps
- `Product`: title, slug, sku, description, price, discount_price, stock, status, is_published, is_featured, is_deleted, deleted_at, category, subcategory, timestamps
- `ProductVariant`: product (FK), sku, size, color_name, color_code, price_override, stock, is_active, timestamps
- `ProductImage`: product (FK), variant (FK), image, alt_text, display_order, is_primary, is_main, timestamps

**Current Admin Setup:**
- Using Django Unfold (`unfold.admin.ModelAdmin`)
- Basic admin registrations for all catalog models
- Currently shows default Django model listing in admin
- Dashboard app exists with a simple view

**Templates & Static:**
- `templates/admin/dashboard.html` exists (basic Bootstrap dashboard)
- `static/js/dynamic_subcategory.js` exists
- Django Unfold configured in settings

**URLs:**
- Admin at `/admin/`
- API at `/api/v1/`
- Dashboard at `/dashboard/`

### Key Observations
- The project already has the models and basic admin setup we need
- Django Unfold is installed and configured
- Soft-delete is implemented (`is_deleted`, `deleted_at`)
- Stock is tracked on both Product and ProductVariant
- Dynamic subcategory JS exists but may need enhancement
- The user wants to replace the default model listing with custom management pages

## 2. Proposed Dashboard Layout

### Main Layout Structure
```
┌─────────────────────────────────────────────────────────┐
│                    Top Navbar                            │
│  Page Title | Admin Profile Dropdown | Logout           │
└─────────────────────────────────────────────────────────┘
┌───────────┬─────────────────────────────────────────────────┐
│  Sidebar  │              Main Content Area                  │
│  Nav      │  (Custom pages: Dashboard, Categories, etc.)    │
└───────────┴─────────────────────────────────────────────────┘
```

### Layout Features
- **Fixed left sidebar** (250-280px width) - collapsible on mobile
- **Main content area** with proper padding and max-width
- **Top navbar** with breadcrumb/page title, user menu, logout
- **Responsive design** - sidebar collapses to hamburger on mobile
- **Consistent styling** using Bootstrap 5 (already in use) with custom CSS
- **Active menu highlighting**

### Design Principles
- Clean, professional e-commerce aesthetic
- Card-based layout for statistics
- Data tables with proper spacing
- Consistent color scheme
- Icon usage (Bootstrap Icons or similar)

## 3. Sidebar Navigation Structure

The sidebar must contain these menu items in order:

```python
SIDEBAR_MENU = [
    {
        'name': 'Dashboard',
        'url': '/admin/custom-dashboard/',  # or custom URL
        'icon': 'bi-speedometer2',
        'active': False
    },
    {
        'name': 'Categories',
        'url': '/admin/categories/',
        'icon': 'bi-folder',
        'active': False
    },
    {
        'name': 'Subcategories',
        'url': '/admin/subcategories/',
        'icon': 'bi-diagram-2',
        'active': False
    },
    {
        'name': 'Products',
        'url': '/admin/products/',
        'icon': 'bi-box-seam',
        'active': False
    }
]
```

**Implementation Notes:**
- Active menu highlighting based on current URL
- Icons from Bootstrap Icons
- All routes under `/admin/` namespace or custom namespace
- Must not use default Django model listing URLs

## 4. Page-by-Page UI Structure

### 4.1 Dashboard Page
**Route:** `/admin/custom-dashboard/` or `/admin/`
**Purpose:** Overview with statistics

**Layout:**
- Header: "Dashboard" with breadcrumb
- Statistics cards row (4 cards):
  1. Total Categories
  2. Total Subcategories  
  3. Total Products
  4. Active Products
- Additional stats row (3 cards):
  1. Low Stock Products
  2. Out of Stock Products
  3. Total Inventory Value
- Recent Products table (last 10)
- Quick action buttons

### 4.2 Category Management

#### Category Index Page
**Route:** `/admin/categories/`
**Components:**
- Header with "Categories" title and "Add Category" button
- Search bar: input + search button
- Table with columns: Name, Status, Created Date, Actions
- Actions: View (eye icon), Edit (pencil icon), Delete (trash icon)
- Pagination (10 per page) with prev/next and page numbers
- Empty state message if no records

#### Category Add Page
**Route:** `/admin/categories/add/`
**Form fields:**
- Name (text, required)
- Description (textarea)
- Status: Active/Inactive (radio or select)
- Slug (auto-generated, readonly or auto-filled)
- Save and Cancel buttons

#### Category Edit Page
**Route:** `/admin/categories/<id>/edit/`
**Same fields as add, pre-filled with existing data**

#### Category View Page
**Route:** `/admin/categories/<id>/view/`
**Display:**
- All category information
- Related subcategories (table/list)
- Edit and Back buttons

### 4.3 Subcategory Management

#### Subcategory Index Page
**Route:** `/admin/subcategories/`
**Components:**
- Header with "Subcategories" and "Add Subcategory"
- Search by name
- Filter by parent category (dropdown)
- Table: Name, Parent Category, Status, Created Date, Actions
- Pagination (10 per page)
- Preserve search and filter in pagination URLs

#### Subcategory Add Page
**Route:** `/admin/subcategories/add/`
**Form fields:**
- Name (required)
- Parent Category (dropdown, required)
- Description (textarea)
- Status (Active/Inactive)
- Slug (auto-generated)
- Save and Cancel

#### Subcategory Edit Page
**Route:** `/admin/subcategories/<id>/edit/`
**Same as add, pre-filled**

#### Subcategory View Page
**Route:** `/admin/subcategories/<id>/view/`
**Display:**
- Subcategory details
- Parent category link
- Related products (table)
- Edit and Back

### 4.4 Product Management

#### Product Index Page
**Route:** `/admin/products/`
**Components:**
- Header with "Products" and "Add Product"
- Search by product name and SKU
- Category filter dropdown
- Subcategory filter dropdown (dynamically updated)
- Table: Thumbnail, Name, SKU, Category, Subcategory, Price, Stock, Status, Actions
- Low stock indicator (e.g., badge or color)
- Out of stock indicator
- Pagination (10 per page)
- Preserve all filters

#### Product Add Page
**Route:** `/admin/products/add/`
**Sections:**

**Basic Info:**
- Product Name (required)
- SKU (required)
- Category (dropdown, required)
- Subcategory (dropdown, dynamic, required)
- Description (textarea)
- Regular Price (number, required)
- Discount Price (number, optional)
- Stock (number, when no variants)
- Status: Active/Inactive
- Featured: Yes/No

**Product Images:**
- Multiple image upload
- Image preview
- Main image selection (radio buttons)
- Add more images button

**Product Variants:**
- "Add Variant" button
- Variant rows with: Size, Color, Variant SKU, Variant Stock, Price Override
- Remove variant button per row
- Validation

#### Product Edit Page
**Route:** `/admin/products/<id>/edit/`
**Same sections as add, with:**
- Load existing product data
- Manage existing images (view, change main, remove)
- Upload additional images
- Manage existing variants (add/edit/remove)
- Preserve relationships

#### Product View Page
**Route:** `/admin/products/<id>/view/`
**Display:**
- Product image gallery with main image highlighted
- All product details
- Category and Subcategory
- SKU and pricing
- Stock information
- Variants table
- Status and featured status
- Edit and Back buttons

## 5. CRUD Workflow

### Category CRUD
1. **Create:** Navigate to `/admin/categories/add/` → Fill form → Save → Redirect to index with success message
2. **Read:** Index lists all non-deleted categories with pagination/search → View shows details
3. **Update:** Edit form loads data → Save changes → Redirect to index/view
4. **Delete:** Click Delete → Modal confirmation → Confirm → Soft delete → Redirect with message

### Subcategory CRUD
Same pattern, with category relationship validation

### Product CRUD
Complex with variants and images. Need to handle:
- Multiple model saves (Product, ProductVariant, ProductImage)
- File uploads
- Dynamic relationships
- Stock management

## 6. Search and Filter Logic

### Category
- **Search:** Filter by `name__icontains` or `slug__icontains`
- **No category filter needed**

### Subcategory
- **Search:** `name__icontains`
- **Filter:** `category_id` dropdown
- **Combined:** `Q(name__icontains=q) & Q(category_id=cat)`

### Product
- **Search:** `Q(title__icontains=q) | Q(sku__icontains=q)`
- **Category filter:** `category_id`
- **Subcategory filter:** `subcategory_id` (dependent on category)
- **All combined:** Preserve all query params in pagination

### Implementation
Use Django's `filter()` with Q objects, pass filters to template context, build pagination URLs with preserved params.

## 7. Pagination Logic

**Requirements:**
- Exactly 10 records per page for all three index pages
- Show Previous/Next buttons
- Show page numbers (with ellipsis for many pages)
- Show "Showing X to Y of Z entries"
- Preserve search and filter query parameters

**Implementation:**
Use Django's `Paginator`. In view:
```python
paginator = Paginator(queryset, 10)
page_number = request.GET.get('page')
page_obj = paginator.get_page(page_number)
```

In template, build URLs preserving GET params:
```django
<a href="?page={{ page_obj.previous_page_number }}{% for key,value in request.GET.items %}{% if key != 'page' %}&{{ key }}={{ value }}{% endif %}{% endfor %}">Previous</a>
```

## 8. Delete Modal Workflow

**Requirements:**
- No browser `alert()` or `confirm()`
- Custom modal popup
- Show item name
- "Are you sure you want to delete this item?"
- Cancel and Confirm Delete buttons
- Use existing soft-delete system
- Prevent deletion when related records unsafe
- Success/error messages

**Implementation:**
1. In index table, Delete button has `data-id`, `data-type`, `data-name` attributes
2. Modal HTML in base template or included
3. JavaScript listens for Delete clicks, populates modal
4. On Confirm, POST to delete URL with CSRF token
5. View performs soft delete or checks for dependencies
6. Redirect back with Django messages

**Soft-delete check:**
- Category: Cannot delete if has subcategories or products? Check existing relationships
- Subcategory: Cannot delete if has products
- Product: Can soft delete (has `is_deleted` field)

Use existing model methods where available.

## 9. Backend Architecture

### Apps to Reuse
- `apps.catalog` - All models (Category, Subcategory, Product, ProductVariant, ProductImage)
- `apps.accounts` - Authentication
- `apps.dashboard` - Can extend or replace

### New Components Needed

**Custom Views (in a new app or extend existing):**
Create `apps/admin_panel/` or add to `apps/dashboard/`:
- `CategoryListView`, `CategoryCreateView`, `CategoryUpdateView`, `CategoryDetailView`, `CategoryDeleteView`
- Similar for Subcategory and Product
- Dashboard view

**Forms:**
- `CategoryForm`, `SubcategoryForm`, `ProductForm`, `ProductVariantFormSet`, `ProductImageFormSet`

**URLs:**
- Custom URL patterns under `/admin/` or separate prefix
- Need to decide: extend Django admin URLs or create separate admin panel URLs

**Considerations:**
- The user says "Do not use the default Django model listing as the main management interface"
- But Django Unfold is installed and configured
- Options:
  1. Create completely custom admin panel views outside Django admin
  2. Override Django admin with custom templates/views
  3. Create custom URLs under `/admin/` that bypass default admin

**Recommendation:** Create a new app `apps.admin_panel` with custom views and templates, mounted at URLs like `/admin-panel/` or integrate under `/admin/` with custom views. Since it's under `/admin/`, need to be careful about URL conflicts.

Alternatively, use Django's admin site customization with custom admin views.

**Better approach:** Create `apps.management` or extend `apps.dashboard` with:
- Custom views for CRUD operations
- Custom templates
- Custom URLs
- Keep using existing models and soft-delete

### Template Structure

```
backend/templates/admin_panel/
├── base.html           # Main layout with sidebar and navbar
├── includes/
│   ├── sidebar.html    # Sidebar navigation
│   ├── navbar.html     # Top navbar
│   └── modal.html      # Delete confirmation modal
├── dashboard/
│   └── index.html      # Dashboard page
├── categories/
│   ├── index.html      # List
│   ├── form.html       # Add/Edit
│   └── view.html       # View details
├── subcategories/
│   ├── index.html
│   ├── form.html
│   └── view.html
└── products/
    ├── index.html
    ├── form.html
    └── view.html
```

### Components

**Sidebar Component:** Reusable with active state, icons
**Navbar Component:** Page title, user info, logout
**Table Component:** Consistent table styling
**Form Component:** Consistent form styling
**Modal Component:** Delete confirmation modal
**Pagination Component:** Reusable pagination

### Search and Filtering Implementation

**Views:**
```python
def category_list(request):
    queryset = Category.objects.filter(is_deleted=False)
    search = request.GET.get('q')
    if search:
        queryset = queryset.filter(name__icontains=search)
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'admin_panel/categories/index.html', {
        'page_obj': page_obj, 'search': search
    })
```

**Templates:** Use GET forms for search/filters

### Pagination Implementation
As described in section 7

### Dynamic Category-Subcategory Filtering
In Product form, use JavaScript to load subcategories based on selected category via AJAX or by filtering in template. The existing `static/js/dynamic_subcategory.js` can be adapted.

**Backend endpoint needed:**
```python
def get_subcategories(request, category_id):
    subcategories = Subcategory.objects.filter(category_id=category_id, is_deleted=False)
    data = [{'id': s.id, 'name': s.name} for s in subcategories]
    return JsonResponse({'subcategories': data})
```

Add URL for this.

### Delete Confirmation Modal
Modal in base template, triggered by JavaScript, posts to delete view.

### Authentication and Permission Handling
- Use Django's `@login_required` and `@permission_required` decorators
- Check user is staff/superuser
- Use existing permission system
- Ensure only authenticated admin users can access

## 10. Security and Validation

### Authentication
- Require login for all admin panel views
- Use `@staff_member_required` or custom decorator
- Redirect to login if not authenticated

### Permissions
- Check model permissions
- Use Django's permission system
- Can leverage existing permissions from apps

### Validation
- **Category:** Unique name/slug (already handled), prevent deletion with related objects
- **Subcategory:** Unique name per category, validate category not deleted
- **Product:** Unique SKU, discount_price < price, subcategory belongs to category, validate variants
- **Images:** File type/size validation (use existing validation)
- **Variants:** Unique SKU per variant, validate combinations

### Soft-Delete
- Use existing `is_deleted` fields
- Filter out deleted items in lists
- Prevent editing deleted items
- Check relationships before deletion

### CSRF Protection
- All forms must include CSRF tokens
- AJAX requests must include CSRF

## 11. Testing Checklist

### Category CRUD
- [ ] List categories with pagination (10 per page)
- [ ] Search categories by name
- [ ] Add new category with validation
- [ ] Edit existing category
- [ ] View category details and related subcategories
- [ ] Delete category with confirmation modal
- [ ] Soft-delete works correctly
- [ ] Cannot delete category with subcategories/products
- [ ] Auto-generate slug

### Subcategory CRUD
- [ ] List subcategories with search and category filter
- [ ] Pagination preserves filters
- [ ] Add subcategory with parent category
- [ ] Edit subcategory
- [ ] View subcategory with parent and related products
- [ ] Delete with confirmation
- [ ] Unique constraint per category

### Product CRUD
- [ ] List products with search and filters
- [ ] Dynamic subcategory dropdown
- [ ] Pagination with filters
- [ ] Add product with all fields
- [ ] Multiple image upload with preview
- [ ] Main image selection
- [ ] Add/edit/remove variants
- [ ] Variant validation
- [ ] Edit product (manage images/variants)
- [ ] View product with gallery
- [ ] Delete with confirmation
- [ ] Low stock/out of stock indicators
- [ ] Stock validation

### UI/UX
- [ ] Sidebar navigation works on all pages
- [ ] Active menu highlighting
- [ ] Responsive design
- [ ] Delete modal works correctly
- [ ] No browser alerts/confirms
- [ ] Success/error messages
- [ ] Empty states
- [ ] Form validation messages

### Security
- [ ] Authentication required
- [ ] Permissions enforced
- [ ] CSRF protection
- [ ] Soft-delete prevents data loss

## 12. Implementation Phases

### Phase 1: Setup and Planning (Complete)
- Inspect existing project
- Create detailed plan
- Identify components needed

### Phase 2: Create Admin Panel App Structure
- Create `apps/admin_panel/` app
- Add to INSTALLED_APPS
- Create URL configuration
- Set up template directories

### Phase 3: Create Base Templates and Components
- `base.html` with sidebar and navbar
- Sidebar component
- Navbar component
- Modal component
- CSS/JS for admin panel

### Phase 4: Dashboard Implementation
- Create dashboard view
- Dashboard template
- Statistics calculations

### Phase 5: Category Management
- Views (CRUD)
- Forms
- Templates (index, form, view)
- URLs
- Delete modal integration

### Phase 6: Subcategory Management
- Views (CRUD with filtering)
- Forms with category validation
- Templates
- URLs
- Dynamic dropdown support

### Phase 7: Product Management
- Complex views (handle variants and images)
- Forms and formsets
- Templates with image upload and variants
- AJAX for dynamic subcategory
- URLs
- Validation

### Phase 8: Integration and Testing
- Connect all URLs
- Test all CRUD operations
- Test pagination and search
- Test delete modal
- Test responsive design
- Fix bugs

### Phase 9: Polish and Documentation
- Ensure consistent styling
- Add proper messages
- Final testing
- Clean up

## Important Notes

1. **Reuse existing models** - All models are already in `apps.catalog`. Do not recreate them.
2. **Use soft-delete** - All delete operations should use the existing `soft_delete()` methods or set `is_deleted=True`.
3. **Preserve relationships** - Product-Subcategory-Category relationships must be maintained.
4. **Django Unfold** - Can coexist but custom pages should be separate from default admin model listing.
5. **No Brand functionality** - Not mentioned in requirements, don't add it.
6. **No Customer/Order/Payment** - Out of scope.
7. **Authentication** - Must work with existing auth system.
8. **Validation** - Reuse existing model validation where possible.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| URL conflicts with Django admin | High | Use different URL prefix or careful routing |
| Complex product form with variants/images | High | Use formsets, handle in views properly, test thoroughly |
| Soft-delete breaking existing queries | Medium | Use proper querysets with is_deleted filters |
| Dynamic dropdown issues | Medium | Test JavaScript thoroughly, have fallback |
| Pagination with filters | Medium | Ensure URL building preserves all params |

## Conclusion

This plan provides a comprehensive roadmap for building a custom e-commerce admin dashboard. The implementation will create dedicated management pages for Categories, Subcategories, and Products with all required CRUD operations, search/filter functionality, pagination, and delete confirmation modals, while reusing the existing models and infrastructure.
