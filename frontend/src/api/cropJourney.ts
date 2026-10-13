import { apiRequest } from './client.ts'
import type { GrowOffer, GrowOfferFarm } from './growOffers.ts'

export type CropStage =
  | 'PLANNED'
  | 'PLANTED'
  | 'GERMINATED'
  | 'GROWING'
  | 'FLOWERING'
  | 'HARVEST_SOON'
  | 'READY'

export type CropUpdate = {
  id: number
  grow_offer_id: number
  stage: CropStage
  message: string
  /** An https link to a photo hosted elsewhere, if the farmer added one. */
  image_url: string | null
  created_at: string
}

export type NewCropUpdate = Pick<CropUpdate, 'stage' | 'message' | 'image_url'>

export type GrowOfferDetail = { offer: GrowOffer; farm: GrowOfferFarm }

// The offer and its journey are public, so reading them sends no token.

export function fetchGrowOfferDetail(offerId: number): Promise<GrowOfferDetail> {
  return apiRequest<GrowOfferDetail>(`/api/grow-offers/${offerId}`)
}

/** The offer's updates, oldest first. */
export function fetchCropUpdates(offerId: number): Promise<CropUpdate[]> {
  return apiRequest<CropUpdate[]>(`/api/grow-offers/${offerId}/updates`)
}

export function postCropUpdate(
  accessToken: string,
  offerId: number,
  update: NewCropUpdate,
): Promise<CropUpdate> {
  return apiRequest<CropUpdate>(`/api/grow-offers/${offerId}/updates`, {
    method: 'POST',
    body: update,
    accessToken,
  })
}

export function completeGrowOffer(accessToken: string, offerId: number): Promise<GrowOffer> {
  return apiRequest<GrowOffer>(`/api/grow-offers/${offerId}/complete`, {
    method: 'POST',
    accessToken,
  })
}
