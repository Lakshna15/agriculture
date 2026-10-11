import { useState, type FormEvent } from 'react'
import { describeApiError } from '../../api/errors.ts'
import { reserveProduct, type ProductReservation } from '../../api/reservations.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import { todayAsIsoDate } from '../../lib/format.ts'
import { secondaryButtonClassName } from '../buttonStyles.ts'
import FormError from '../FormError.tsx'
import SubmitButton from '../SubmitButton.tsx'
import TextField from '../TextField.tsx'

const WHOLE_NUMBER_PATTERN = /^\d+$/
const DEFAULT_PICKUP_TIME = '10:00'

type ReserveProductFormProps = {
  productId: number
  unitLabel: string
  quantityAvailable: number
  onReserved: (reservation: ProductReservation) => void
  onCancel: () => void
}

export default function ReserveProductForm({
  productId,
  unitLabel,
  quantityAvailable,
  onReserved,
  onCancel,
}: ReserveProductFormProps) {
  const accessToken = useAccessToken()
  const today = todayAsIsoDate()
  const [quantityText, setQuantityText] = useState('1')
  const [pickupDate, setPickupDate] = useState(today)
  const [pickupTime, setPickupTime] = useState(DEFAULT_PICKUP_TIME)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const quantity = Number(quantityText)
    const isValidQuantity =
      WHOLE_NUMBER_PATTERN.test(quantityText.trim()) && quantity >= 1 && quantity <= quantityAvailable
    if (!isValidQuantity) {
      setErrorMessage(`Quantity must be a whole number between 1 and ${quantityAvailable}.`)
      return
    }
    // ISO dates compare correctly as text.
    if (pickupDate === '' || pickupDate < today) {
      setErrorMessage('Choose a pickup date that is today or later.')
      return
    }
    if (pickupTime === '') {
      setErrorMessage('Choose a pickup time.')
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      const reservation = await reserveProduct(accessToken, {
        product_id: productId,
        quantity,
        pickup_date: pickupDate,
        pickup_time: pickupTime,
      })
      onReserved(reservation)
    } catch (error) {
      setErrorMessage(describeApiError(error))
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 space-y-4 border-t border-stone-200 pt-4">
      <FormError message={errorMessage} />
      <div className="grid gap-4 sm:grid-cols-3">
        <TextField
          label={`Quantity (${unitLabel})`}
          name="quantity"
          inputMode="numeric"
          required
          hint={`Up to ${quantityAvailable}.`}
          value={quantityText}
          onChange={(event) => setQuantityText(event.target.value)}
        />
        <TextField
          label="Pickup date"
          name="pickup_date"
          type="date"
          required
          min={today}
          value={pickupDate}
          onChange={(event) => setPickupDate(event.target.value)}
        />
        <TextField
          label="Pickup time"
          name="pickup_time"
          type="time"
          required
          value={pickupTime}
          onChange={(event) => setPickupTime(event.target.value)}
        />
      </div>
      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className={secondaryButtonClassName}
        >
          Cancel
        </button>
        <div className="sm:w-48">
          <SubmitButton
            label="Confirm reservation"
            submittingLabel="Reserving…"
            isSubmitting={isSubmitting}
          />
        </div>
      </div>
    </form>
  )
}
