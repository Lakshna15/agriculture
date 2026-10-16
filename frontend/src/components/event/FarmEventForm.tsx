import { useState, type FormEvent } from 'react'
import { describeApiError } from '../../api/errors.ts'
import type { FarmEventType, NewFarmEvent } from '../../api/events.ts'
import { farmEventTypeOptions } from '../../data/eventOptions.ts'
import { todayAsIsoDate } from '../../lib/format.ts'
import { PRICE_PATTERN, WHOLE_NUMBER_PATTERN } from '../../lib/numberInput.ts'
import { secondaryButtonClassName } from '../buttonStyles.ts'
import FormError from '../FormError.tsx'
import SelectField from '../SelectField.tsx'
import SubmitButton from '../SubmitButton.tsx'
import TextAreaField from '../TextAreaField.tsx'
import TextField from '../TextField.tsx'

/** Form state. Numbers stay as text while the user is typing them. */
type FarmEventFormValues = {
  title: string
  eventType: FarmEventType | ''
  description: string
  eventDate: string
  startTime: string
  endTime: string
  price: string
  capacity: string
}

/** Returns a message for the first problem found, or null when the values can be sent. */
function findProblem(values: FarmEventFormValues, today: string): string | null {
  // ISO dates and 24-hour times compare correctly as text.
  if (values.eventDate === '' || values.eventDate < today) {
    return 'Choose an event date that is today or later.'
  }
  if (values.startTime === '' || values.endTime === '' || values.endTime <= values.startTime) {
    return 'The end time must be after the start time.'
  }
  if (!PRICE_PATTERN.test(values.price.trim())) {
    return 'Price must be zero or more with at most two decimal places, for example 12.00.'
  }
  if (!WHOLE_NUMBER_PATTERN.test(values.capacity.trim()) || Number(values.capacity) < 1) {
    return 'Capacity must be a whole number of at least 1.'
  }
  return null
}

type FarmEventFormProps = {
  onSubmit: (event: NewFarmEvent) => Promise<void>
  onCancel: () => void
}

export default function FarmEventForm({ onSubmit, onCancel }: FarmEventFormProps) {
  const today = todayAsIsoDate()
  const [values, setValues] = useState<FarmEventFormValues>({
    title: '',
    eventType: '',
    description: '',
    eventDate: '',
    startTime: '09:00',
    endTime: '12:00',
    price: '',
    capacity: '',
  })
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function setValue<Field extends keyof FarmEventFormValues>(
    field: Field,
    value: FarmEventFormValues[Field],
  ) {
    setValues((current) => ({ ...current, [field]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const problem = findProblem(values, today)
    if (problem !== null || values.eventType === '') {
      setErrorMessage(problem ?? 'Choose a type of event.')
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      await onSubmit({
        title: values.title.trim(),
        description: values.description.trim() || null,
        event_type: values.eventType,
        event_date: values.eventDate,
        start_time: values.startTime,
        end_time: values.endTime,
        price: values.price.trim(),
        capacity: Number(values.capacity),
      })
    } catch (error) {
      setErrorMessage(describeApiError(error))
      setIsSubmitting(false)
    }
  }

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8">
      <h3 className="text-lg font-semibold tracking-tight text-stone-900">Create Farm Event</h3>
      <form onSubmit={handleSubmit} className="mt-6 space-y-5">
        <FormError message={errorMessage} />

        <div className="grid gap-5 sm:grid-cols-2">
          <TextField
            label="Event title"
            name="title"
            required
            maxLength={120}
            value={values.title}
            onChange={(event) => setValue('title', event.target.value)}
          />
          <SelectField
            label="Type of event"
            name="event_type"
            required
            placeholder="Select a type"
            options={farmEventTypeOptions}
            value={values.eventType}
            onChange={(event) => setValue('eventType', event.target.value as FarmEventType | '')}
          />
        </div>

        <TextAreaField
          label="Description"
          name="description"
          rows={2}
          maxLength={2000}
          hint="Optional. Tell visitors what to expect and what to bring."
          value={values.description}
          onChange={(event) => setValue('description', event.target.value)}
        />

        <div className="grid gap-5 sm:grid-cols-3">
          <TextField
            label="Event date"
            name="event_date"
            type="date"
            required
            min={today}
            value={values.eventDate}
            onChange={(event) => setValue('eventDate', event.target.value)}
          />
          <TextField
            label="Start time"
            name="start_time"
            type="time"
            required
            value={values.startTime}
            onChange={(event) => setValue('startTime', event.target.value)}
          />
          <TextField
            label="End time"
            name="end_time"
            type="time"
            required
            value={values.endTime}
            onChange={(event) => setValue('endTime', event.target.value)}
          />
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <TextField
            label="Price per person"
            name="price"
            inputMode="decimal"
            required
            hint="In dollars. Enter 0 for a free event."
            value={values.price}
            onChange={(event) => setValue('price', event.target.value)}
          />
          <TextField
            label="Capacity"
            name="capacity"
            inputMode="numeric"
            required
            hint="The most people you can host in total."
            value={values.capacity}
            onChange={(event) => setValue('capacity', event.target.value)}
          />
        </div>

        <div className="flex flex-col-reverse gap-3 pt-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className={secondaryButtonClassName}
          >
            Cancel
          </button>
          <div className="sm:w-44">
            <SubmitButton label="Create event" submittingLabel="Saving…" isSubmitting={isSubmitting} />
          </div>
        </div>
      </form>
    </section>
  )
}
