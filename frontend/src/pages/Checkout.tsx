import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/http'
import { placeOrder } from '../api/orders'
import { useCart } from '../features/cart/CartContext'
import type { CheckoutPayload } from '../types/order'
import { formatBDT } from '../utils/currency'

/* ────────────────────────────────────────────────────────────────────────────
 * Checkout — cash-on-delivery order form.
 *
 * The bag (prices, quantities, totals) always comes from the backend cart; this
 * form only collects the delivery details. Placing the order posts the cart to
 * the orders API, which re-validates stock and prices server-side, then clears
 * the bag and returns the created order.
 * ──────────────────────────────────────────────────────────────────────── */

const EMPTY_FORM = {
  customer_name: '',
  customer_phone: '',
  customer_email: '',
  address_line1: '',
  address_line2: '',
  city: '',
  area: '',
  postal_code: '',
  country: 'Bangladesh',
  notes: '',
}

function Field({
  label,
  name,
  value,
  onChange,
  required = false,
  type = 'text',
  placeholder,
  hint,
  autoComplete,
}: {
  label: string
  name: keyof typeof EMPTY_FORM
  value: string
  onChange: (name: keyof typeof EMPTY_FORM, value: string) => void
  required?: boolean
  type?: string
  placeholder?: string
  hint?: string
  autoComplete?: string
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium uppercase tracking-widest text-stone-600">
        {label}
        {required && <span className="ml-1 text-red-600">*</span>}
      </span>
      <input
        type={type}
        name={name}
        value={value}
        required={required}
        placeholder={placeholder}
        autoComplete={autoComplete}
        onChange={(event) => onChange(name, event.target.value)}
        className="mt-2 w-full rounded-md border border-stone-300 px-3 py-2.5 text-sm outline-none transition-colors focus:border-stone-900"
      />
      {hint && <span className="mt-1 block text-xs text-stone-400">{hint}</span>}
    </label>
  )
}

