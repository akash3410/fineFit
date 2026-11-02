# Plan: Add images to Category and Subcategory

## Goal
Add image support to Category and Subcategory models in the catalog app, update admin forms/templates/views, and create migrations.

## Current state
- Category and Subcategory models have no image fields
- ProductImage uses ImageField with custom upload path
- Admin panel handles category/subcategory add/edit via POST data (no ModelForms) in `apps/admin_panel/views.py`
- Templates for category/subcategory forms don't handle file uploads

## Design
1. **Models** (`apps/catalog/models.py`)
   - Add upload path functions `category_image_upload_path` and `subcategory_image_upload_path`
   - Add `image = models.ImageField(upload_to=category_image_upload_path, blank=True, null=True, verbose_name=_("image"), help_text=_("Image for this category."))` to Category
   - Add `image = models.ImageField(upload_to=subcategory_image_upload_path, blank=True, null=True, verbose_name=_("image"), help_text=_("Image for this subcategory."))` to Subcategory

2. **Migrations**
   - Create migration for adding image fields to Category and Subcategory

3. **Admin panel views** (`apps/admin_panel/views.py`)
   - Update `category_add`, `category_edit` to handle `request.FILES` for image
   - Update `subcategory_add`, `subcategory_edit` to handle image upload
   - Save image if provided

4. **Templates**
   - Update `templates/admin_panel/categories/form.html` to add file input and `enctype="multipart/form-data"`
   - Update `templates/admin_panel/subcategories/form.html` similarly
   - Optionally show current image in edit mode

5. **Serializers/API (if needed)**
   - Update catalog serializers if they expose categories/subcategories to include image URL

## Implementation details
- Use upload_to similar to product images for organization
- Make fields optional (blank/null) for backward compatibility
- Ensure forms use `enctype="multipart/form-data"`
- Handle image replacement

## Validation
- Add category with image via admin
- Edit category to change image
- Same for subcategory
- Images display correctly
