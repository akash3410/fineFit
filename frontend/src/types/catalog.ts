export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Category {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  image?: string | null;
  children: Category[];
}

export interface Subcategory {
  id: number;
  name: string;
  slug: string;
  image?: string | null;
  is_active: boolean;
  category: number;
  category_name: string;
  category_slug?: string | null;
}

export interface ProductImage {
  id: number;
  image: string;
  alt_text: string;
  display_order: number;
  is_primary: boolean;
  variant: number | null;
}

export interface ProductVariant {
  id: string;
  sku: string;
  size: string;
  color_name: string;
  color_code: string;
  is_active: boolean;
  effective_price: string | null;
  /** Derived server-side from the inventory source of truth. */
  is_in_stock?: boolean;
  is_low_stock?: boolean;
  stock_status?: "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK";
}

export interface ProductListItem {
  id: string;
  slug: string;
  title: string;
  base_price: string;
  discount_price?: string | null;
  stock?: number;
  category: string;
  primary_image: ProductImage | null;
  created_at: string;
}

export interface Event {
  id: number;
  slug: string;
  title: string;
  announcement: string;
  image?: string | null;
  start_at: string;
  end_at: string | null;
  is_active: boolean;
  cta_label: string;
  cta_link: string;
  created_at: string;
}

export interface ProductDetail {
  id: string;
  slug: string;
  title: string;
  description: string;
  base_price: string;
  category: Category;
  images: ProductImage[];
  variants: ProductVariant[];
  created_at: string;
}
