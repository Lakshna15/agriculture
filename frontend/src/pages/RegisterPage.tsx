import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import type { RegistrableRole } from '../api/auth.ts'
import { describeApiError } from '../api/errors.ts'
import { useAuth } from '../auth/useAuth.ts'
import FormCard from '../components/FormCard.tsx'
import FormError from '../components/FormError.tsx'
import SubmitButton from '../components/SubmitButton.tsx'
import TextField from '../components/TextField.tsx'

const PASSWORD_MIN_LENGTH = 8

const roleOptions: { role: RegistrableRole; label: string; description: string }[] = [
  { role: 'CUSTOMER', label: 'Customer', description: 'I want to buy from nearby farms.' },
  { role: 'FARMER', label: 'Farmer', description: 'I want to sell what my farm grows.' },
]

export default function RegisterPage() {
  const { register } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<RegistrableRole>('CUSTOMER')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      // On success the new user is signed in and the route redirects to the
      // dashboard for the chosen role.
      await register({ name, email, password, role })
    } catch (error) {
      setErrorMessage(describeApiError(error))
      setIsSubmitting(false)
    }
  }

  return (
    <FormCard
      title="Register"
      description="Create an account to buy from local farms or to sell your own produce."
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormError message={errorMessage} />
        <TextField
          label="Name"
          type="text"
          name="name"
          autoComplete="name"
          required
          maxLength={100}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <TextField
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <TextField
          label="Password"
          type="password"
          name="password"
          autoComplete="new-password"
          required
          minLength={PASSWORD_MIN_LENGTH}
          hint={`At least ${PASSWORD_MIN_LENGTH} characters.`}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <fieldset>
          <legend className="text-sm font-medium text-stone-800">Role</legend>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {roleOptions.map((option) => (
              <label
                key={option.role}
                className="flex cursor-pointer gap-3 rounded-md border border-stone-300 p-3 has-checked:border-green-700 has-checked:bg-green-50"
              >
                <input
                  type="radio"
                  name="role"
                  value={option.role}
                  checked={role === option.role}
                  onChange={() => setRole(option.role)}
                  className="mt-1 accent-green-700"
                />
                <span>
                  <span className="block text-sm font-medium text-stone-900">{option.label}</span>
                  <span className="block text-xs text-stone-600">{option.description}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <SubmitButton
          label="Create account"
          submittingLabel="Creating account…"
          isSubmitting={isSubmitting}
        />
      </form>
      <p className="mt-6 text-center text-sm text-stone-600">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-green-800 underline underline-offset-4">
          Login
        </Link>
      </p>
    </FormCard>
  )
}
