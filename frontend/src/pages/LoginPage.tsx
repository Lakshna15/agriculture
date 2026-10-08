import { useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { describeApiError } from '../api/errors.ts'
import { useAuth } from '../auth/useAuth.ts'
import FormCard from '../components/FormCard.tsx'
import FormError from '../components/FormError.tsx'
import SubmitButton from '../components/SubmitButton.tsx'
import TextField from '../components/TextField.tsx'

export default function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setErrorMessage(null)
    setIsSubmitting(true)
    try {
      // On success the session changes and the route redirects to the
      // dashboard, so there is nothing further to do here.
      await login(email, password)
    } catch (error) {
      setErrorMessage(describeApiError(error))
      setIsSubmitting(false)
    }
  }

  return (
    <FormCard title="Login" description="Welcome back. Sign in to your Farm2Local account.">
      <form onSubmit={handleSubmit} className="space-y-4">
        <FormError message={errorMessage} />
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
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <SubmitButton label="Login" submittingLabel="Signing in…" isSubmitting={isSubmitting} />
      </form>
      <p className="mt-6 text-center text-sm text-stone-600">
        Need an account?{' '}
        <Link to="/register" className="font-medium text-green-800 underline underline-offset-4">
          Register
        </Link>
      </p>
    </FormCard>
  )
}
