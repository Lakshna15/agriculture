import { useId, type SelectHTMLAttributes } from 'react'
import { fieldControlClassName, fieldLabelClassName } from './fieldStyles.ts'

type SelectFieldProps = {
  label: string
  options: { value: string; label: string }[]
  /** Text of the empty first option, shown until the user makes a choice. */
  placeholder: string
} & Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id' | 'className' | 'children'>

export default function SelectField({
  label,
  options,
  placeholder,
  ...selectProps
}: SelectFieldProps) {
  const selectId = useId()

  return (
    <div>
      <label htmlFor={selectId} className={fieldLabelClassName}>
        {label}
      </label>
      <select id={selectId} className={fieldControlClassName} {...selectProps}>
        <option value="">{placeholder}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}
