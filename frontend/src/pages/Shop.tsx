import { normalizeImageUrl } from '../utils/image'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getCategories, getProducts } from '../api/catalog'
import type { Category, ProductListItem } from '../types/catalog'
import { formatBDT } from '../utils/currency'

export function Shop() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [categories, setCategories] = useState<Category[]>([])
  const [products, setProducts] = useState<ProductListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const category = searchParams.get('category') || ''
  const subcategory = searchParams.get('subcategory') || ''
  const ordering = searchParams.get('ordering') || ''

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [cats, prods] = await Promise.all([getCategories(), getProducts({ ...(category ? { category } : {}), ...(subcategory ? { subcategory } : {}), ...(ordering ? { ordering } : {}), page_size: '24' })])
        const catList = Array.isArray(cats) ? (cats as any).results || cats : (cats as any).results || []
        const prodList = (prods as any).results || []
        setCategories(catList)
        setProducts(prodList)
      } catch {
        setError('Failed to load products')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [category, subcategory, ordering])

  const updateFilter = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams)
    if (value) params.set(key, value)
    else params.delete(key)
    setSearchParams(params)
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Shop</h1>
        <p className="mt-2 text-stone-600">Browse the collection</p>
      </div>
      <div className="flex flex-col gap-8 lg:flex-row">
        <aside className="w-full lg:w-64">
          <div className="mb-6">
            <h2 className="mb-3 text-sm font-medium">Category</h2>
            <div className="flex flex-col gap-2 text-sm">
              <button onClick={() => updateFilter('category', '')} className={!category ? 'text-left font-medium' : 'text-left text-stone-600 hover:text-stone-900'}>All</button>
              {categories.map((cat) => (<button key={cat.id} onClick={() => updateFilter('category', cat.slug)} className={category === cat.slug ? 'text-left font-medium' : 'text-left text-stone-600 hover:text-stone-900'}>{cat.name}</button>))}
            </div>
          </div>
          <div>
            <h2 className="mb-3 text-sm font-medium">Sort by</h2>
            <select value={ordering} onChange={(e) => updateFilter('ordering', e.target.value)} className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm">
              <option value="">Newest</option>
              <option value="base_price">Price: Low to High</option>
              <option value="-base_price">Price: High to Low</option>
              <option value="title">Name</option>
            </select>
          </div>
        </aside>
        <section className="flex-1">
          {loading && <p className="text-sm text-stone-600">Loading...</p>}
          {error && <p className="text-sm text-red-600">{error}</p>}
          {!loading && !error && products.length === 0 && <p className="text-sm text-stone-600">No products found.</p>}
          {!loading && !error && products.length > 0 && (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {products.map((product) => {
                const img = product.primary_image?.image
                const inStock = (product.stock ?? 0) > 0
                const detailPath = `/product/${product.slug}`
                return (
                  <article key={product.id} className="group">
                    <Link to={detailPath} className="block" aria-label={`View ${product.title} details`}>
                      <div className="aspect-[4/5] w-full overflow-hidden rounded-lg bg-stone-100 relative">
                        {img ? <img src={normalizeImageUrl(img) ?? undefined} alt={product.primary_image?.alt_text||product.title} className="h-full w-full object-cover transition-transform group-hover:scale-105" /> : <div className="flex h-full items-center justify-center text-sm text-stone-400">No image</div>}
                        <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex items-end p-3 gap-2">
                          <Link
                            to={`${detailPath}?intent=cart`}
                            className="flex-1 text-center rounded-md bg-white/90 backdrop-blur-sm px-3 py-2 text-xs font-medium uppercase tracking-widest text-stone-900 transition-colors hover:bg-white"
                            aria-label={inStock ? `Add ${product.title} to cart` : `View ${product.title} options`}
                          >
                            {inStock ? 'Add to cart' : 'View options'}
                          </Link>
                          <Link
                            to={`${detailPath}?intent=buy`}
                            className="flex-1 text-center rounded-md border border-white/30 bg-transparent px-3 py-2 text-xs font-medium uppercase tracking-widest text-white transition-colors hover:bg-white/10"
                            aria-label={`Order ${product.title} now`}
                          >
                            Order now
                          </Link>
                        </div>
                      </div>
                    </Link>
                    <div className="mt-3"><h3 className="text-sm font-medium">{product.title}</h3><p className="text-sm text-stone-600">{formatBDT(product.base_price)}</p></div>
                  </article>
                )
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}