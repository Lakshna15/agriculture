import { useCallback, useState, type FormEvent } from 'react'
import {
  closeCropPoll,
  createCropPoll,
  fetchMyCropPolls,
  type CropPoll,
} from '../../api/cropPolls.ts'
import { describeApiError } from '../../api/errors.ts'
import { useAccessToken } from '../../auth/useAuth.ts'
import { primaryButtonClassName, secondaryButtonClassName } from '../../components/buttonStyles.ts'
import FormError from '../../components/FormError.tsx'
import PollResults from '../../components/poll/PollResults.tsx'
import SubmitButton from '../../components/SubmitButton.tsx'
import TextField from '../../components/TextField.tsx'
import { useAsyncData } from '../../lib/useAsyncData.ts'

const DEFAULT_QUESTION = 'What should I grow next?'
const MIN_OPTIONS = 2
const MAX_OPTIONS = 8
const INITIAL_OPTION_COUNT = 3

type CropPollFormProps = {
  onSubmit: (question: string, options: string[]) => Promise<void>
  onCancel: () => void
}

function CropPollForm({ onSubmit, onCancel }: CropPollFormProps) {
  const [question, setQuestion] = useState(DEFAULT_QUESTION)
  const [options, setOptions] = useState<string[]>(() => Array(INITIAL_OPTION_COUNT).fill(''))
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  function setOption(index: number, value: string) {
    setOptions((current) => current.map((option, position) => (position === index ? value : option)))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    // Empty rows are left out, so a farmer need not fill every box.
    const crops = options.map((option) => option.trim()).filter((option) => option !== '')
    if (question.trim() === '') {
      setErrorMessage('Enter the question you want to ask.')
      return
    }
    if (crops.length < MIN_OPTIONS) {
      setErrorMessage(`Give customers at least ${MIN_OPTIONS} crops to choose between.`)
      return
    }
    const distinctCrops = new Set(crops.map((crop) => crop.toLowerCase().replace(/\s+/g, ' ')))
    if (distinctCrops.size !== crops.length) {
      setErrorMessage('Each crop can appear only once.')
      return
    }

    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      await onSubmit(question.trim(), crops)
    } catch (error) {
      setErrorMessage(describeApiError(error))
      setIsSubmitting(false)
    }
  }

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm sm:p-8">
      <h3 className="text-lg font-semibold tracking-tight text-stone-900">Create Crop Poll</h3>
      <form onSubmit={handleSubmit} className="mt-6 space-y-5">
        <FormError message={errorMessage} />
        <TextField
          label="Question"
          name="question"
          required
          maxLength={200}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <fieldset>
          <legend className="text-sm font-medium text-stone-800">Crops to choose between</legend>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            {options.map((option, index) => (
              <TextField
                // The rows have no identity of their own beyond their position.
                key={index}
                label={`Crop ${index + 1}`}
                name={`option-${index + 1}`}
                maxLength={80}
                value={option}
                onChange={(event) => setOption(index, event.target.value)}
              />
            ))}
          </div>
          {options.length < MAX_OPTIONS && (
            <button
              type="button"
              onClick={() => setOptions((current) => [...current, ''])}
              className={`mt-3 ${secondaryButtonClassName}`}
            >
              Add another crop
            </button>
          )}
        </fieldset>
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
            <SubmitButton label="Create poll" submittingLabel="Saving…" isSubmitting={isSubmitting} />
          </div>
        </div>
      </form>
    </section>
  )
}

/** The farmer's polls asking customers what to grow next, with the votes so far. */
export default function FarmCropPollsPage() {
  const accessToken = useAccessToken()
  const loadPolls = useCallback(() => fetchMyCropPolls(accessToken), [accessToken])
  const { state, reload, updateData } = useAsyncData(loadPolls)
  const [isCreating, setIsCreating] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [pollError, setPollError] = useState<string | null>(null)

  async function handleCreate(question: string, options: string[]) {
    const poll = await createCropPoll(accessToken, { question, options })
    updateData((polls) => [poll, ...polls])
    setIsCreating(false)
    setNotice('Your poll is open. Nearby customers can now vote.')
  }

  async function handleClose(poll: CropPoll) {
    setPollError(null)
    try {
      const closedPoll = await closeCropPoll(accessToken, poll.id)
      updateData((polls) =>
        polls.map((current) => (current.id === closedPoll.id ? closedPoll : current)),
      )
    } catch (error) {
      setPollError(describeApiError(error))
    }
  }

  function startCreating() {
    setNotice(null)
    setIsCreating(true)
  }

  return (
    <section aria-labelledby="crop-polls-heading">
      <div className="flex items-center justify-between gap-4">
        <h2 id="crop-polls-heading" className="text-xl font-semibold tracking-tight text-stone-900">
          Crop polls
        </h2>
        {state.status === 'loaded' && !isCreating && (
          <button type="button" onClick={startCreating} className={primaryButtonClassName}>
            Create Crop Poll
          </button>
        )}
      </div>
      <p className="mt-1 text-sm text-stone-600">
        Ask nearby customers what you should grow next. You see how many votes each crop gets,
        not who cast them.
      </p>

      <div className="mt-4 space-y-4">
        {notice && (
          <p
            role="status"
            className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-900"
          >
            {notice}
          </p>
        )}
        {pollError && (
          <p role="alert" className="text-sm text-red-800">
            {pollError}
          </p>
        )}

        {isCreating && <CropPollForm onSubmit={handleCreate} onCancel={() => setIsCreating(false)} />}

        {state.status === 'loading' && (
          <p role="status" className="text-stone-600">
            Loading your polls…
          </p>
        )}

        {state.status === 'failed' && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4">
            <p role="alert" className="text-sm text-red-800">
              Your polls could not be loaded. {state.message}
            </p>
            <button type="button" onClick={reload} className={`mt-3 ${primaryButtonClassName}`}>
              Try again
            </button>
          </div>
        )}

        {state.status === 'loaded' && state.data.length === 0 && !isCreating && (
          <p className="rounded-xl border border-dashed border-stone-300 bg-white p-6 text-center text-sm text-stone-600">
            You have not created any polls yet. A poll is a quick way to find out which crop
            your neighbors would like before you commit to growing it.
          </p>
        )}

        {state.status === 'loaded' && state.data.length > 0 && (
          <ul className="space-y-3">
            {state.data.map((poll) => (
              <li key={poll.id} className="rounded-lg border border-stone-200 bg-white p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-semibold text-stone-900">{poll.question}</h3>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      poll.status === 'OPEN'
                        ? 'bg-green-100 text-green-900'
                        : 'bg-stone-200 text-stone-700'
                    }`}
                  >
                    {poll.status === 'OPEN' ? 'Open' : 'Closed'}
                  </span>
                </div>
                <p className="mt-1 text-sm text-stone-600">
                  {poll.total_votes} {poll.total_votes === 1 ? 'vote' : 'votes'} in total
                </p>
                <div className="mt-3 sm:w-96">
                  <PollResults poll={poll} />
                </div>
                {poll.status === 'OPEN' && (
                  <button
                    type="button"
                    aria-label={`Close poll: ${poll.question}`}
                    onClick={() => void handleClose(poll)}
                    className={`mt-4 ${secondaryButtonClassName}`}
                  >
                    Close poll
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
