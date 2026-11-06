/* ────────────────────────────────────────────────────────────────────────────
 * CategoryGallery — editorial category collage.
 *
 * Reference layout: deep-maroon serif headline with a small year, a short lede
 * and four numbered portrait images staggered across the page with their
 * captions underneath.
 *
 * Every image, caption and link is driven by GET /api/v1/categories/ (image,
 * name, slug). Categories without an uploaded image fall back to a toned
 * placeholder instead of a broken image. Loading / error / empty states are
 * handled locally so the rest of the homepage stays untouched.
 * ────────────────────────────────────────────────────────────────────────── */

import { normalizeImageUrl } from "../../utils/image";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getCategories } from "../../api/catalog";
import type { Category, PaginatedResponse } from "../../types/catalog";

const FEATURED_COUNT = 4;
const COLLECTION_YEAR = new Date().getFullYear();

interface CategoryGalleryProps {
  className?: string;
}

function toCategoryList(
  data: Category[] | PaginatedResponse<Category>
): Category[] {
  return Array.isArray(data) ? data : data.results ?? [];
}

export function CategoryGallery({ className }: CategoryGalleryProps) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getCategories();
        if (!cancelled) setCategories(toCategoryList(data));
      } catch {
        if (!cancelled) setError("Failed to load categories");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const sectionClass = ["category-gallery", className].filter(Boolean).join(" ");

  if (loading) {
    return (
      <section className={sectionClass} aria-busy="true" aria-label="Shop by category">
        <div className="category-gallery__inner">
          <div className="category-gallery__stage">
            <div className="category-gallery__intro">
              <span className="category-gallery__skeleton category-gallery__skeleton--title" />
              <span className="category-gallery__skeleton category-gallery__skeleton--lede" />
            </div>
            {Array.from({ length: FEATURED_COUNT }, (_, i) => (
              <div
                key={i}
                className={`category-gallery__item category-gallery__item--${i + 1}`}
                aria-hidden="true"
              >
                <span className="category-gallery__frame category-gallery__skeleton" />
              </div>
            ))}
          </div>
        </div>
      </section>
    );
  }

  if (error || categories.length === 0) return null;

  const featured = categories.slice(0, FEATURED_COUNT);

  return (
    <section className={sectionClass} aria-labelledby="category-gallery-title">
      <div className="category-gallery__inner">
        <div className="category-gallery__stage">
          <header className="category-gallery__intro">
            <h2 id="category-gallery-title" className="category-gallery__title">
              FineFit Collections
              <span className="category-gallery__year">{COLLECTION_YEAR}</span>
            </h2>
            <p className="category-gallery__lede">
              Our aim is to inspire you and provide the energy and confidence you
              need — because the rest is up to you. Explore the collections,
              chosen for the refined wardrobe.
            </p>
            <Link to="/shop" className="category-gallery__view-all">
              View all categories
              <svg
                className="category-gallery__view-all-arrow"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={1.75}
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </header>

          {featured.map((category, index) => (
            <Link
              key={category.id}
              to={`/shop?category=${category.slug}`}
              className={`category-gallery__item category-gallery__item--${index + 1}`}
              aria-label={`Browse the ${category.name} collection`}
            >
              <span className="category-gallery__index" aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="category-gallery__frame">
                {category.image ? (
                  <img
                    src={normalizeImageUrl(category.image) ?? undefined}
                    alt=""
                    className="category-gallery__image"
                    loading="lazy"
                    decoding="async"
                    aria-hidden="true"
                  />
                ) : (
                  <span className="category-gallery__placeholder" aria-hidden="true" />
                )}
              </span>
              <span className="category-gallery__caption">{category.name}</span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
