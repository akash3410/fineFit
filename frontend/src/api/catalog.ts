const API_BASE = "/api/v1";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getCategories() {
  return apiGet<CategoryResponse>("/categories/");
}

export function getSubcategories(params?: Record<string, string>) {
  const query = params ? `?${new URLSearchParams(params).toString()}` : "";
  return apiGet<SubcategoryListResponse>(`/subcategories/${query}`);
}

export function getEvents() {
  return apiGet<EventResponse>("/events/");
}

export function getProducts(params?: Record<string, string>) {
  const query = params ? `?${new URLSearchParams(params).toString()}` : "";
  return apiGet<ProductListResponse>(`/products/${query}`);
}

export function getProduct(slug: string) {
  return apiGet<ProductDetail>(`/products/${slug}/`);
}

import type {
  Category,
  Event,
  PaginatedResponse,
  ProductDetail,
  ProductListItem,
  Subcategory,
} from "../types/catalog";

type CategoryResponse = Category[] | PaginatedResponse<Category>;
type SubcategoryListResponse = PaginatedResponse<Subcategory>;
type EventResponse = Event[] | PaginatedResponse<Event>;
type ProductListResponse = PaginatedResponse<ProductListItem>;
