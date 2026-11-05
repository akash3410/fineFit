/**
 * Order API client.
 *
 * Checkout posts the current server-side cart to ``/orders/checkout/``; the
 * backend recomputes prices, validates stock and clears the cart, so the client
 * never sends prices, totals or stock figures.
 */

import { apiRequest } from "./http";
import type {
  CheckoutPayload,
  Order,
  OrderListResponse,
  ReturnRequest,
  ReturnRequestPayload,
} from "../types/order";

export function placeOrder(payload: CheckoutPayload) {
  return apiRequest<Order>("/orders/checkout/", {
    method: "POST",
    body: payload,
  });
}

export function getOrder(orderNumber: string) {
  return apiRequest<Order>(`/orders/${encodeURIComponent(orderNumber)}/`);
}

export function listOrders() {
  return apiRequest<OrderListResponse>("/orders/");
}

/** Ask to return delivered units; stock only moves when staff approve. */
export function requestReturn(orderNumber: string, payload: ReturnRequestPayload) {
  return apiRequest<ReturnRequest>(
    `/orders/${encodeURIComponent(orderNumber)}/returns/`,
    { method: "POST", body: payload },
  );
}
