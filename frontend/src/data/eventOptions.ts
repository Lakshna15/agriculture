import type { FarmEventType } from '../api/events.ts'

export const farmEventTypeLabels: Record<FarmEventType, string> = {
  STRAWBERRY_PICKING: 'Strawberry picking',
  APPLE_PICKING: 'Apple picking',
  PUMPKIN_PICKING: 'Pumpkin picking',
  VEGETABLE_PICKING: 'Vegetable picking',
  FARM_TOUR: 'Farm tour',
  OTHER: 'Other',
}

export const farmEventTypeOptions = (
  Object.entries(farmEventTypeLabels) as [FarmEventType, string][]
).map(([value, label]) => ({ value, label }))
