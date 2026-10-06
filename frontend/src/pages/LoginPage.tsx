import { Link } from 'react-router'
import PlaceholderPage from '../components/PlaceholderPage.tsx'

export default function LoginPage() {
  return (
    <PlaceholderPage title="Login" description="Signing in is not available yet.">
      <Link to="/register" className="text-sm font-medium text-green-800 underline underline-offset-4">
        Need an account? Register
      </Link>
    </PlaceholderPage>
  )
}
