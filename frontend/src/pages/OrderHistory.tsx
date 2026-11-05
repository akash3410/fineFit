import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/http'
import { listOrders } from '../api/orders'
import type { Order } from '../types/order'
import { formatBDT } from '../utils/currency'
import { ORDER_STATUS_LABELS, formatOrderDate } from '../utils/orderStatus'

/* ────────────────────────────────────────────────────────────────────────────
 * OrderHistory — "My orders".
 *
 * The list comes from GET /orders/, which the backend scopes to the signed-in
 * customer or the guest session that placed the orders. Each row links to the
 * tracking page for that order.
 * ──────────────────────────────────────────────────────────────────────── */

export function OrderHistory() {
  const [orders, setOrders] = useState<Order[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    listOrders()
      .then((data) => {
        if (!active) return
        setOrders(data.results)
        setError(null)
      })
      .catch((err: unknown) => {
        if (!active) return
        setError(
          err instanceof ApiError
            ? err.message
            : 'We could not load your orders right now. Please try again shortly.',
        )
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
        Your account
      </p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">My orders</h1>
      <p className="mt-3 text-sm leading-relaxed text-stone-600">
        Track delivery and request a return from any delivered order.
      </p>

      {isLoading && (
        <p className="mt-10 text-sm text-stone-600">Loading your orders…</p>
      )}

      {!isLoading && error && (
        <p className="mt-10 text-sm text-red-600">{error}</p>
      )}

      {!isLoading && !error && orders.length === 0 && (
        <div className="mt-10 rounded-lg border border-stone-200 px-5 py-10 text-center">
          <p className="text-sm text-stone-600">
            You have not placed an order with this browser session yet.
          </p>
          <Link
            to="/shop"
            className="mt-6 inline-flex rounded-md bg-stone-900 px-6 py-3 text-xs font-medium uppercase tracking-widest text-white transition-colors hover:bg-stone-700"
          >
            Start shopping
          </Link>
        </div>
      )}

      {orders.length > 0 && (
        <ul className="mt-10 divide-y divide-stone-200 border-y border-stone-200">
          {orders.map((order) => (
            <li key={order.id} className="py-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <p className="font-mono text-sm font-medium">
                    {order.order_number}
                  </p>
                  <p className="mt-1 text-xs text-stone-500">
                    {formatOrderDate(order.created_at)} · {order.total_quantity}{' '}
                    {order.total_quantity === 1 ? 'item' : 'items'} ·{' '}
                    {formatBDT(order.total)}
                  </p>
                </div>
                <div className="flex items-center gap-5">
                  <span className="text-xs font-medium text-stone-700">
                    {ORDER_STATUS_LABELS[order.status]}
                  </span>
                  <Link
                    to={`/order/${order.order_number}`}
                    className="text-xs font-medium uppercase tracking-widest underline-offset-4 hover:underline"
                  >
                    Track
                  </Link>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
