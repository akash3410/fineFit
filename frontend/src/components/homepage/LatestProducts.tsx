/* ────────────────────────────────────────────────────────────────────────────
 * LatestProducts — editorial "New Arrivals" grid.
 *
 * Reference design: a slim tab row ("New Arrivals" + a View all link), one
 * descriptive line, then a tight 4-up grid of tall portrait images. Product
 * name and price sit under the image at the left, with a small "New Season"
 * tag at the right. Hovering a card reveals quick actions — Add to cart,
 * Order now and a circular details button — over the photograph.
 *
 * Data comes from GET /api/v1/products/?ordering=-created_at with real
 * server-side pagination (numbered pages, not append-style loading). Cards
 * reveal with a staggered fade-up the first time the section scrolls into
 * view, and re-animate on every page change.
 *
 * Note: a size/variant must be chosen before an item can enter the bag, so the
 * quick actions route into the product page where the shopper picks one and
 * adds it to the (server-backed) cart.
 * ────────────────────────────────────────────────────────────────────────── */

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { getProducts, getProduct } from "../../api/catalog";
import type { PaginatedResponse, ProductListItem } from "../../types/catalog";
import { formatBDT } from "../../utils/currency";
import { useCart } from "../../features/cart/CartContext";
import { useToast } from "../../features/toast/ToastContext";

const PAGE_SIZE = 8;
const NEW_PRODUCT_DAYS = 30;

function isNew(createdAt: string) {
  const created = new Date(createdAt).getTime();
  const cutoff = Date.now() - NEW_PRODUCT_DAYS * 24 * 60 * 60 * 1000;
  return created >= cutoff;
}

/** Page numbers with a single gap on each side of the current page. */
function buildPages(current: number, total: number): (number | "gap")[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages: (number | "gap")[] = [1];
  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);
  if (start > 2) pages.push("gap");
  for (let p = start; p <= end; p += 1) pages.push(p);
  if (end < total - 1) pages.push("gap");
  pages.push(total);
  return pages;
}

function ChevronIcon({ direction }: { direction: "left" | "right" }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={direction === "left" ? "M15 5l-7 7 7 7" : "M9 5l7 7-7 7"} />
    </svg>
  );
}

function DetailsIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2.5 12s3.5-6.5 9.5-6.5S21.5 12 21.5 12s-3.5 6.5-9.5 6.5S2.5 12 2.5 12Z" />
      <circle cx="12" cy="12" r="2.75" />
    </svg>
  );
}

interface LatestProductsProps {
  className?: string;
}

