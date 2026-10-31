export interface Category {
  id: number;
  name: string;
  slug: string;
  is_active: boolean;
  children: Category[];
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
}

export interface ProductListItem {
  id: string;
  slug: string;
  title: string;
  base_price: string;
  category: string;
  primary_image: ProductImage | null;
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
