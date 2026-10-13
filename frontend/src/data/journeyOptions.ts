import type { CropStage } from '../api/cropJourney.ts'

/** Stages in growing order, which is also the order the API accepts them in. */
export const cropStageLabels: Record<CropStage, string> = {
  PLANNED: 'Planned',
  PLANTED: 'Planted',
  GERMINATED: 'Germinated',
  GROWING: 'Growing',
  FLOWERING: 'Flowering',
  HARVEST_SOON: 'Harvest soon',
  READY: 'Ready',
}

export const cropStageOptions = (Object.entries(cropStageLabels) as [CropStage, string][]).map(
  ([value, label]) => ({ value, label }),
)
