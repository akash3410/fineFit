import type { OrderStatus } from "../types/order";

/** Customer-facing wording for each fulfilment status. */
export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  PENDING: "Received — awaiting confirmation",
  CONFIRMED: "Confirmed",
  PROCESSING: "Preparing your order",
  SHIPPED: "Shipped",
  DELIVERED: "Delivered",
  CANCELLED: "Cancelled",
  RETURNED: "Returned",
};

const DATE_FORMAT: Intl.DateTimeFormatOptions = {
  day: "numeric",
  month: "short",
  year: "numeric",
};

/** e.g. "6 Nov 2026" */
export function formatOrderDate(value: string): string {
  return new Date(value).toLocaleDateString("en-GB", DATE_FORMAT);
}

/** e.g. "6 Nov 2026, 14:05" */
export function formatOrderDateTime(value: string): string {
  return new Date(value).toLocaleString("en-GB", {
    ...DATE_FORMAT,
    hour: "2-digit",
    minute: "2-digit",
  });
}
