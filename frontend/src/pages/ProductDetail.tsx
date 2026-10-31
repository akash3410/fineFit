import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getProduct } from '../api/catalog'
import type { ProductDetail } from '../types/catalog'
import { formatBDT } from '../utils/currency'

export function ProductDetail() {
  const { slug } = useParams<{ slug: string }>()
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedVariant, setSelectedVariant] = useState<string | null>(null)

  useEffect(() => {
    async function load() {
      if (!slug) return
      try {
        const data = await getProduct(slug)
        setProduct(data)
        const active = (data.variants || []).find((v: any) => v.is_active)
        if (active) setSelectedVariant(active.id)
      } catch (e) {
        setError('Failed to load product')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [slug])

  if (loading) return <div className="mx-auto max-w-7xl px-4 py-10 text-sm text-stone-600">Loading...</div>
  if (error || !product) return <div className="mx-auto max-w-7xl px-4 py-10 text-sm text-red-600">{error || 'Product not found'}</div>

  const images = product.images || []
  // Show the flagged primary image in the hero slot (list views use
  // ``primary_image``); fall back to the first image when none is flagged.
  const hero = images.find((img) => img.is_primary) ?? images[0]
  const variants = (product.variants || []).filter(v => v.is_active)
  const activeVariant = variants.find(v => v.id === selectedVariant)
  const price = activeVariant?.effective_price || product.base_price

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <div className="mb-6"><Link to="/shop" className="text-sm text-stone-600 hover:text-stone-900">← Back to shop</Link></div>
      <div className="grid gap-10 lg:grid-cols-2">
        <div>
          {hero ? <div className="aspect-[4/5] w-full overflow-hidden rounded-lg bg-stone-100"><img src={hero.image} alt={hero.alt_text||product.title} className="h-full w-full object-cover" /></div> : <div className="flex aspect-[4/5] items-center justify-center rounded-lg bg-stone-100 text-sm text-stone-400">No image</div>}
        </div>
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{product.title}</h1>
          <p className="mt-2 text-lg text-stone-600">{formatBDT(price)}</p>
          {product.description && <p className="mt-6 text-sm leading-relaxed text-stone-700">{product.description}</p>}
          {variants.length > 0 && (
            <div className="mt-8">
              <h2 className="mb-3 text-sm font-medium">Select variant</h2>
              <div className="flex flex-wrap gap-2">
                {variants.map((variant) => (
                  <button key={variant.id} onClick={() => setSelectedVariant(variant.id)} className={selectedVariant===variant.id ? "rounded-md border border-stone-900 bg-stone-900 px-3 py-2 text-sm text-white" : "rounded-md border border-stone-300 px-3 py-2 text-sm hover:bg-stone-50"}>
                    {[variant.size, variant.color_name].filter(Boolean).join(' / ') || variant.sku}
                  </button>
                ))}
              </div>
              {activeVariant && <p className="mt-3 text-sm text-stone-600">SKU: {activeVariant.sku}</p>}
            </div>
          )}
          <div className="mt-8"><p className="text-sm text-stone-600">{variants.length > 0 ? 'Available' : 'Contact for availability'}</p></div>
        </div>
      </div>
    </div>
  )
}
