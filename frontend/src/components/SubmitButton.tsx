type SubmitButtonProps = {
  label: string
  submittingLabel: string
  isSubmitting: boolean
}

export default function SubmitButton({ label, submittingLabel, isSubmitting }: SubmitButtonProps) {
  return (
    <button
      type="submit"
      disabled={isSubmitting}
      className="w-full rounded-md bg-green-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-green-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-700 disabled:cursor-not-allowed disabled:bg-green-700/60"
    >
      {isSubmitting ? submittingLabel : label}
    </button>
  )
}
