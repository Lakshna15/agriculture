import type { ProductCategory, ProductSearchSort, ProductUnit } from '../api/products.ts'

export const productCategoryLabels: Record<ProductCategory, string> = {
  VEGETABLES: 'Vegetables',
  FRUITS: 'Fruits',
  EGGS: 'Eggs',
  DAIRY: 'Dairy',
  MEAT: 'Meat',
  HERBS: 'Herbs',
  SEASONAL: 'Seasonal',
  OTHER: 'Other',
}

/** Short forms used next to a price or a quantity, as in "$4.50 / lb". */
export const productUnitLabels: Record<ProductUnit, string> = {
  LB: 'lb',
  OZ: 'oz',
  EACH: 'each',
  DOZEN: 'dozen',
  BUNCH: 'bunch',
  PINT: 'pint',
  QUART: 'quart',
  GALLON: 'gallon',
}

function toOptions<Value extends string>(labels: Record<Value, string>) {
  return (Object.entries(labels) as [Value, string][]).map(([value, label]) => ({ value, label }))
}

export const productCategoryOptions = toOptions(productCategoryLabels)
export const productUnitOptions = toOptions(productUnitLabels)

export const searchRadiusMilesOptions = [5, 10, 25, 50, 100]
export const DEFAULT_SEARCH_RADIUS_MILES = 25

export const searchSortOptions: { value: ProductSearchSort; label: string }[] = [
  { value: 'distance', label: 'Nearest first' },
  { value: 'price', label: 'Lowest price first' },
  { value: 'harvest_date', label: 'Most recently harvested first' },
]
