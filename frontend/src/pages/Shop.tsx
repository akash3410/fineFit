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
  const ordering = searchParams.get('ordering') || ''

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError(null)
      try {
        const [cats, prods] = await Promise.all([getCategories(), getProducts({ ...(category ? { category } : {}), ...(ordering ? { ordering } : {}), page_size: '24' })])
        const catList = Array.isArray(cats) ? (cats as any).results || cats : (cats as any).results || []
        const prodList = (prods as any).results || []
        setCategories(catList)
        setProducts(prodList)
      } catch (e) {
        setError('Failed to load products')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [category, ordering])

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
                return (
                  <Link key={product.id} to={"/product/"+product.slug} className="group">
                    <div className="aspect-[4/5] w-full overflow-hidden rounded-lg bg-stone-100">
                      {img ? <img src={img} alt={product.primary_image?.alt_text||product.title} className="h-full w-full object-cover transition-transform group-hover:scale-105" /> : <div className="flex h-full items-center justify-center text-sm text-stone-400">No image</div>}
                    </div>
                    <div className="mt-3"><h3 className="text-sm font-medium">{product.title}</h3><p className="text-sm text-stone-600">{formatBDT(product.base_price)}</p></div>
                  </Link>
                )
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
