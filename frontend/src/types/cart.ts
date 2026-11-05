/**
 * Cart API types.
 *
 * Mirrors the backend contract in ``apps/cart/serializers.py``. All monetary
 * values are server-computed decimal strings — the client never sends prices,
 * totals or availability.
 */

export interface CartVariant {
  id: string;
  sku: string;
  size: string;
  color_name: string;
  color_code: string;
  is_active: boolean;
  product_title: string;
  product_slug: string;
}

export interface CartItem {
  id: number;
  variant: CartVariant;
  image: string | null;
  /** Current trusted unit price as a decimal string. */
  unit_price: string | null;
  quantity: number;
  /** unit_price * quantity as a decimal string. */
  line_total: string | null;
  /** Sellable units right now (advisory; re-validated at checkout). */
  available_quantity: number;
  is_available: boolean;
  has_sufficient_stock: boolean;
  created_at: string;
}

export interface CartConflict {
  cart_item_id: number;
  variant_id: string;
  sku: string;
  quantity: number;
  available_quantity: number;
  reason: "OUT_OF_STOCK" | "INSUFFICIENT_STOCK" | "VARIANT_UNAVAILABLE" | string;
}

export interface Cart {
  id: string;
  items: CartItem[];
  total_quantity: number;
  subtotal: string;
  has_stock_conflicts: boolean;
  conflicts: CartConflict[];
  created_at: string;
  updated_at: string;
}
