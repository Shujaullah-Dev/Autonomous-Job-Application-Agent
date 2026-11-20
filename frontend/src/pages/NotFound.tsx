import { Link } from 'react-router-dom'
import { EmptyState } from '../components/ui'
export function NotFound() {
  return (
    <main className="standalone">
      <EmptyState title="This page has moved off the map.">
        Check the address, or <Link to="/">return home</Link>.
      </EmptyState>
    </main>
  )
}
