import { useEffect, useState } from 'react'
import { describeApiError } from '../api/errors.ts'
import { createFarm, fetchMyFarm, updateFarm, type Farm, type FarmDetails } from '../api/farms.ts'
import { useAccessToken } from '../auth/useAuth.ts'
import FarmForm from '../components/farm/FarmForm.tsx'
import FarmProfile from '../components/farm/FarmProfile.tsx'

type FarmLoadState =
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  /** farm is null when the farmer has not created one yet. */
  | { status: 'loaded'; farm: Farm | null }

const primaryButtonClassName =
  'rounded-md bg-green-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-green-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-700'

export default function FarmerDashboardPage() {
  const accessToken = useAccessToken()
  const [farmState, setFarmState] = useState<FarmLoadState>({ status: 'loading' })
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [isEditing, setIsEditing] = useState(false)
  const [savedMessage, setSavedMessage] = useState<string | null>(null)

  useEffect(() => {
    let isCurrent = true
    fetchMyFarm(accessToken)
      .then((farm) => {
        if (isCurrent) {
          setFarmState({ status: 'loaded', farm })
        }
      })
      .catch((error: unknown) => {
        if (isCurrent) {
          setFarmState({ status: 'failed', message: describeApiError(error) })
        }
      })
    return () => {
      isCurrent = false
    }
  }, [accessToken, loadAttempt])

  function retryLoading() {
    setFarmState({ status: 'loading' })
    setLoadAttempt((attempt) => attempt + 1)
  }

  function startEditing() {
    setSavedMessage(null)
    setIsEditing(true)
  }

  function showSavedFarm(farm: Farm, message: string) {
    setFarmState({ status: 'loaded', farm })
    setIsEditing(false)
    setSavedMessage(message)
  }

  async function handleCreate(details: FarmDetails) {
    showSavedFarm(await createFarm(accessToken, details), 'Your farm has been created.')
  }

  async function handleUpdate(farmId: number, details: FarmDetails) {
    showSavedFarm(await updateFarm(accessToken, farmId, details), 'Your changes have been saved.')
  }

  const hasLoaded = farmState.status === 'loaded'
  const farm = farmState.status === 'loaded' ? farmState.farm : null

  return (
    <>
      <h1 className="text-3xl font-bold tracking-tight text-stone-900">Farmer Dashboard</h1>
      <p className="mt-2 text-stone-600">
        Your farm profile is what nearby customers see when they find you.
      </p>

      <div className="mt-8 space-y-4">
        {savedMessage && (
          <p
            role="status"
            className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900"
          >
            {savedMessage}
          </p>
        )}

        {farmState.status === 'loading' && (
          <p role="status" className="text-stone-600">
            Loading your farm…
          </p>
        )}

        {farmState.status === 'failed' && (
          <section className="rounded-xl border border-red-200 bg-red-50 p-6">
            <p role="alert" className="text-sm text-red-800">
              Your farm could not be loaded. {farmState.message}
            </p>
            <button type="button" onClick={retryLoading} className={`mt-4 ${primaryButtonClassName}`}>
              Try again
            </button>
          </section>
        )}

        {hasLoaded && farm === null && !isEditing && (
          <section className="rounded-xl border border-dashed border-stone-300 bg-white p-8 text-center">
            <h2 className="text-lg font-semibold text-stone-900">You have not set up your farm yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-stone-600">
              Create your farm profile so customers nearby can find you. You will need your
              address and your farm's coordinates.
            </p>
            <button type="button" onClick={startEditing} className={`mt-6 ${primaryButtonClassName}`}>
              Create Farm
            </button>
          </section>
        )}

        {hasLoaded && farm === null && isEditing && (
          <FarmForm
            title="Create Farm"
            submitLabel="Create Farm"
            initialFarm={null}
            onSubmit={handleCreate}
            onCancel={() => setIsEditing(false)}
          />
        )}

        {farm !== null && !isEditing && <FarmProfile farm={farm} onEdit={startEditing} />}

        {farm !== null && isEditing && (
          <FarmForm
            title="Edit Farm"
            submitLabel="Save changes"
            initialFarm={farm}
            onSubmit={(details) => handleUpdate(farm.id, details)}
            onCancel={() => setIsEditing(false)}
          />
        )}
      </div>
    </>
  )
}