export function LatestProducts({ className }: LatestProductsProps) {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [revealed, setRevealed] = useState(() => typeof IntersectionObserver === "undefined");
  const sectionRef = useRef<HTMLElement | null>(null);
  const { addItem, isMutating } = useCart()
  const { showToast } = useToast()
  const [addingToCart, setAddingToCart] = useState<Set<number>>(new Set())

  /* ── Data ── */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = (await getProducts({
          page: String(page),
          page_size: String(PAGE_SIZE),
          ordering: "-created_at",
        })) as PaginatedResponse<ProductListItem>;
        if (cancelled) return;
        setProducts(data.results);
        setCount(data.count);
        setError(null);
      } catch {
        if (!cancelled) setError("Failed to load products");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [page, reloadKey]);

  /* ── Scroll reveal ── */
  useEffect(() => {
    const node = sectionRef.current;
    if (!node || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setRevealed(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1, rootMargin: "0px 0px -80px 0px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  const changePage = (next: number) => {
    if (next === page || next < 1 || next > totalPages) return;
    setLoading(true);
    setPage(next);
    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    sectionRef.current?.scrollIntoView({
      behavior: prefersReduced ? "auto" : "smooth",
      block: "start",
    });
  };

  const sectionClass = ["latest-products", revealed ? "latest-products--visible" : "", className]
    .filter(Boolean)
    .join(" ");

  const handleAddToCart = async (product: ProductListItem) => {
    if (addingToCart.has(product.id)) return
    const newAdding = new Set(addingToCart)
    newAdding.add(product.id)
    setAddingToCart(newAdding)

    try {
      const detail = await getProduct(product.slug)
      const variant = (detail.variants || []).find((v) => v.is_active)
      if (!variant) {
        showToast('This product has no available options', 'error')
        return
      }
      const result = await addItem(variant.id, 1)
      if (result.ok) {
        showToast(`${product.title} added to cart`, 'success')
      } else {
        showToast(result.error, 'error')
      }
    } catch {
      showToast('Failed to add to cart', 'error')
    } finally {
      const newAdding = new Set(addingToCart)
      newAdding.delete(product.id)
      setAddingToCart(newAdding)
    }
  }

  const handleOrderNow = (product: ProductListItem) => {
    window.location.href = `/product/${product.slug}?intent=buy`
  }

  return (
    <section className={sectionClass} ref={sectionRef} aria-labelledby="latest-products-title">
      <div className="latest-products__wrap">
        <div className="latest-products__toolbar">
          <h2 id="latest-products-title" className="latest-products__tab">
            New Arrivals
          </h2>
          <Link to="/shop" className="latest-products__view-all">
            View all
            <svg
              className="latest-products__view-all-arrow"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.6}
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M5 12h14M13 6l6 6-6 6" />
            </svg>
          </Link>
        </div>

        <p className="latest-products__description">
          The latest pieces from our consciously crafted collection — added as they land in the
          studio.
        </p>

        {error ? (
          <div className="latest-products__empty">
            <p className="latest-products__empty-message">{error}</p>
            <button
              type="button"
              className="latest-products__retry"
              onClick={() => {
                setLoading(true);
                setReloadKey((key) => key + 1);
              }}
            >
              Try again
            </button>
          </div>
        ) : products.length === 0 && loading ? (
          <div className="latest-products__grid latest-products__grid--loading" aria-hidden="true">
            {Array.from({ length: PAGE_SIZE }, (_, i) => (
              <div key={i} className="latest-products__item">
                <div className="latest-products__skeleton-media" />
                <div className="latest-products__skeleton-line" />
                <div className="latest-products__skeleton-line latest-products__skeleton-line--short" />
              </div>
            ))}
          </div>
        ) : products.length === 0 ? (
          <div className="latest-products__empty">
            <p className="latest-products__empty-message">
              No products available yet. Check back soon.
            </p>
          </div>
        ) : (
          <div
            className={[
              "latest-products__grid",
              loading ? "latest-products__grid--busy" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            aria-busy={loading}
          >
            {products.map((product, index) => {
              const img = product.primary_image;
              const onSale =
                product.discount_price != null &&
                product.discount_price !== "" &&
                parseFloat(product.discount_price) < parseFloat(product.base_price);
              const salePrice = onSale ? product.discount_price : null;
              const inStock = (product.stock ?? 0) > 0;
              const tag = !inStock
                ? "Sold out"
                : onSale
                  ? "Sale"
                  : isNew(product.created_at)
                    ? "New Season"
                    : null;
              const detailPath = `/product/${product.slug}`;

              return (
                <article
                  key={`${page}-${product.id}`}
                  className="latest-products__item"
                  style={{ "--reveal-index": index } as CSSProperties}
                >
                  <div className="latest-products__media">
                    <Link
                      to={detailPath}
                      className="latest-products__image-link"
                      aria-label={`View ${product.title} details`}
                    >
                      {img?.image ? (
                        <img
                          src={img.image}
                          alt={img.alt_text || product.title}
                          className="latest-products__image"
                          loading="lazy"
                          decoding="async"
                        />
                      ) : (
                        <span className="latest-products__image-fallback" aria-hidden="true" />
                      )}
                    </Link>

                    <Link
                      to={detailPath}
                      className="latest-products__details-icon"
                      aria-label={`View ${product.title} details`}
                    >
                      <DetailsIcon />
                    </Link>

                    <div className="latest-products__actions">
                      <button
                        type="button"
                        onClick={() => handleAddToCart(product)}
                        disabled={addingToCart.has(product.id) || isMutating || !inStock}
                        className="latest-products__action latest-products__action--primary"
                        aria-label={inStock ? `Add ${product.title} to cart` : `View ${product.title} options`}
                      >
                        {addingToCart.has(product.id) ? 'Adding…' : inStock ? 'Add to cart' : 'View options'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleOrderNow(product)}
                        disabled={isMutating}
                        className="latest-products__action latest-products__action--ghost"
                        aria-label={`Order ${product.title} now`}
                      >
                        Order now
                      </button>
                    </div>
                  </div>

                  <div className="latest-products__meta">
                    <div className="latest-products__info">
                      <Link to={detailPath} className="latest-products__name">
                        {product.title}
                      </Link>
                      <p className="latest-products__price">
                        {salePrice ? (
                          <>
                            {formatBDT(salePrice)}
                            <span className="latest-products__price-original">
                              {formatBDT(product.base_price)}
                            </span>
                          </>
                        ) : (
                          formatBDT(product.base_price)
                        )}
                      </p>
                    </div>
                    {tag && <span className="latest-products__tag">{tag}</span>}
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {totalPages > 1 && (
          <nav className="latest-products__pagination" aria-label="Product pages">
            <button
              type="button"
              className="latest-products__page latest-products__page--arrow"
              onClick={() => changePage(page - 1)}
              disabled={page === 1 || loading}
              aria-label="Previous page"
            >
              <ChevronIcon direction="left" />
            </button>

            {buildPages(page, totalPages).map((entry, i) =>
              entry === "gap" ? (
                <span key={`gap-${i}`} className="latest-products__page-gap" aria-hidden="true">
                  …
                </span>
              ) : (
                <button
                  key={entry}
                  type="button"
                  className="latest-products__page"
                  onClick={() => changePage(entry)}
                  aria-current={entry === page ? "page" : undefined}
                  disabled={loading}
                >
                  {entry}
                </button>
              ),
            )}

            <button
              type="button"
              className="latest-products__page latest-products__page--arrow"
              onClick={() => changePage(page + 1)}
              disabled={page === totalPages || loading}
              aria-label="Next page"
            >
              <ChevronIcon direction="right" />
            </button>
          </nav>
        )}
      </div>
    </section>
  );
}
