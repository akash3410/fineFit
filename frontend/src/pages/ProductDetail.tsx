import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams, useNavigate } from 'react-router-dom'
import { getProduct } from '../api/catalog'
import { MAX_QUANTITY_PER_ITEM } from '../api/cart'
import { useCart } from '../features/cart/CartContext'
import type { ProductDetail } from '../types/catalog'
import { normalizeImageUrl } from '../utils/image'
import { formatBDT } from '../utils/currency'

const STOCK_LABELS: Record<string, string> = {
  IN_STOCK: 'In stock',
  LOW_STOCK: 'Low stock',
  OUT_OF_STOCK: 'Sold out',
}

export function ProductDetail() {
  const { slug } = useParams<{ slug: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { addItem, isMutating } = useCart()
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedVariant, setSelectedVariant] = useState<string | null>(null)
  const [quantity, setQuantity] = useState(1)
  const [feedback, setFeedback] = useState<
    { type: 'success'; message: string } | { type: 'error'; message: string } | null
  >(null)

  const intent = searchParams.get('intent')
  const buyIntentHandled = useRef(false)
  const cartIntentHandled = useRef(false)

  useEffect(() => {
    async function load() {
      if (!slug) return
      try {
        const data = await getProduct(slug)
        setProduct(data)
        const active = (data.variants || []).find((v) => v.is_active)
        if (active) setSelectedVariant(active.id)
      } catch {
        setError('Failed to load product')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [slug])

  const images = product?.images || []
  const hero = images.find((img) => img.is_primary) ?? images[0]
  const variants = (product?.variants || []).filter((v) => v.is_active)
  const activeVariant = variants.find((v) => v.id === selectedVariant)
  const price = activeVariant?.effective_price || product?.base_price
  const soldOut = activeVariant?.is_in_stock === false
  const canAddToCart = Boolean(activeVariant) && !soldOut && !isMutating

  const selectVariant = (variantId: string) => {
    setSelectedVariant(variantId)
    setQuantity(1)
    setFeedback(null)
  }

  const handleBuyNow = useCallback(async () => {
    if (!activeVariant) return
    setFeedback(null)
    const result = await addItem(activeVariant.id, quantity)
    if (result.ok) {
      navigate('/cart')
    } else {
      setFeedback({ type: 'error', message: result.error })
    }
  }, [activeVariant, quantity, addItem, navigate])

  const handleAddToCart = useCallback(async () => {
    if (!activeVariant) return
    setFeedback(null)
    const result = await addItem(activeVariant.id, quantity)
    if (result.ok) {
      setFeedback({
        type: 'success',
        message: `${quantity} × ${[activeVariant.size, activeVariant.color_name].filter(Boolean).join(' / ') || activeVariant.sku} added to your cart.`,
      })
    } else {
      setFeedback({ type: 'error', message: result.error })
    }
  }, [activeVariant, quantity, addItem])

  useEffect(() => {
    if (intent === 'buy' && product && selectedVariant && !isMutating && !buyIntentHandled.current) {
      buyIntentHandled.current = true
      void handleBuyNow()
    }
    if (intent === 'cart' && product && selectedVariant && !isMutating && !cartIntentHandled.current) {
      cartIntentHandled.current = true
      void handleAddToCart()
    }
    // Reset when intent changes
    if (intent !== 'buy') {
      buyIntentHandled.current = false
    }
    if (intent !== 'cart') {
      cartIntentHandled.current = false
    }
  }, [intent, product, selectedVariant, isMutating, handleBuyNow, handleAddToCart])

  if (loading) return <div className="mx-auto max-w-7xl px-4 py-10 text-sm text-stone-600">Loading...</div>
  if (error || !product) return <div className="mx-auto max-w-7xl px-4 py-10 text-sm text-red-600">{error || 'Product not found'}</div>

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <div className="mb-6"><Link to="/shop" className="text-sm text-stone-600 hover:text-stone-900">← Back to shop</Link></div>
      <div className="grid gap-10 lg:grid-cols-2">
        <div>
          {hero ? <div className="aspect-[4/5] w-full overflow-hidden rounded-lg bg-stone-100"><img src={normalizeImageUrl(hero.image) ?? undefined} alt={hero.alt_text||product.title} className="h-full w-full object-cover" /></div> : <div className="flex aspect-[4/5] items-center justify-center rounded-lg bg-stone-100 text-sm text-stone-400">No image</div>}
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
                  <button key={variant.id} onClick={() => selectVariant(variant.id)} className={selectedVariant===variant.id ? "rounded-md border border-stone-900 bg-stone-900 px-3 py-2 text-sm text-white" : "rounded-md border border-stone-300 px-3 py-2 text-sm hover:bg-stone-50"}>
                    {[variant.size, variant.color_name].filter(Boolean).join(' / ') || variant.sku}
                  </button>
                ))}
              </div>
              {activeVariant && <p className="mt-3 text-sm text-stone-600">SKU: {activeVariant.sku}</p>}
            </div>
          )}

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <p className={`text-sm ${soldOut ? 'text-red-600' : 'text-stone-600'}`}>
              {variants.length === 0
                ? 'Contact for availability'
                : STOCK_LABELS[activeVariant?.stock_status ?? ''] ?? 'Available'}
            </p>
            {activeVariant?.stock_status === 'LOW_STOCK' && (
              <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs text-amber-800">Selling fast</span>
            )}
          </div>

          {activeVariant && (
            <div className="mt-6 flex flex-wrap items-center gap-4">
              <div className="inline-flex items-center rounded-md border border-stone-300">
                <button
                  type="button"
                  onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                  disabled={quantity <= 1 || isMutating}
                  className="flex h-11 w-11 items-center justify-center text-lg text-stone-700 transition-colors hover:bg-stone-50 disabled:cursor-not-allowed disabled:text-stone-300"
                  aria-label="Decrease quantity"
                >
                  −
                </button>
                <span className="w-10 text-center text-sm tabular-nums" aria-live="polite">
                  {quantity}
                </span>
                <button
                  type="button"
                  onClick={() => setQuantity((q) => Math.min(MAX_QUANTITY_PER_ITEM, q + 1))}
                  disabled={quantity >= MAX_QUANTITY_PER_ITEM || isMutating}
                  className="flex h-11 w-11 items-center justify-center text-lg text-stone-700 transition-colors hover:bg-stone-50 disabled:cursor-not-allowed disabled:text-stone-300"
                  aria-label="Increase quantity"
                >
                  +
                </button>
              </div>
              <button
                type="button"
                onClick={handleBuyNow}
                disabled={!canAddToCart}
                className="min-w-[220px] rounded-md bg-stone-900 px-6 py-3 text-xs font-medium uppercase tracking-widest text-white transition-colors hover:bg-stone-700 disabled:cursor-not-allowed disabled:bg-stone-300"
              >
                {isMutating ? 'Adding…' : soldOut ? 'Sold out' : 'Order now'}
              </button>
              <Link
                to="/cart"
                className="min-w-[220px] rounded-md border border-stone-900 px-6 py-3 text-xs font-medium uppercase tracking-widest text-stone-900 transition-colors hover:bg-stone-100"
              >
                View Cart
              </Link>
            </div>
          )}

          {feedback && (
            <div
              role={feedback.type === 'error' ? 'alert' : 'status'}
              className={`mt-4 rounded-md border px-4 py-3 text-sm ${
                feedback.type === 'success'
                  ? 'border-green-200 bg-green-50 text-green-800'
                  : 'border-red-200 bg-red-50 text-red-700'
              }`}
            >
              {feedback.message}
              {feedback.type === 'success' && (
                <Link to="/cart" className="ml-2 font-medium underline underline-offset-4">
                  View Cart
                </Link>
              )}
            </div>
          )}

          {variants.length === 0 && (
            <p className="mt-4 text-sm text-stone-500">
              This piece has no purchasable options yet, so it cannot be added to your bag.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}