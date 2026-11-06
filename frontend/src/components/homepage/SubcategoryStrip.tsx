/* ────────────────────────────────────────────────────────────────────────────
 * SubcategoryStrip — leaf-shaped subcategory tiles on a floating white panel.
 *
 * Reference layout: a centred heading over one row of square image tiles whose
 * corners are cut into a leaf shape. Each tile carries the subcategory name in
 * white over a soft scrim, plus a circular arrow that appears on hover/focus,
 * and the row closes with a "Shop All" tile that links to the full catalogue.
 *
 * Tile data (image / name / slug) comes from GET /api/v1/subcategories/.
 * Subcategories without an uploaded image fall back to a toned placeholder.
 * Loading / error / empty states are handled locally so the homepage degrades
 * gracefully when the catalogue API is unavailable.
 * ────────────────────────────────────────────────────────────────────────── */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getSubcategories } from "../../api/catalog";
import type { Subcategory } from "../../types/catalog";

/* Five tiles plus the Shop All tile fill the six-up row exactly. */
const DISPLAY_COUNT = 5;

interface SubcategoryStripProps {
  className?: string;
}

function ArrowIcon({ className }: { className: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M7 17 17 7M9 7h8v8" />
    </svg>
  );
}

/** Contour-style line work for the Shop All tile. */
function ShopAllPattern() {
  return (
    <svg
      className="subcategory-strip__pattern"
      viewBox="0 0 200 200"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <g fill="none" stroke="currentColor" strokeWidth="0.9">
        <circle cx="118" cy="96" r="26" />
        <circle cx="118" cy="96" r="50" />
        <circle cx="118" cy="96" r="74" />
        <circle cx="118" cy="96" r="98" />
        <circle cx="118" cy="96" r="122" />
        <circle cx="118" cy="96" r="146" />
      </g>
    </svg>
  );
}

function subcategoryLink(sub: Subcategory) {
  return `/shop?subcategory=${sub.slug}${
    sub.category_slug ? `&category=${sub.category_slug}` : ""
  }`;
}

export function SubcategoryStrip({ className }: SubcategoryStripProps) {
  const [subcategories, setSubcategories] = useState<Subcategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getSubcategories({
          page: "1",
          page_size: String(DISPLAY_COUNT),
        });
        if (!cancelled) setSubcategories(data.results);
      } catch {
        if (!cancelled) setError("Failed to load subcategories");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const sectionClass = ["subcategory-strip", className].filter(Boolean).join(" ");

  if (loading) {
    return (
      <section className={sectionClass} aria-busy="true" aria-label="Shop by subcategory">
        <div className="subcategory-strip__panel">
          <span className="subcategory-strip__title subcategory-strip__skeleton subcategory-strip__skeleton--title" />
          <div className="subcategory-strip__grid">
            {Array.from({ length: 6 }, (_, i) => (
              <span key={i} className="subcategory-strip__card subcategory-strip__skeleton" />
            ))}
          </div>
        </div>
      </section>
    );
  }

  if (error || subcategories.length === 0) return null;

  return (
    <section className={sectionClass} aria-labelledby="subcategory-strip-title">
      <div className="subcategory-strip__panel">
        <h2 id="subcategory-strip-title" className="subcategory-strip__title">
          Find Your Fit
        </h2>
        <p className="subcategory-strip__description" aria-label="Made for your style.">
          Made for your style.
        </p>

        <div className="subcategory-strip__grid">
          {subcategories.map((sub) => (
            <Link
              key={sub.id}
              to={subcategoryLink(sub)}
              className="subcategory-strip__card"
              aria-label={`Browse ${sub.name}`}
            >
              {sub.image ? (
                <img
                  src={sub.image}
                  alt=""
                  className="subcategory-strip__image"
                  loading="lazy"
                  decoding="async"
                  aria-hidden="true"
                />
              ) : (
                <span className="subcategory-strip__fallback" aria-hidden="true" />
              )}
              <span className="subcategory-strip__scrim" aria-hidden="true" />
              <span className="subcategory-strip__body">
                <span className="subcategory-strip__label">{sub.name}</span>
                <span className="subcategory-strip__action" aria-hidden="true">
                  <ArrowIcon className="subcategory-strip__action-icon" />
                </span>
              </span>
            </Link>
          ))}

          <Link
            to="/shop"
            className="subcategory-strip__card subcategory-strip__card--shop-all"
            aria-label="Shop all products"
          >
            <span className="subcategory-strip__pattern-wrap" aria-hidden="true">
              <ShopAllPattern />
            </span>
            <span className="subcategory-strip__body subcategory-strip__body--shop-all">
              <span className="subcategory-strip__action subcategory-strip__action--visible" aria-hidden="true">
                <ArrowIcon className="subcategory-strip__action-icon" />
              </span>
              <span className="subcategory-strip__label">Shop All</span>
            </span>
          </Link>
        </div>
      </div>
    </section>
  );
}
