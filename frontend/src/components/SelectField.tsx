import { useId, type SelectHTMLAttributes } from 'react'
import { fieldControlClassName, fieldLabelClassName } from './fieldStyles.ts'

type SelectFieldProps = {
  label: string
  options: { value: string; label: string }[]
  /** Text of an empty first option. Omit it when one of the options is always selected. */
  placeholder?: string
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
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}
