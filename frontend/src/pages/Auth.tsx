import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Sprout } from 'lucide-react'
import { supabase, useAuth } from '../features/auth/AuthProvider'
import { Alert } from '../components/ui'

const schema = z.object({ email: z.email('Enter a valid email address.'), password: z.string() })

/**
 * Translate the auth service's error code into an instruction the reader can
 * act on. The generic fallback is used only for codes we do not recognise.
 */
function authFailure(error: { code?: string; status?: number } | null, mode: string): string {
  const known: Record<string, string> = {
    email_address_invalid:
      'That email address was rejected. Use an address you can receive mail at.',
    email_exists: 'An account already exists for this email. Sign in instead.',
    user_already_exists: 'An account already exists for this email. Sign in instead.',
    weak_password: 'Choose a stronger password with at least 8 characters.',
    signup_disabled:
      'New accounts are disabled for this project. Ask the owner to enable sign-ups.',
    email_not_confirmed: 'Confirm your email address from the link we sent, then sign in.',
    invalid_credentials: 'Email or password is incorrect.',
    over_email_send_rate_limit: 'Too many emails were sent. Wait a few minutes and try again.',
    over_request_rate_limit: 'Too many attempts. Wait a moment and try again.',
    same_password: 'Choose a password you have not used for this account.',
  }
  const message = error?.code ? known[error.code] : undefined
  if (message) return message
  if (mode === 'login') return 'Could not sign in. Check your email and password, then try again.'
  if (mode === 'forgot-password') return 'Could not send a recovery link. Try again later.'
  return 'Could not create the account. Check your details or try again later.'
}
export function AuthPage({ mode }: { mode: 'login' | 'signup' | 'forgot-password' | 'callback' }) {
  const { session, loading, enterDemo } = useAuth()
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const location = useLocation()
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { password: '' },
  })
  const titles = {
    login: 'Welcome back.',
    signup: 'Give your search a home.',
    'forgot-password': 'Reset your password.',
    callback: 'Check your account.',
  }
  const submit = handleSubmit(async (values) => {
    setError('')
    setMessage('')
    if (!supabase) {
      setError('Account sign-in is not configured. You can explore the demo.')
      return
    }
    if (mode !== 'forgot-password' && values.password.length < (mode === 'signup' ? 8 : 1)) {
      setError(
        mode === 'signup' ? 'Use a password with at least 8 characters.' : 'Enter your password.',
      )
      return
    }
    try {
      const redirect = `${window.location.origin}/auth/callback`
      const result =
        mode === 'signup'
          ? await supabase.auth.signUp({ ...values, options: { emailRedirectTo: redirect } })
          : mode === 'forgot-password'
            ? await supabase.auth.resetPasswordForEmail(values.email, { redirectTo: redirect })
            : await supabase.auth.signInWithPassword(values)
      if (result.error) {
        setError(authFailure(result.error, mode))
        return
      }
      if (mode === 'signup' && 'session' in result.data && result.data.session) {
        // Some projects confirm the address automatically; the session is
        // already usable, so open the workspace instead of the inbox notice.
        navigate('/dashboard')
        return
      }
      if (mode === 'login') {
        const destination = location.state?.from
        navigate(
          typeof destination === 'string' &&
            destination.startsWith('/') &&
            !destination.startsWith('//')
            ? destination
            : '/dashboard',
        )
      } else
        setMessage(
          mode === 'signup'
            ? 'Check your inbox to verify your email before signing in.'
            : 'If an account exists for this email, a recovery link has been sent.',
        )
    } catch {
      setError('Cannot reach the sign-in service. Check your connection and try again.')
    }
  })
  const [password, setPassword] = useState('')
  return (
    <main className="auth-page">
      <Link to="/" className="brand">
        <span className="brand-symbol">
          <Sprout />
        </span>
        jobagent.
      </Link>
      <section className="auth-card">
        <h1>{titles[mode]}</h1>
        <p>
          {mode === 'login'
            ? 'Pick up where you left off.'
            : 'Your applications stay under your control.'}
        </p>
        {!supabase && mode !== 'callback' && (
          <Alert kind="error">
            Supabase is not configured. Add the project URL and publishable key to
            frontend/.env.local, then restart Vite.
          </Alert>
        )}
        {error && <Alert kind="error">{error}</Alert>}
        {message && <Alert kind="success">{message}</Alert>}
        {mode === 'callback' ? (
          <>
            {loading ? (
              <p role="status">Verifying your session…</p>
            ) : session ? (
              <>
                <Alert kind="success">Your account is connected.</Alert>
                <label>
                  New password
                  <input
                    type="password"
                    autoComplete="new-password"
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </label>
                <button
                  disabled={password.length < 8}
                  onClick={async () => {
                    const result = await supabase!.auth.updateUser({ password })
                    if (result.error)
                      setError('Could not update your password. Request a new recovery link.')
                    else {
                      setMessage('Password updated.')
                      setPassword('')
                    }
                  }}
                >
                  Update password
                </button>
                <Link className="button secondary" to="/dashboard">
                  Open workspace
                </Link>
              </>
            ) : (
              <Alert>
                Open the latest verification or recovery link from your email, or sign in to
                continue.
              </Alert>
            )}
            <Link to="/login">Back to sign in</Link>
          </>
        ) : (
          <form onSubmit={submit} noValidate>
            <label>
              Email
              <input
                {...register('email')}
                type="email"
                autoComplete="email"
                aria-invalid={Boolean(errors.email)}
                aria-describedby={errors.email ? 'email-error' : undefined}
              />
            </label>
            {errors.email && (
              <small className="field-error" id="email-error">
                {errors.email.message}
              </small>
            )}
            {mode !== 'forgot-password' && (
              <label>
                Password
                <input
                  {...register('password')}
                  type="password"
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                />
              </label>
            )}
            <button disabled={isSubmitting} type="submit">
              {isSubmitting
                ? 'Please wait…'
                : mode === 'login'
                  ? 'Sign in'
                  : mode === 'signup'
                    ? 'Create account'
                    : 'Send recovery link'}
            </button>
            {mode === 'login' && <Link to="/forgot-password">Forgot your password?</Link>}
            <p>
              {mode === 'signup' ? 'Already have an account?' : 'New here?'}{' '}
              <Link to={mode === 'signup' ? '/login' : '/signup'}>
                {mode === 'signup' ? 'Sign in' : 'Create account'}
              </Link>
            </p>
          </form>
        )}
        <div className="auth-demo">
          <button
            className="secondary"
            onClick={() => {
              enterDemo()
              navigate('/dashboard')
            }}
          >
            Explore with sample data
          </button>
          <small>The demo stores changes in memory for this visit.</small>
        </div>
      </section>
    </main>
  )
}
