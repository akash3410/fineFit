const API_BASE = "/api/v1";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getCategories() {
  return apiGet<CategoryResponse>("/catalog/categories/");
}

export function getProducts(params?: Record<string, string>) {
  const query = params ? `?${new URLSearchParams(params).toString()}` : "";
  return apiGet<ProductListResponse>(`/catalog/products/${query}`);
}

export function getProduct(slug: string) {
  return apiGet<ProductDetail>(`/catalog/products/${slug}/`);
}

import type { Category, ProductDetail, ProductListItem } from "../types/catalog";

type CategoryResponse = Category[] | { results: Category[] };
type ProductListResponse = { results: ProductListItem[] };
