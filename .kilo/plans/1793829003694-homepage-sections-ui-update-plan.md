# Plan: Update Homepage Sections to Match Design References

## Goal
Update the homepage UI for Event section, Category section, Subcategory section, and Latest Products section to match the provided design references (events.jpeg, categorie.jpeg, subcategorie.jpeg, latestproduct.jpeg). **Hero section must remain unchanged**.

## Current State
- Hero: `FashionHeroSlider` - must not touch
- Events: `EventsAnnouncement` component (rotating card, currently vertical/compact style)
- Categories: `CategoryGallery` component (asymmetric masonry-like grid)
- Subcategories: `SubcategoryStrip` component (horizontal pill cards with scroll)
- Latest Products: `LatestProducts` component (grid with cards)

All sections are data-driven from backend APIs and have their own CSS in `frontend/src/index.css`.

## Key Decisions Needed (to be confirmed with user)
Since I cannot see the images, I need to clarify:
1. **Events section**: Does it want a banner style (full-width horizontal) vs current compact card? Maybe a carousel/slider of event banners?
2. **Categories**: Grid layout changes (maybe more standard grid vs asymmetric gallery)? Card styling (overlay text position, aspect ratios)?
3. **Subcategories**: Pills vs grid of cards? Different styling?
4. **Latest Products**: Card layout changes (product card design), grid columns?

## Implementation Plan

### 1. Events Announcement Section
**Current**: Single rotating card with fade transition, overlay image, title/announcement text, CTA button
**Likely changes based on typical e-commerce patterns**:
- May want full-width banner style instead of card-in-container
- Different layout (horizontal split between image and content)
- More prominent styling
- Or different animation style

**Files to modify**:
- `frontend/src/components/homepage/EventsAnnouncement.tsx` - restructure JSX/CSS classes
- `frontend/src/index.css` - update `.events-announcement*` styles

**Considerations**:
- Keep the data fetching logic, rotation logic, accessibility features
- Keep props interface compatible
- Don't change API contracts

### 2. Category Gallery Section  
**Current**: Asymmetric grid with feature/medium/small cards, image zoom on hover, overlay
**Likely changes**:
- More uniform grid layout
- Different card styling (rounded corners, shadows, text overlays)
- Maybe different aspect ratios
- Different "View all" button style

**Files to modify**:
- `frontend/src/components/homepage/CategoryGallery.tsx`
- `frontend/src/index.css` - `.category-gallery*`

### 3. Subcategory Strip Section
**Current**: Horizontal scrolling pills with rounded edges, images in circles, "Load more" button
**Likely changes**:
- Maybe grid layout instead of horizontal strip?
- Or different pill styling
- Or show as cards in a grid

**Files to modify**:
- `frontend/src/components/homepage/SubcategoryStrip.tsx`
- `frontend/src/index.css` - `.subcategory-strip*`

### 4. Latest Products Section
**Current**: Grid of product cards with image, badges (Sale/New), price, "View all" link, Load more
**Likely changes**:
- Card design updates (shadows, borders, hover effects)
- Grid responsive columns
- Badge positioning/styling
- Maybe different "Add to cart" or quick view buttons

**Files to modify**:
- `frontend/src/components/homepage/LatestProducts.tsx`
- `frontend/src/index.css` - `.latest-products*`

## Technical Approach
1. **Analyze CSS patterns** - Understand current design tokens, spacing, colors
2. **Make minimal changes** - Preserve all data fetching, state management, accessibility
3. **Update styles first** - CSS changes often drive UI changes
4. **Component structure** - Only change JSX if layout structure needs to change
5. **Test responsiveness** - Ensure mobile/tablet/desktop work
6. **Keep hero untouched** - Verify `FashionHeroSlider` not modified

## Validation
- [ ] Hero section unchanged
- [ ] All four sections load data correctly
- [ ] Loading/empty/error states work
- [ ] Responsive design works on mobile
- [ ] Hover/focus states work
- [ ] No console errors
- [ ] TypeScript compiles

## Risks
- Without seeing images, styling guesses may not match exactly - need to iterate
- CSS class names might need to change if structure changes significantly
- Need to be careful not to break existing functionality

## Next Steps
1. Start by examining the full CSS for all four sections more closely
2. Look at any design system/tokens in use
3. Make targeted style updates based on common modern e-commerce patterns
4. Test the changes
5. Be ready to adjust based on feedback
