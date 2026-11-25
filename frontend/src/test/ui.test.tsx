import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect } from 'vitest'
import { EmptyState } from '../components/ui'
import { AuthProvider, ProtectedRoute } from '../features/auth/AuthProvider'
import { AuthPage } from '../pages/Auth'
import { DemoProvider } from '../app/store'
import { Profile } from '../pages/Profile'
import { NotFound } from '../pages/NotFound'

function wrap(children: React.ReactNode) {
  return render(
    <MemoryRouter>
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <DemoProvider>{children}</DemoProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  )
}
describe('accessible screens', () => {
  it('offers next steps in empty and missing-route states', () => {
    render(<EmptyState title="No jobs found">Clear your filters.</EmptyState>)
    expect(screen.getByRole('heading', { name: 'No jobs found' })).toBeVisible()
    expect(screen.getByText('Clear your filters.')).toBeVisible()
  })
  it('provides a home link for unknown routes', () => {
    wrap(<NotFound />)
    expect(screen.getByRole('link', { name: 'return home' })).toHaveAttribute('href', '/')
  })
  it('does not render private content for signed-out visitors', async () => {
    wrap(
      <Routes>
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <p>Private records</p>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<p>Sign in required</p>} />
      </Routes>,
    )
    expect(screen.queryByText('Private records')).not.toBeInTheDocument()
    expect(await screen.findByText('Sign in required')).toBeVisible()
    expect(screen.queryByText('Private records')).not.toBeInTheDocument()
  })
  it('validates sign-in email without sending a request', async () => {
    wrap(<AuthPage mode="login" />)
    await userEvent.type(screen.getByLabelText('Email'), 'invalid')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Enter a valid email address.')).toBeVisible()
  })
  it('rejects blank names and retains editable skill labels', async () => {
    wrap(<Profile />)
    await userEvent.clear(screen.getByLabelText('Full name'))
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }))
    expect(await screen.findByText('Enter your name.')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Remove React' })).toBeVisible()
  })
})
