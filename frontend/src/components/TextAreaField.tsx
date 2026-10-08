import { useId, type TextareaHTMLAttributes } from 'react'
import { fieldControlClassName, fieldHintClassName, fieldLabelClassName } from './fieldStyles.ts'

type TextAreaFieldProps = {
  label: string
  hint?: string
} & Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id' | 'className'>

export default function TextAreaField({ label, hint, ...textAreaProps }: TextAreaFieldProps) {
  const textAreaId = useId()
  const hintId = useId()

  return (
    <div>
      <label htmlFor={textAreaId} className={fieldLabelClassName}>
        {label}
      </label>
      <textarea
        id={textAreaId}
        aria-describedby={hint ? hintId : undefined}
        className={fieldControlClassName}
        {...textAreaProps}
      />
      {hint && (
        <p id={hintId} className={fieldHintClassName}>
          {hint}
        </p>
      )}
    </div>
  )
}
