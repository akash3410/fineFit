import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/http'
import { getOrder, requestReturn } from '../api/orders'
import type { Order, ReturnRequestStatus } from '../types/order'
import { formatBDT } from '../utils/currency'
import { ORDER_STATUS_LABELS, formatOrderDateTime } from '../utils/orderStatus'

/* ────────────────────────────────────────────────────────────────────────────
 * OrderConfirmation — the order tracking screen.
 *
 * Shows the placed order, its full status history, any return requests and the
 * per-line return form (only offered once the order is delivered). The order is
 * fetched by its customer-facing number; the API only returns it to the
 * customer or guest session that placed it.
 * ──────────────────────────────────────────────────────────────────────── */

const RETURN_STATUS_LABELS: Record<ReturnRequestStatus, string> = {
  REQUESTED: 'Awaiting review',
  APPROVED: 'Approved — units received',
  DECLINED: 'Declined',
}

export function OrderConfirmation() {
  const { orderNumber = '' } = useParams()
  const [order, setOrder] = useState<Order | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const [quantities, setQuantities] = useState<Record<number, number>>({})
  const [reason, setReason] = useState('')
  const [returnError, setReturnError] = useState<string | null>(null)
  const [returnNotice, setReturnNotice] = useState<string | null>(null)
  const [isSubmittingReturn, setIsSubmittingReturn] = useState(false)

  useEffect(() => {
    let active = true
    getOrder(orderNumber)
      .then((data) => {
        if (active) {
          setOrder(data)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (!active) return
        setError(
          err instanceof ApiError && err.status === 404
            ? 'We could not find that order for this browser session.'
            : 'We could not load your order right now. Please try again shortly.',
        )
      })
      .finally(() => {
        if (active) setIsLoading(false)
      })
    return () => {
      active = false
    }
  }, [orderNumber])

  function updateQuantity(itemId: number, value: number, max: number) {
    const clamped = Number.isFinite(value) ? Math.max(0, Math.min(max, value)) : 0
    setQuantities((previous) => ({ ...previous, [itemId]: clamped }))
  }

  async function handleReturnSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const items = Object.entries(quantities)
      .map(([itemId, quantity]) => ({ item_id: Number(itemId), quantity }))
      .filter((item) => item.quantity > 0)

    if (items.length === 0) {
      setReturnError('Choose at least one item and quantity to return.')
      return
    }

    setIsSubmittingReturn(true)
    setReturnError(null)
    setReturnNotice(null)
    try {
      await requestReturn(orderNumber, { reason, items })
      setOrder(await getOrder(orderNumber))
      setQuantities({})
      setReason('')
      setReturnNotice(
        'Your return request has been sent. We will review it and contact you with the next steps.',
      )
    } catch (err: unknown) {
      setReturnError(
        err instanceof ApiError
          ? err.message
          : 'We could not submit your return request. Please try again.',
      )
    } finally {
      setIsSubmittingReturn(false)
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <p className="text-sm text-stone-600">Loading your order…</p>
      </div>
    )
  }

  if (error || !order) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <h1 className="text-2xl font-semibold tracking-tight">Order</h1>
        <p className="mt-4 text-sm text-red-600">{error}</p>
        <Link
          to="/shop"
          className="mt-8 inline-flex rounded-md bg-stone-900 px-6 py-3 text-xs font-medium uppercase tracking-widest text-white transition-colors hover:bg-stone-700"
        >
          Continue shopping
        </Link>
      </div>
    )
  }

  const address = order.shipping_address
  const openRequest = order.return_requests.find(
    (returnRequest) => returnRequest.status === 'REQUESTED',
  )

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <p className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
        Thank you
      </p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">
        Your order is placed
      </h1>
      <p className="mt-3 text-sm leading-relaxed text-stone-600">
        We have received your order and will call you on{' '}
        <span className="font-medium text-stone-900">{order.customer_phone}</span>{' '}
        to confirm the delivery.
      </p>

      <div className="mt-8 rounded-lg border border-stone-200">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 px-5 py-4">
          <div>
            <p className="text-xs uppercase tracking-widest text-stone-500">
              Order number
            </p>
            <p className="mt-1 font-mono text-sm font-medium">
              {order.order_number}
            </p>
          </div>
          <div className="text-right">
            <p className="text-xs uppercase tracking-widest text-stone-500">
              Status
            </p>
            <p className="mt-1 text-sm font-medium">
              {ORDER_STATUS_LABELS[order.status]}
            </p>
          </div>
        </div>

        <ul className="divide-y divide-stone-200 px-5">
          {order.items.map((item) => (
            <li key={item.id} className="flex justify-between gap-4 py-4 text-sm">
              <span className="min-w-0">
                <span className="block font-medium">{item.product_title}</span>
                <span className="mt-0.5 block text-xs text-stone-500">
                  {[item.size, item.color_name].filter(Boolean).join(' / ')} ·{' '}
                  {item.variant_sku} × {item.quantity}
                </span>
                {item.returned_quantity > 0 && (
                  <span className="mt-1 block text-xs text-amber-700">
                    {item.returned_quantity} of {item.quantity} returned
                  </span>
                )}
              </span>
              <span className="whitespace-nowrap">{formatBDT(item.line_total)}</span>
            </li>
          ))}
        </ul>

        <dl className="space-y-3 border-t border-stone-200 px-5 py-4 text-sm">
          <div className="flex justify-between">
            <dt className="text-stone-600">Subtotal</dt>
            <dd>{formatBDT(order.subtotal)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-stone-600">Delivery</dt>
            <dd>
              {Number(order.shipping_fee) === 0
                ? 'Free'
                : formatBDT(order.shipping_fee)}
            </dd>
          </div>
          <div className="flex justify-between border-t border-stone-200 pt-3">
            <dt className="font-medium">Total due on delivery</dt>
            <dd className="font-semibold">{formatBDT(order.total)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-stone-600">Payment</dt>
            <dd>Cash on delivery</dd>
          </div>
        </dl>

        <div className="border-t border-stone-200 px-5 py-4 text-sm">
          <p className="text-xs uppercase tracking-widest text-stone-500">
            Delivering to
          </p>
          <p className="mt-2 leading-relaxed text-stone-700">
            {order.customer_name}
            <br />
            {address.address_line1}
            {address.address_line2 && (
              <>
                <br />
                {address.address_line2}
              </>
            )}
            <br />
            {[address.area, address.city, address.postal_code]
              .filter(Boolean)
              .join(', ')}
            {address.country && (
              <>
                <br />
                {address.country}
              </>
            )}
          </p>
          {order.notes && (
            <p className="mt-3 text-xs text-stone-500">Note: {order.notes}</p>
          )}
        </div>
      </div>

      {/* ── Tracking timeline ─────────────────────────────────────────── */}
      <section className="mt-10">
        <h2 className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
          Tracking
        </h2>
        <ol className="mt-4 space-y-5 border-l border-stone-200 pl-5">
          <li className="relative">
            <span className="absolute -left-[26px] top-1.5 h-2 w-2 rounded-full bg-stone-300" />
            <p className="text-sm font-medium">Order placed</p>
            <p className="mt-0.5 text-xs text-stone-500">
              {formatOrderDateTime(order.created_at)}
            </p>
          </li>
          {order.status_history.map((entry, index) => (
            <li key={`${entry.created_at}-${index}`} className="relative">
              <span className="absolute -left-[26px] top-1.5 h-2 w-2 rounded-full bg-stone-900" />
              <p className="text-sm font-medium">
                {entry.previous_status === entry.new_status
                  ? 'Return recorded'
                  : ORDER_STATUS_LABELS[entry.new_status]}
              </p>
              <p className="mt-0.5 text-xs text-stone-500">
                {formatOrderDateTime(entry.created_at)}
              </p>
              {entry.note && (
                <p className="mt-1 text-xs text-stone-600">{entry.note}</p>
              )}
            </li>
          ))}
        </ol>
        <p className="mt-4 text-xs text-stone-500">
          Keep this page bookmarked — it always shows the latest status.
        </p>
      </section>

      {/* ── Return requests ───────────────────────────────────────────── */}
      {order.return_requests.length > 0 && (
        <section className="mt-10">
          <h2 className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
            Return requests
          </h2>
          <ul className="mt-4 space-y-3">
            {order.return_requests.map((returnRequest) => (
              <li
                key={returnRequest.id}
                className="rounded-lg border border-stone-200 px-5 py-4 text-sm"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium">
                    {RETURN_STATUS_LABELS[returnRequest.status]}
                  </p>
                  <p className="text-xs text-stone-500">
                    {formatOrderDateTime(returnRequest.created_at)}
                  </p>
                </div>
                <p className="mt-2 text-xs text-stone-600">
                  {returnRequest.items
                    .map(
                      (line) =>
                        `${line.quantity} × ${line.product_title} (${line.variant_sku})`,
                    )
                    .join(', ')}
                </p>
                {returnRequest.reason && (
                  <p className="mt-1 text-xs text-stone-500">
                    Your reason: {returnRequest.reason}
                  </p>
                )}
                {returnRequest.staff_note && (
                  <p className="mt-1 text-xs text-stone-600">
                    From our team: {returnRequest.staff_note}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── Request a return ──────────────────────────────────────────── */}
      <section className="mt-10">
        <h2 className="text-xs font-medium uppercase tracking-[0.2em] text-stone-500">
          Need to return something?
        </h2>

        {returnNotice && (
          <p className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
            {returnNotice}
          </p>
        )}

        {order.can_request_return ? (
          <form
            onSubmit={(event) => void handleReturnSubmit(event)}
            className="mt-4 rounded-lg border border-stone-200 px-5 py-4"
          >
            <ul className="divide-y divide-stone-200">
              {order.items
                .filter((item) => item.remaining_quantity > 0)
                .map((item) => (
                  <li
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"
                  >
                    <span className="min-w-0">
                      <span className="block font-medium">
                        {item.product_title}
                      </span>
                      <span className="mt-0.5 block text-xs text-stone-500">
                        {item.variant_sku} · {item.remaining_quantity} left to
                        return
                      </span>
                    </span>
                    <label className="flex items-center gap-2 text-xs text-stone-600">
                      Return
                      <input
                        type="number"
                        min={0}
                        max={item.remaining_quantity}
                        step={1}
                        value={quantities[item.id] ?? 0}
                        onChange={(event) =>
                          updateQuantity(
                            item.id,
                            Number(event.target.value),
                            item.remaining_quantity,
                          )
                        }
                        className="w-16 rounded-md border border-stone-300 px-2 py-1 text-sm tabular-nums"
                        aria-label={`Units of ${item.product_title} to return`}
                      />
                    </label>
                  </li>
                ))}
            </ul>

            <label
              htmlFor="return-reason"
              className="mt-3 block text-xs uppercase tracking-widest text-stone-500"
            >
              Reason (optional)
            </label>
            <textarea
              id="return-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              maxLength={1000}
              rows={2}
              className="mt-2 w-full rounded-md border border-stone-300 px-3 py-2 text-sm"
              placeholder="e.g. wrong size, damaged on arrival"
            />

            {returnError && <p className="mt-2 text-sm text-red-600">{returnError}</p>}

            <button
              type="submit"
              disabled={isSubmittingReturn}
              className="mt-4 rounded-md bg-stone-900 px-6 py-3 text-xs font-medium uppercase tracking-widest text-white transition-colors hover:bg-stone-700 disabled:cursor-not-allowed disabled:bg-stone-400"
            >
              {isSubmittingReturn ? 'Sending…' : 'Request a return'}
            </button>
            <p className="mt-2 text-xs text-stone-500">
              Our team reviews every request. Stock only returns to the catalog
              once we approve it.
            </p>
          </form>
        ) : (
          <p className="mt-3 text-sm text-stone-600">
            {openRequest
              ? 'Your return request is awaiting review. We will update this page once it is resolved.'
              : order.status === 'DELIVERED'
                ? 'Every item on this order has already been returned.'
                : 'You can request a return once your order has been delivered.'}
          </p>
        )}
      </section>

      <div className="mt-8 flex flex-wrap gap-4">
        <Link
          to="/orders"
          className="rounded-md bg-stone-900 px-6 py-3 text-xs font-medium uppercase tracking-widest text-white transition-colors hover:bg-stone-700"
        >
          All my orders
        </Link>
        <Link
          to="/shop"
          className="rounded-md border border-stone-300 px-6 py-3 text-xs font-medium uppercase tracking-widest text-stone-700 transition-colors hover:border-stone-900 hover:text-stone-900"
        >
          Continue shopping
        </Link>
      </div>
    </div>
  )
}
