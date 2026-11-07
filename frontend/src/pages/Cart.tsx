import { Link } from 'react-router-dom'
import { MAX_QUANTITY_PER_ITEM } from '../api/cart'
import { useCart } from '../features/cart/CartContext'
import type { CartItem } from '../types/cart'
import { formatBDT } from '../utils/currency'

/* ────────────────────────────────────────────────────────────────────────────
 * Cart — the shopping bag.
 *
 * Every figure shown here (unit price, line total, subtotal, availability)
 * comes from the backend cart response; the page only renders it and sends
 * variant/quantity intent back to the API.
 * ──────────────────────────────────────────────────────────────────────────── */

function maxSelectable(item: CartItem): number {
  const stockCap = item.available_quantity > 0 ? item.available_quantity : MAX_QUANTITY_PER_ITEM
  return Math.min(MAX_QUANTITY_PER_ITEM, stockCap)
}

function QuantityStepper({ item }: { item: CartItem }) {
  const { updateQuantity, isMutating } = useCart()
  const cap = maxSelectable(item)

  return (
    <div className="inline-flex items-center rounded-md border border-stone-300">
      <button
        type="button"
        onClick={() => void updateQuantity(item.id, item.quantity - 1)}
        disabled={item.quantity <= 1 || isMutating}
        className="flex h-9 w-9 items-center justify-center text-lg text-stone-700 transition-colors hover:bg-stone-50 disabled:cursor-not-allowed disabled:text-stone-300"
        aria-label={`Decrease quantity of ${item.variant.product_title}`}
      >
        −
      </button>
      <span className="w-9 text-center text-sm tabular-nums" aria-live="polite">
        {item.quantity}
      </span>
      <button
        type="button"
        onClick={() => void updateQuantity(item.id, item.quantity + 1)}
        disabled={item.quantity >= cap || isMutating}
        className="flex h-9 w-9 items-center justify-center text-lg text-stone-700 transition-colors hover:bg-stone-50 disabled:cursor-not-allowed disabled:text-stone-300"
        aria-label={`Increase quantity of ${item.variant.product_title}`}
      >
        +
      </button>
    </div>
  )
}

function CartLine({ item }: { item: CartItem }) {
  const { removeItem, isMutating } = useCart()
  const variantLabel =
    [item.variant.size, item.variant.color_name].filter(Boolean).join(' / ') || item.variant.sku

  return (
    <li className="flex gap-4 border-b border-stone-200 py-5">
      <Link to={`/product/${item.variant.product_slug}`} className="shrink-0">
        <div className="h-28 w-24 overflow-hidden rounded-md bg-stone-100">
          {item.image ? (
            <img
              src={item.image}
              alt={item.variant.product_title}
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-stone-400">
              No image
            </div>
          )}
        </div>
      </Link>

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <Link
              to={`/product/${item.variant.product_slug}`}
              className="block truncate text-sm font-medium hover:text-stone-600"
            >
              {item.variant.product_title}
            </Link>
            <p className="mt-1 text-xs text-stone-600">{variantLabel}</p>
            <p className="mt-1 text-xs text-stone-400">SKU: {item.variant.sku}</p>
          </div>
          <p className="whitespace-nowrap text-sm font-medium">
            {item.line_total ? formatBDT(item.line_total) : '—'}
          </p>
        </div>

        {!item.has_sufficient_stock && (
          <p className="text-xs text-red-600">
            {item.available_quantity === 0
              ? 'This item is currently out of stock.'
              : `Only ${item.available_quantity} left in stock — reduce the quantity to continue.`}
          </p>
        )}

        <div className="mt-auto flex flex-wrap items-center gap-4">
          <QuantityStepper item={item} />
          <span className="text-xs text-stone-500">
            {item.unit_price ? `${formatBDT(item.unit_price)} each` : 'Price unavailable'}
          </span>
          <button
            type="button"
            onClick={() => void removeItem(item.id)}
            disabled={isMutating}
            className="ml-auto text-xs text-stone-500 underline-offset-4 transition-colors hover:text-stone-900 hover:underline disabled:cursor-not-allowed disabled:text-stone-300"
          >
            Remove
          </button>
        </div>
      </div>
    </li>
  )
}