export function Checkout() {
  const { items, subtotal, totalQuantity, isLoading, refresh } = useCart()
  const navigate = useNavigate()
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const update = (name: keyof typeof EMPTY_FORM, value: string) => {
    setForm((current) => ({ ...current, [name]: value }))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIsSubmitting(true)
    setError(null)

    const payload: CheckoutPayload = {
      customer_name: form.customer_name,
      customer_phone: form.customer_phone,
      customer_email: form.customer_email,
      shipping_address: {
        address_line1: form.address_line1,
        address_line2: form.address_line2,
        city: form.city,
        area: form.area,
        postal_code: form.postal_code,
        country: form.country,
      },
      notes: form.notes,
      payment_method: 'COD',
    }

    try {
      const order = await placeOrder(payload)
      // The backend cleared the bag as part of placing the order.
      await refresh()
      navigate(`/order/${order.order_number}`, { replace: true })
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'We could not place your order. Please try again.',
      )
      setIsSubmitting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10">
        <p className="text-sm text-stone-600">Loading your bag…</p>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-10">
        <h1 className="text-3xl font-semibold tracking-tight">Checkout</h1>
        <div className="mt-10 rounded-lg border border-dashed border-stone-300 px-6 py-16 text-center">
          <p className="text-sm text-stone-600">Your bag is empty.</p>
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
      <h1 className="text-3xl font-semibold tracking-tight">Checkout</h1>
      <p className="mt-2 text-sm text-stone-600">
        Pay cash when your order is delivered.
      </p>

      <form
        onSubmit={handleSubmit}
        className="mt-8 grid gap-10 lg:grid-cols-[minmax(0,1fr)_340px]"
      >
        <div className="space-y-8">
          {error && (
            <div
              role="alert"
              className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              {error}
            </div>
          )}

          <section>
            <h2 className="text-sm font-medium uppercase tracking-widest">
              Contact
            </h2>
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              <Field
                label="Full name"
                name="customer_name"
                value={form.customer_name}
                onChange={update}
                required
                autoComplete="name"
              />
              <Field
                label="Phone"
                name="customer_phone"
                value={form.customer_phone}
                onChange={update}
                required
                type="tel"
                placeholder="01XXXXXXXXX"
                autoComplete="tel"
                hint="We call this number to confirm delivery."
              />
              <div className="sm:col-span-2">
                <Field
                  label="Email"
                  name="customer_email"
                  value={form.customer_email}
                  onChange={update}
                  type="email"
                  autoComplete="email"
                  hint="Optional — for order updates."
                />
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-medium uppercase tracking-widest">
              Delivery address
            </h2>
            <div className="mt-4 grid gap-5 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Field
                  label="Address"
                  name="address_line1"
                  value={form.address_line1}
                  onChange={update}
                  required
                  placeholder="House / road / block"
                  autoComplete="address-line1"
                />
              </div>
              <div className="sm:col-span-2">
                <Field
                  label="Area or landmark"
                  name="address_line2"
                  value={form.address_line2}
                  onChange={update}
                  autoComplete="address-line2"
                />
              </div>
              <Field
                label="City / district"
                name="city"
                value={form.city}
                onChange={update}
                required
                autoComplete="address-level2"
              />
              <Field
                label="Area"
                name="area"
                value={form.area}
                onChange={update}
                autoComplete="address-level3"
              />
              <Field
                label="Postal code"
                name="postal_code"
                value={form.postal_code}
                onChange={update}
                autoComplete="postal-code"
              />
              <Field
                label="Country"
                name="country"
                value={form.country}
                onChange={update}
                autoComplete="country-name"
              />
              <div className="sm:col-span-2">
                <label className="block">
                  <span className="text-xs font-medium uppercase tracking-widest text-stone-600">
                    Delivery notes
                  </span>
                  <textarea
                    name="notes"
                    value={form.notes}
                    onChange={(event) => update('notes', event.target.value)}
                    rows={3}
                    placeholder="Optional instructions for the delivery rider"
                    className="mt-2 w-full rounded-md border border-stone-300 px-3 py-2.5 text-sm outline-none transition-colors focus:border-stone-900"
                  />
                </label>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-sm font-medium uppercase tracking-widest">
              Payment
            </h2>
            <div className="mt-4 rounded-md border border-stone-900 px-4 py-4">
              <div className="flex items-start gap-3">
                <input
                  type="radio"
                  id="payment-cod"
                  name="payment_method"
                  value="COD"
                  checked
                  readOnly
                  className="mt-1 h-4 w-4 accent-stone-900"
                />
                <div>
                  <label
                    htmlFor="payment-cod"
                    className="text-sm font-medium text-stone-900"
                  >
                    Cash on delivery
                  </label>
                  <p className="mt-1 text-xs leading-relaxed text-stone-600">
                    Pay the rider in cash when your order arrives. No card or
                    online payment is required.
                  </p>
                </div>
              </div>
            </div>
          </section>
        </div>

        <aside className="h-fit rounded-lg border border-stone-200 p-6">
          <h2 className="text-sm font-medium uppercase tracking-widest">
            Order summary
          </h2>
          <ul className="mt-5 space-y-3 border-b border-stone-200 pb-4">
            {items.map((item) => (
              <li key={item.id} className="flex justify-between gap-3 text-sm">
                <span className="min-w-0">
                  <span className="block truncate">{item.variant.product_title}</span>
                  <span className="mt-0.5 block text-xs text-stone-500">
                    {[item.variant.size, item.variant.color_name]
                      .filter(Boolean)
                      .join(' / ')}{' '}
                    × {item.quantity}
                  </span>
                </span>
                <span className="whitespace-nowrap">
                  {item.line_total ? formatBDT(item.line_total) : '—'}
                </span>
              </li>
            ))}
          </ul>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-stone-600">Items</dt>
              <dd>{totalQuantity}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-stone-600">Subtotal</dt>
              <dd className="font-medium">{formatBDT(subtotal)}</dd>
            </div>
            <div className="flex justify-between border-t border-stone-200 pt-3">
              <dt className="font-medium">Total due on delivery</dt>
              <dd className="font-semibold">{formatBDT(subtotal)}</dd>
            </div>
          </dl>

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-6 w-full rounded-md bg-stone-900 px-6 py-3 text-xs font-medium uppercase tracking-widest text-white transition-colors hover:bg-stone-700 disabled:cursor-not-allowed disabled:bg-stone-400"
          >
            {isSubmitting ? 'Placing order…' : 'Place order (cash on delivery)'}
          </button>
          <Link
            to="/cart"
            className="mt-4 block text-center text-xs text-stone-600 underline-offset-4 hover:text-stone-900 hover:underline"
          >
            Back to bag
          </Link>
        </aside>
      </form>
    </div>
  )
}
