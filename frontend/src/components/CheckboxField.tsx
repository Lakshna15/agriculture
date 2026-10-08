type CheckboxFieldProps = {
  label: string
  description?: string
  checked: boolean
  onChange: (checked: boolean) => void
}

export default function CheckboxField({
  label,
  description,
  checked,
  onChange,
}: CheckboxFieldProps) {
  return (
    <label className="flex cursor-pointer gap-3 rounded-md border border-stone-300 p-3 has-checked:border-green-700 has-checked:bg-green-50">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1 accent-green-700"
      />
      <span>
        <span className="block text-sm font-medium text-stone-900">{label}</span>
        {description && <span className="block text-xs text-stone-600">{description}</span>}
      </span>
    </label>
  )
}