export function Cart() {
  const {
    items,
    totalQuantity,
    subtotal,
    hasStockConflicts,
    isLoading,
    isMutating,
    error,
    clear,
    refresh,
    dismissError,
  } = useCart()

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10">
        <p className="text-sm text-stone-600">Loading your cart…</p>
      </div>
    )
  }

  // A load failure leaves no usable cart state: offer a retry instead of an
  // empty-cart screen that would misrepresent the shopper's cart.
  if (error && items.length === 0) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10">
        <h1 className="text-3xl font-semibold tracking-tight">Your Cart</h1>
        <p className="mt-4 text-sm text-red-600">{error}</p>
        <button
          type="button"
          onClick={() => void refresh()}
          className="mt-6 rounded-md border border-stone-900 px-5 py-2.5 text-sm font-medium transition-colors hover:bg-stone-900 hover:text-white"
        >
          View Cart
        </button>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10">
        <h1 className="text-3xl font-semibold tracking-tight">Your Cart</h1>
        <div className="mt-10 rounded-lg border border-dashed border-stone-300 px-6 py-16 text-center">
          <p className="text-sm text-stone-600">Your cart is empty.</p>
          <Link
            to="/shop"
            className="mt-6 inline-flex rounded-md bg-stone-900 px-6 py-3 text-xs font-medium uppercase tracking-widest text-white transition-colors hover:bg-stone-700"
          >
            Continue shopping
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-10">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Your Cart</h1>
          <p className="mt-2 text-sm text-stone-600">
            {totalQuantity} {totalQuantity === 1 ? 'item' : 'items'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            if (window.confirm('Remove every item from your cart?')) void clear()
          }}
          disabled={isMutating}
          className="text-xs text-stone-500 underline-offset-4 transition-colors hover:text-stone-900 hover:underline disabled:cursor-not-allowed disabled:text-stone-300"
        >
          Remove all items
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="mt-6 flex items-start justify-between gap-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={dismissError}
            className="shrink-0 text-xs uppercase tracking-widest text-red-700 hover:text-red-900"
          >
            Dismiss
          </button>
        </div>
      )}

      {hasStockConflicts && (
        <div
          role="status"
          className="mt-6 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          Some items in your cart exceed the stock currently available. Adjust the
          quantities below to continue.
        </div>
      )}

      <div className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_340px]">
        <ul className="list-none">
          {items.map((item) => (
            <CartLine key={item.id} item={item} />
          ))}
        </ul>

        <aside className="h-fit rounded-lg border border-stone-200 p-6">
          <h2 className="text-sm font-medium uppercase tracking-widest">Order summary</h2>
          <p className="mt-1 text-xs text-stone-500">Review what you want to buy.</p>
          <dl className="mt-5 space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-stone-600">Subtotal</dt>
              <dd className="font-medium">{formatBDT(subtotal)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-stone-600">Items</dt>
              <dd>{totalQuantity}</dd>
            </div>
          </dl>
          {hasStockConflicts ? (
            <button
              type="button"
              disabled
              title="Reduce the quantities marked above to continue"
              className="mt-6 w-full cursor-not-allowed rounded-md bg-stone-300 px-6 py-3 text-xs font-medium uppercase tracking-widest text-white"
            >
              Proceed to checkout
            </button>
          ) : (
            <Link
              to="/checkout"
              className="mt-6 block w-full rounded-md bg-stone-900 px-6 py-3 text-center text-xs font-medium uppercase tracking-widest text-white transition-colors hover:bg-stone-700"
            >
              Proceed to checkout
            </Link>
          )}
          <p className="mt-3 text-xs leading-relaxed text-stone-500">
            Cash on delivery available — pay when your order arrives.
          </p>
          <Link
            to="/shop"
            className="mt-5 block text-center text-xs text-stone-600 underline-offset-4 hover:text-stone-900 hover:underline"
          >
            Continue shopping
          </Link>
        </aside>
      </div>
    </div>
  )
}
