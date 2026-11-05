/**
 * Order API types.
 *
 * Mirrors the backend contract in ``apps/orders/serializers.py``. Prices and
 * totals are server-computed decimal strings taken from the order snapshot.
 */

export type OrderStatus =
  | "PENDING"
  | "CONFIRMED"
  | "PROCESSING"
  | "SHIPPED"
  | "DELIVERED"
  | "CANCELLED"
  | "RETURNED";

export type PaymentMethod = "COD";

export interface ShippingAddress {
  address_line1: string;
  address_line2: string;
  city: string;
  area: string;
  postal_code: string;
  country: string;
}

export interface OrderItem {
  id: number;
  product_title: string;
  variant_sku: string;
  size: string;
  color_name: string;
  unit_price: string;
  quantity: number;
  returned_quantity: number;
  remaining_quantity: number;
  line_total: string;
}

export interface OrderStatusHistoryEntry {
  previous_status: OrderStatus | "";
  new_status: OrderStatus;
  note: string;
  created_at: string;
}

export type ReturnRequestStatus = "REQUESTED" | "APPROVED" | "DECLINED";

export interface ReturnRequestLine {
  item_id: number;
  product_title: string;
  variant_sku: string;
  quantity: number;
}

export interface ReturnRequest {
  id: string;
  status: ReturnRequestStatus;
  reason: string;
  staff_note: string;
  items: ReturnRequestLine[];
  total_quantity: number;
  created_at: string;
  resolved_at: string | null;
}

export interface Order {
  id: string;
  order_number: string;
  status: OrderStatus;
  payment_method: PaymentMethod;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  shipping_address: ShippingAddress;
  notes: string;
  subtotal: string;
  shipping_fee: string;
  total: string;
  total_quantity: number;
  items: OrderItem[];
  status_history: OrderStatusHistoryEntry[];
  return_requests: ReturnRequest[];
  can_request_return: boolean;
  created_at: string;
}

export interface OrderListResponse {
  results: Order[];
}

/** Return request payload: order item ids and unit counts only. */
export type ReturnRequestPayload = {
  reason: string;
  items: { item_id: number; quantity: number }[];
};

/** Checkout payload: customer + delivery details only (never prices or totals). */
export type CheckoutPayload = {
  customer_name: string;
  customer_phone: string;
  customer_email: string;
  shipping_address: {
    address_line1: string;
    address_line2: string;
    city: string;
    area: string;
    postal_code: string;
    country: string;
  };
  notes: string;
  payment_method: PaymentMethod;
};
