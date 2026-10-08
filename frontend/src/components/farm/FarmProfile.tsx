import type { Farm } from '../../api/farms.ts'

function describeFulfilment(farm: Farm): string {
  if (farm.pickup_available && farm.delivery_available) {
    return 'Pickup and delivery'
  }
  if (farm.pickup_available) {
    return 'Pickup only'
  }
  if (farm.delivery_available) {
    return 'Delivery only'
  }
  return 'Not offered yet'
}

type FarmProfileProps = {
  farm: Farm
  onEdit: () => void
}

export default function FarmProfile({ farm, onEdit }: FarmProfileProps) {
  const profileFacts = [
    { term: 'Address', detail: `${farm.address}, ${farm.city}, ${farm.state} ${farm.zip_code}` },
    { term: 'Coordinates', detail: `${farm.latitude}, ${farm.longitude}` },
    { term: 'Phone', detail: farm.phone ?? 'Not provided' },
    { term: 'Fulfilment', detail: describeFulfilment(farm) },
  ]

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-stone-900">{farm.farm_name}</h2>
          <p className="mt-2 whitespace-pre-line text-stone-600">
            {farm.description ?? 'No description yet.'}
          </p>
        </div>
        <button
          type="button"
          onClick={onEdit}
          className="shrink-0 rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-800 shadow-sm transition-colors hover:bg-stone-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-700"
        >
          Edit Farm
        </button>
      </div>

      <dl className="mt-6 grid gap-x-8 gap-y-4 border-t border-stone-200 pt-6 sm:grid-cols-2">
        {profileFacts.map((fact) => (
          <div key={fact.term}>
            <dt className="text-xs font-medium tracking-wide text-stone-500 uppercase">
              {fact.term}
            </dt>
            <dd className="mt-1 text-sm text-stone-900">{fact.detail}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
