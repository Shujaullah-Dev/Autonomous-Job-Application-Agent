import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { createClient, type Session } from '@supabase/supabase-js'
import { Navigate, useLocation } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useClock } from '../../lib/useClock'

const url = import.meta.env.VITE_SUPABASE_URL
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY
export const supabase =
  url && key
    ? createClient(url, key, {
        auth: {
          detectSessionInUrl: true,
          flowType: 'pkce',
          persistSession: true,
          autoRefreshToken: true,
        },
      })
    : null
type Auth = {
  session: Session | null
  loading: boolean
  demo: boolean
  enterDemo: () => void
  signOut: () => Promise<void>
}
const Context = createContext<Auth | null>(null)
export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(Boolean(supabase))
  const [demo, setDemo] = useState(false)
  const query = useQueryClient()
  useEffect(() => {
    if (!supabase) return
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      query.clear()
      setSession(next)
      setDemo(false)
      setLoading(false)
    })
    return () => data.subscription.unsubscribe()
  }, [query])
  useEffect(() => {
    if (!session?.expires_at) return
    const timer = setTimeout(
      () => {
        query.clear()
        setSession(null)
      },
      Math.max(0, session.expires_at * 1000 - Date.now()),
    )
    return () => clearTimeout(timer)
  }, [session, query])
  const signOut = async () => {
    if (supabase) await supabase.auth.signOut()
    query.clear()
    setSession(null)
    setDemo(false)
  }
  return (
    <Context.Provider
      value={{
        session,
        loading,
        demo,
        enterDemo: () => {
          query.clear()
          setDemo(true)
        },
        signOut,
      }}
    >
      {children}
    </Context.Provider>
  )
}
export function useAuth() {
  const auth = useContext(Context)
  if (!auth) throw new Error('Auth provider is missing')
  return auth
}
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { session, demo, loading } = useAuth()
  const location = useLocation()
  const now = useClock(1000)
  if (loading)
    return (
      <div role="status" className="loading">
        Checking your session…
      </div>
    )
  if (
    !demo &&
    (!session ||
      !session.user.email_confirmed_at ||
      !session.expires_at ||
      session.expires_at * 1000 <= now)
  )
    return <Navigate to="/login" state={{ from: location.pathname }} replace />
  return children
}
