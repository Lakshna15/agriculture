import { useId, type InputHTMLAttributes } from 'react'
import { fieldControlClassName, fieldHintClassName, fieldLabelClassName } from './fieldStyles.ts'

type TextFieldProps = {
  label: string
  hint?: string
} & Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'className'>

export default function TextField({ label, hint, ...inputProps }: TextFieldProps) {
  const inputId = useId()
  const hintId = useId()

  return (
    <div>
      <label htmlFor={inputId} className={fieldLabelClassName}>
        {label}
      </label>
      <input
        id={inputId}
        aria-describedby={hint ? hintId : undefined}
        className={fieldControlClassName}
        {...inputProps}
      />
      {hint && (
        <p id={hintId} className={fieldHintClassName}>
          {hint}
        </p>
      )}
    </div>
  )
}
