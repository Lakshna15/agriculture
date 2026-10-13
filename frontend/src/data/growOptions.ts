import type { RequestFrequency, Season } from '../api/cropRequests.ts'
import type { GrowOfferStatus } from '../api/growOffers.ts'

/** Completes "3 lb ...", as in "3 lb every week". */
export const requestFrequencyLabels: Record<RequestFrequency, string> = {
  ONE_TIME: 'one time',
  WEEKLY: 'every week',
  MONTHLY: 'every month',
}

export const requestFrequencyOptions: { value: RequestFrequency; label: string }[] = [
  { value: 'WEEKLY', label: 'Every week' },
  { value: 'MONTHLY', label: 'Every month' },
  { value: 'ONE_TIME', label: 'One time only' },
]

export const seasonLabels: Record<Season, string> = {
  SPRING: 'Spring',
  SUMMER: 'Summer',
  FALL: 'Fall',
  WINTER: 'Winter',
}

export const seasonOptions = (Object.entries(seasonLabels) as [Season, string][]).map(
  ([value, label]) => ({ value, label }),
)

export const growOfferStatusLabels: Record<GrowOfferStatus, string> = {
  OPEN: 'Open',
  CONFIRMED: 'Confirmed',
  GROWING: 'Growing',
  READY: 'Ready',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
}

export const growOfferStatusBadgeClassNames: Record<GrowOfferStatus, string> = {
  OPEN: 'bg-amber-100 text-amber-900',
  CONFIRMED: 'bg-green-100 text-green-900',
  GROWING: 'bg-green-100 text-green-900',
  READY: 'bg-green-100 text-green-900',
  COMPLETED: 'bg-stone-200 text-stone-700',
  CANCELLED: 'bg-red-100 text-red-900',
}
