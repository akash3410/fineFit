import { FashionHeroSlider } from "../components/FashionHeroSlider"
import { BrandPromiseStrip } from "../components/homepage/BrandPromiseStrip"
import { EventsAnnouncement } from "../components/homepage/EventsAnnouncement"
import { CategoryGallery } from "../components/homepage/CategoryGallery"
import { SubcategoryStrip } from "../components/homepage/SubcategoryStrip"
import { LatestProducts } from "../components/homepage/LatestProducts"

/* ────────────────────────────────────────────────────────────────────────────
 * Home — FineFit luxury homepage
 *
 * Section order (exact):
 *   1. Hero (FashionHeroSlider — unchanged)
 *   2. Brand Promise Strip
 *   3. Events / Announcements
 *   4. Shop by Category
 *   5. Shop by Subcategory
 *   6. Latest Products
 *
 * Each data-driven section fetches from the real backend API and owns its own
 * loading / empty / error states. The hero is preserved exactly as before,
 * and the Brand Promise Strip connects to it directly with no vertical gap.
 * ─────────────────────────────────────────────────────────────────────────── */

export function Home() {
  return (
    <div>
      {/* ── 1. Hero — cinematic campaign sequence (unchanged) ── */}
      <FashionHeroSlider />

      {/* ── 2. Brand Promise Strip ── */}
      <BrandPromiseStrip />

      {/* ── 3. Events / Announcements ── */}
      <EventsAnnouncement />

      {/* ── 4. Shop by Category ── */}
      <CategoryGallery />

      {/* ── 5. Shop by Subcategory ── */}
      <SubcategoryStrip />

      {/* ── 6. Latest Products ── */}
      <LatestProducts />
    </div>
  )
}
