/* ────────────────────────────────────────────────────────────────────────────
 * CategoryGallery — editorial category collage.
 *
 * Reference layout: a serif headline with a small year, a short lede and four
 * numbered portrait images staggered across the page with their captions
 * underneath.
 *
 * The four portrait slots are fixed: the grid composition never moves. Only the
 * card contents are paged. When the audience clicks the next / previous arrow,
 * the same four slots swap in the following four categories with a short
 * horizontal fade-through animation, so the headline, lede and layout stay put.
 *
 * Every image, caption and link is driven by GET /api/v1/categories/ (image,
 * name, slug). Categories without an uploaded image fall back to a toned
 * placeholder instead of a broken image. Loading / error / empty states are
 * handled locally so the rest of the homepage stays untouched.
 * ────────────────────────────────────────────────────────────────────────── */

import { normalizeImageUrl } from "../../utils/image";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { getCategories } from "../../api/catalog";
import type { Category, PaginatedResponse } from "../../types/catalog";

/** Four portrait slots per page — the fixed composition of the collage. */
const PAGE_SIZE = 4;
const COLLECTION_YEAR = new Date().getFullYear();

/** Direction of the last page change; drives the card enter animation. */
type PageDirection = "initial" | "next" | "prev";

interface CategoryGalleryProps {
  className?: string;
}

function toCategoryList(
  data: Category[] | PaginatedResponse<Category>
): Category[] {
  return Array.isArray(data) ? data : data.results ?? [];
}

function chunk<T>(items: T[], size: number): T[][] {
  const pages: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    pages.push(items.slice(i, i + size));
  }
  return pages;
}

export function CategoryGallery({ className }: CategoryGalleryProps) {
  const [categories, setCategories] = useState<Category[]>([]);
  const [page, setPage] = useState(0);
  const [direction, setDirection] = useState<PageDirection>("initial");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pagerRef = useRef<HTMLDivElement>(null);
  const visibleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hiddenTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [pagerVisible, setPagerVisible] = useState(false);

  // Sync animation states back to "initial" after each page transition completes.
  useEffect(() => {
    const timer = setTimeout(() => setDirection("initial"), 700);
    return () => clearTimeout(timer);
  }, [direction]);

  // Show/hide the pager based on whether the category section is in view.
  useEffect(() => {
    if (!pagerRef.current) return;

    const margin = 0;
    const rect = pagerRef.current.getBoundingClientRect();
    const sectionTop = rect.top;
    const sectionBottom = rect.bottom;
    const viewportHeight = window.innerHeight;

    // The pager is considered "in view" as long as any part of the section
    // overlaps the viewport. A slight margin keeps it visible when the very
    // bottom edge is near the scroll threshold.
    const topInView = sectionTop <= viewportHeight - margin;
    const bottomInView = sectionBottom >= margin;

    if (topInView && bottomInView) {
      if (hiddenTimer.current) clearTimeout(hiddenTimer.current);
      hiddenTimer.current = null;
      if (!pagerVisible) {
        setPagerVisible(true);
      }
    } else {
      if (visibleTimer.current) clearTimeout(visibleTimer.current);
      visibleTimer.current = setTimeout(() => {
        setPagerVisible(false);
      }, 280);
    }
  }, [pagerVisible]);

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
            {Array.from({ length: PAGE_SIZE }, (_, i) => (
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

  const pages = chunk(categories, PAGE_SIZE);
  const pageCount = pages.length;
  const currentPage = Math.min(page, pageCount - 1);
  const visible = pages[currentPage] ?? [];
  const isFirstPage = currentPage === 0;
  const isLastPage = currentPage === pageCount - 1;
  const firstIndex = currentPage * PAGE_SIZE + 1;
  const lastIndex = currentPage * PAGE_SIZE + visible.length;

  const goToPage = (delta: -1 | 1) => {
    setDirection(delta === 1 ? "next" : "prev");
    setPage((previous) => Math.min(Math.max(previous + delta, 0), pageCount - 1));
  };

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

            {pageCount > 1 && (
              <div className="category-gallery__pager category-gallery__pager--under-view-all">
                <button
                  type="button"
                  className="category-gallery__pager-btn"
                  onClick={() => goToPage(-1)}
                  disabled={isFirstPage}
                  aria-label="Show previous categories"
                >
                  <svg
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.75}
                    aria-hidden="true"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 5l-7 7 7 7" />
                  </svg>
                </button>

                <span className="category-gallery__pager-count" aria-live="polite">
                  {String(currentPage + 1).padStart(2, "0")} / {String(pageCount).padStart(2, "0")}
                </span>

                <button
                  type="button"
                  className="category-gallery__pager-btn"
                  onClick={() => goToPage(1)}
                  disabled={isLastPage}
                  aria-label="Show next categories"
                >
                  <svg
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={1.75}
                    aria-hidden="true"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </button>

                <span className="sr-only" aria-live="polite">
                  Showing categories {firstIndex} to {lastIndex} of {categories.length}
                </span>
              </div>
            )}
          </header>

          {visible.map((category, index) => (
            <Link
              key={`${currentPage}-${category.id}`}
              to={`/shop?category=${category.slug}`}
              className={[
                "category-gallery__item",
                `category-gallery__item--${index + 1}`,
                direction !== "initial" && `category-gallery__item--enter-${direction}`,
              ]
                .filter(Boolean)
                .join(" ")}
              aria-label={`Browse the ${category.name} collection`}
            >
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
        {pageCount > 1 && (
          <div
            ref={pagerRef}
            className={[
              "category-gallery__pager",
              "category-gallery__pager--under-view-all",
              "page-count",
              !pagerVisible && "category-gallery__pager--hidden",
            ]
              .filter(Boolean)
              .join(" ")}
          >
            {pageCount > 2 && (
              <span className="category-gallery__pager-count" aria-live="polite">
                {String(currentPage + 1).padStart(2, "0")} / {String(pageCount).padStart(2, "0")}
              </span>
            )}

            <span className="sr-only" aria-live="polite">
              Showing categories {firstIndex} to {lastIndex} of {categories.length}
            </span>
          </div>
        )}
      </div>
    </section>
  );
}
