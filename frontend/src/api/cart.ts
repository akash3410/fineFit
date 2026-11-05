/**
 * Cart API client.
 *
 * Every mutation returns the authoritative, server-recomputed cart, so the UI
 * state is replaced rather than patched locally. The cart owner is resolved
 * server-side from the session (guest) or the logged-in customer — no cart or
 * session identifiers are ever sent from the client.
 */

import { apiRequest } from "./http";
import type { Cart } from "../types/cart";

const CART_PATH = "/cart/";

/** Highest quantity the backend accepts for a single line. */
export const MAX_QUANTITY_PER_ITEM = 99;

export function getCart() {
  return apiRequest<Cart>(CART_PATH);
}

export function addCartItem(variantId: string, quantity = 1) {
  return apiRequest<Cart>(`${CART_PATH}items/`, {
    method: "POST",
    body: { variant_id: variantId, quantity },
  });
}

export function updateCartItem(itemId: number, quantity: number) {
  return apiRequest<Cart>(`${CART_PATH}items/${itemId}/`, {
    method: "PATCH",
    body: { quantity },
  });
}

export function removeCartItem(itemId: number) {
  return apiRequest<Cart>(`${CART_PATH}items/${itemId}/`, {
    method: "DELETE",
  });
}

export function clearCart() {
  return apiRequest<Cart>(CART_PATH, { method: "DELETE" });
}
