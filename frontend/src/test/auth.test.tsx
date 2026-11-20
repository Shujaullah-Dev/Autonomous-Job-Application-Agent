import { act, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { beforeAll, afterAll, afterEach, describe, expect, it, vi } from 'vitest'
import type { Session } from '@supabase/supabase-js'

const mock = vi.hoisted(() => ({
  listener: null as null | ((event: string, session: Session | null) => void),
  signOut: vi.fn(async () => ({ error: null })),
}))
vi.mock('@supabase/supabase-js', () => ({
  createClient: () => ({
    auth: {
      onAuthStateChange: (callback: typeof mock.listener) => {
        mock.listener = callback
        return { data: { subscription: { unsubscribe: vi.fn() } } }
      },
      signOut: mock.signOut,
    },
  }),
}))
let auth: typeof import('../features/auth/AuthProvider')
beforeAll(async () => {
  vi.stubEnv('VITE_SUPABASE_URL', 'https://example.supabase.co')
  vi.stubEnv('VITE_SUPABASE_PUBLISHABLE_KEY', 'public-test-key')
  auth = await import('../features/auth/AuthProvider')
})
afterEach(() => vi.useRealTimers())
afterAll(() => vi.unstubAllEnvs())
const session = (id: string, verified = true) =>
  ({
    user: { id, email_confirmed_at: verified ? '2026-01-01' : undefined },
    expires_at: Math.floor(Date.now() / 1000) + 60,
  }) as Session
function mount() {
  const client = new QueryClient()
  function Probe() {
    const value = auth.useAuth()
    return (
      <>
        <span>{value.session?.user.id || 'No session'}</span>
        <button onClick={() => value.signOut()}>End session</button>
      </>
    )
  }
  render(
    <QueryClientProvider client={client}>
      <auth.AuthProvider>
        <MemoryRouter>
          <Probe />
          <Routes>
            <Route
              path="/"
              element={
                <auth.ProtectedRoute>
                  <p>Private workspace</p>
                </auth.ProtectedRoute>
              }
            />
            <Route path="/login" element={<p>Sign in screen</p>} />
          </Routes>
        </MemoryRouter>
      </auth.AuthProvider>
    </QueryClientProvider>,
  )
  return client
}
describe('configured auth session lifecycle with a mocked provider', () => {
  it('admits a verified session and clears cached data on user switch', () => {
    const client = mount()
    act(() => mock.listener!('SIGNED_IN', session('user-one')))
    expect(screen.getByText('Private workspace')).toBeVisible()
    client.setQueryData(['private'], { confidential: true })
    act(() => mock.listener!('SIGNED_IN', session('user-two')))
    expect(client.getQueryData(['private'])).toBeUndefined()
    expect(screen.getByText('user-two')).toBeVisible()
  })
  it('redirects an unverified account away from private screens', () => {
    mount()
    act(() => mock.listener!('SIGNED_IN', session('unverified', false)))
    expect(screen.queryByText('Private workspace')).not.toBeInTheDocument()
    expect(screen.getByText('Sign in screen')).toBeVisible()
  })
  it('expires the session and clears private cache at the token boundary', () => {
    vi.useFakeTimers()
    const client = mount()
    act(() => mock.listener!('SIGNED_IN', session('expires')))
    client.setQueryData(['private'], 'private-value')
    act(() => vi.advanceTimersByTime(61000))
    expect(screen.getByText('No session')).toBeVisible()
    expect(screen.getByText('Sign in screen')).toBeVisible()
    expect(client.getQueryData(['private'])).toBeUndefined()
  })
  it('clears the session on provider sign-out events', () => {
    const client = mount()
    act(() => mock.listener!('SIGNED_IN', session('signed-in')))
    client.setQueryData(['private'], 'private-value')
    act(() => mock.listener!('SIGNED_OUT', null))
    expect(screen.getByText('No session')).toBeVisible()
    expect(client.getQueryData(['private'])).toBeUndefined()
  })
})
