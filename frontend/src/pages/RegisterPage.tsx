import { Link } from 'react-router'
import PlaceholderPage from '../components/PlaceholderPage.tsx'

export default function RegisterPage() {
  return (
    <PlaceholderPage title="Register" description="Account registration is not available yet.">
      <Link to="/login" className="text-sm font-medium text-green-800 underline underline-offset-4">
        Already have an account? Login
      </Link>
    </PlaceholderPage>
  )
}
