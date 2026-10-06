import { Link } from 'react-router'
import PlaceholderPage from '../components/PlaceholderPage.tsx'

export default function NotFoundPage() {
  return (
    <PlaceholderPage title="Page not found" description="The page you are looking for does not exist.">
      <Link to="/" className="text-sm font-medium text-green-800 underline underline-offset-4">
        Back to the homepage
      </Link>
    </PlaceholderPage>
  )
}
