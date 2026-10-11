import { apiRequest } from './client.ts'

export type ProductCategory =
  | 'VEGETABLES'
  | 'FRUITS'
  | 'EGGS'
  | 'DAIRY'
  | 'MEAT'
  | 'HERBS'
  | 'SEASONAL'
  | 'OTHER'

export type ProductUnit = 'LB' | 'OZ' | 'EACH' | 'DOZEN' | 'BUNCH' | 'PINT' | 'QUART' | 'GALLON'

export type Product = {
  id: number
  farm_id: number
  name: string
  category: ProductCategory
  description: string | null
  /** A decimal amount as text, for example "4.50", so cents are never rounded. */
  price: string
  unit: ProductUnit
  quantity_available: number
  /** Dates are ISO calendar dates, for example "2026-06-01". */
  harvest_date: string | null
  available_from: string | null
  available_until: string | null
  organic: boolean
  active: boolean
  created_at: string
  updated_at: string
}

/** The fields a farmer can edit. Stock is changed separately so every change is recorded. */
export type ProductDetails = Omit<
  Product,
  'id' | 'farm_id' | 'quantity_available' | 'created_at' | 'updated_at'
>

export type NewProduct = ProductDetails & { quantity_available: number }

export type ProductSearchSort = 'distance' | 'price' | 'harvest_date'

export type ProductSearchCriteria = {
  query: string
  /** An empty string means every category. */
  category: ProductCategory | ''
  latitude: number
  longitude: number
  radiusMiles: number
  availableOnly: boolean
  sort: ProductSearchSort
}

export type ProductSearchResult = {
  product: Pick<
    Product,
    | 'id'
    | 'name'
    | 'category'
    | 'description'
    | 'unit'
    | 'organic'
    | 'available_from'
    | 'available_until'
  >
  farm: {
    id: number
    farm_name: string
    city: string
    state: string
    pickup_available: boolean
    delivery_available: boolean
  }
  distance_miles: number
  price: string
  quantity_available: number
  harvest_date: string | null
}

export function fetchMyProducts(accessToken: string): Promise<Product[]> {
  return apiRequest<Product[]>('/api/products/mine', { accessToken })
}

export function createProduct(accessToken: string, product: NewProduct): Promise<Product> {
  return apiRequest<Product>('/api/products', { method: 'POST', body: product, accessToken })
}

export function updateProduct(
  accessToken: string,
  productId: number,
  details: ProductDetails,
): Promise<Product> {
  return apiRequest<Product>(`/api/products/${productId}`, {
    method: 'PUT',
    body: details,
    accessToken,
  })
}

export function updateProductInventory(
  accessToken: string,
  productId: number,
  quantityAvailable: number,
): Promise<Product> {
  return apiRequest<Product>(`/api/products/${productId}/inventory`, {
    method: 'PATCH',
    body: { quantity_available: quantityAvailable },
    accessToken,
  })
}

export function searchProducts(criteria: ProductSearchCriteria): Promise<ProductSearchResult[]> {
  const params = new URLSearchParams({
    latitude: String(criteria.latitude),
    longitude: String(criteria.longitude),
    radius_miles: String(criteria.radiusMiles),
    available_only: String(criteria.availableOnly),
    sort: criteria.sort,
  })
  if (criteria.query.trim() !== '') {
    params.set('query', criteria.query.trim())
  }
  if (criteria.category !== '') {
    params.set('category', criteria.category)
  }
  return apiRequest<ProductSearchResult[]>(`/api/products/search?${params}`)
}
