import { useState, type FormEvent } from 'react'
import type { CropStage, NewCropUpdate } from '../../api/cropJourney.ts'
import { describeApiError } from '../../api/errors.ts'
import FormError from '../FormError.tsx'
import SelectField from '../SelectField.tsx'
import SubmitButton from '../SubmitButton.tsx'
import TextAreaField from '../TextAreaField.tsx'
import TextField from '../TextField.tsx'

type CropUpdateFormProps = {
  /** The stages the farmer may choose now. The first is selected to begin with. */
  stageOptions: { value: CropStage; label: string }[]
  onSubmit: (update: NewCropUpdate) => Promise<void>
}

export default function CropUpdateForm({ stageOptions, onSubmit }: CropUpdateFormProps) {
  const [stage, setStage] = useState<CropStage>(stageOptions[0].value)
  const [message, setMessage] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (message.trim() === '') {
      setErrorMessage('Write a short message about how the crop is doing.')
      return
    }
    const trimmedImageUrl = imageUrl.trim()
    if (trimmedImageUrl !== '' && !trimmedImageUrl.startsWith('https://')) {
      setErrorMessage('The photo link must start with https://')
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      await onSubmit({ stage, message: message.trim(), image_url: trimmedImageUrl || null })
      setMessage('')
      setImageUrl('')
    } catch (error) {
      setErrorMessage(describeApiError(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <FormError message={errorMessage} />
      <div className="sm:w-64">
        <SelectField
          label="Stage"
          name="stage"
          options={stageOptions}
          value={stage}
          onChange={(event) => setStage(event.target.value as CropStage)}
        />
      </div>
      <TextAreaField
        label="Message"
        name="message"
        rows={3}
        maxLength={2000}
        required
        hint="Everyone committed to this crop is notified."
        value={message}
        onChange={(event) => setMessage(event.target.value)}
      />
      <TextField
        label="Photo link"
        name="image_url"
        type="url"
        maxLength={500}
        placeholder="https://"
        hint="Optional. An https link to a photo hosted elsewhere."
        value={imageUrl}
        onChange={(event) => setImageUrl(event.target.value)}
      />
      <div className="sm:w-48">
        <SubmitButton label="Post Crop Update" submittingLabel="Posting…" isSubmitting={isSubmitting} />
      </div>
    </form>
  )
}
