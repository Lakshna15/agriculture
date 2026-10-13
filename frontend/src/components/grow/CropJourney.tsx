import type { CropUpdate } from '../../api/cropJourney.ts'
import { cropStageLabels } from '../../data/journeyOptions.ts'
import { formatDateTime } from '../../lib/format.ts'

/** A grow offer's updates as a timeline, in the order they were posted. */
export default function CropJourney({ updates }: { updates: CropUpdate[] }) {
  if (updates.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-stone-300 bg-white p-6 text-center text-sm text-stone-600">
        No updates yet. The farmer will post here as the crop is planned, planted and grown.
      </p>
    )
  }

  return (
    <ol className="space-y-3">
      {updates.map((update) => (
        <li key={update.id} className="rounded-lg border border-stone-200 bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-semibold text-stone-900">{cropStageLabels[update.stage]}</h3>
            <time dateTime={update.created_at} className="text-xs text-stone-500">
              {formatDateTime(update.created_at)}
            </time>
          </div>
          <p className="mt-1 text-sm whitespace-pre-line text-stone-700">{update.message}</p>
          {update.image_url && (
            // The photo is a link rather than an embedded image. Loading it
            // automatically would let whoever hosts it record the address of
            // every customer who opens the page.
            <a
              href={update.image_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-block text-sm font-medium text-green-800 underline underline-offset-4"
            >
              View photo
            </a>
          )}
        </li>
      ))}
    </ol>
  )
}
