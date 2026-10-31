import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { FashionHeroSlider } from '../components/FashionHeroSlider'
import { BrandPromiseGateway } from '../components/BrandPromiseGateway'
import { getCategories, getProducts } from '../api/catalog'
import type { Category, ProductListItem } from '../types/catalog'
import { formatBDT } from '../utils/currency'

/* ────────────────────────────────────────────────────────────────────────────
 * Home — Gucci-inspired luxury homepage
 *
 * Structure:
 *   1. Full-viewport cinematic campaign sequence (see FashionHeroSlider)
 *   2. API-driven category pills
 *   3. API-driven featured products grid
 * ──────────────────────────────────────────────────────────────────────── */

export function Home() {
  const [categories, setCategories] = useState<Category[]>([])
  const [products, setProducts] = useState<ProductListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      try {
        const [cats, prods] = await Promise.all([getCategories(), getProducts({ page_size: '8' })])
        const catList = Array.isArray(cats) ? (cats as any).results || cats : (cats as any).results || []
        const prodList = (prods as any).results || []
        setCategories(catList)
        setProducts(prodList)
      } catch (_e) {
        setError('Failed to load catalog data')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  return (
    <div>
      {/* ── Hero — cinematic campaign sequence ── */}
      <FashionHeroSlider />

      {/* ── Brand Promise Gateway ── */}
      <BrandPromiseGateway />

      {/* ── Categories Section ── */}
      {categories.length > 0 && (
        <section className="bg-white py-16 sm:py-20">
          <div className="mx-auto max-w-7xl px-6 lg:px-10">
            <h2 className="mb-8 text-center text-2xl font-semibold tracking-tight text-stone-900 sm:text-3xl font-serif">
              Shop by Category
            </h2>
            <div className="flex flex-wrap justify-center gap-3">
              {categories.map((cat) => (
                <Link
                  key={cat.id}
                  to={"/shop?category=" + cat.slug}
                  className="rounded-full border border-stone-300 px-6 py-2.5 text-sm text-stone-700 hover:bg-stone-900 hover:text-white hover:border-stone-900 transition-all duration-200"
                >
                  {cat.name}
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── Featured Products Section ── */}
      <section className="bg-stone-50 py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-6 lg:px-10">
          <div className="mb-10 flex items-end justify-between">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight text-stone-900 sm:text-3xl font-serif">
                Featured Pieces
              </h2>
              <p className="mt-2 text-sm text-stone-500">
                Curated selections from our latest collection
              </p>
            </div>
            <Link
              to="/shop"
              className="hidden sm:inline-flex items-center gap-1 text-sm text-stone-600 hover:text-stone-900 transition-colors"
            >
              View all
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
            </Link>
          </div>

          {loading && (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="animate-pulse">
                  <div className="aspect-[3/4] w-full rounded-lg bg-stone-200" />
                  <div className="mt-4 space-y-2">
                    <div className="h-4 w-3/4 rounded bg-stone-200" />
                    <div className="h-4 w-1/3 rounded bg-stone-200" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {error && (
            <div className="py-16 text-center">
              <p className="text-sm text-red-600">{error}</p>
              <button
                onClick={() => window.location.reload()}
                className="mt-3 text-sm text-stone-600 hover:text-stone-900 underline underline-offset-4"
              >
                Try again
              </button>
            </div>
          )}

          {!loading && !error && products.length === 0 && (
            <p className="py-16 text-center text-sm text-stone-500">
              No products available yet. Check back soon.
            </p>
          )}

          {!loading && !error && products.length > 0 && (
            <div className="grid grid-cols-1 gap-x-6 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
              {products.map((product) => {
                const img = product.primary_image?.image
                return (
                  <Link
                    key={product.id}
                    to={"/product/" + product.slug}
                    className="group"
                  >
                    <div className="aspect-[3/4] w-full overflow-hidden rounded-lg bg-stone-100">
                      {img ? (
                        <img
                          src={img}
                          alt={product.primary_image?.alt_text || product.title}
                          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                          loading="lazy"
                        />
                      ) : (
                        <div className="flex h-full items-center justify-center text-sm text-stone-400">
                          No image
                        </div>
                      )}
                    </div>
                    <div className="mt-4">
                      <h3 className="text-sm font-medium text-stone-900 group-hover:text-stone-600 transition-colors">
                        {product.title}
                      </h3>
                      <p className="mt-1 text-sm text-stone-500">
                        {formatBDT(product.base_price)}
                      </p>
                    </div>
                  </Link>
                )
              })}
            </div>
          )}

          {/* Mobile "View all" link */}
          <div className="mt-10 text-center sm:hidden">
            <Link
              to="/shop"
              className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-stone-900 transition-colors"
            >
              View all products
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
