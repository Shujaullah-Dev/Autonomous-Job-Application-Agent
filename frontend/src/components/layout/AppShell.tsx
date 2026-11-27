import { useState } from 'react'
import { NavLink, Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Search,
  ListChecks,
  Files,
  CalendarDays,
  Bell,
  UserRound,
  FileText,
  Settings,
  ArrowUpRight,
  Menu,
  X,
  LogOut,
  Sprout,
  Clock3,
} from 'lucide-react'
import { useAuth } from '../../features/auth/AuthProvider'
import { useWorkspace } from '../../app/workspace'
import { Alert } from '../ui'
import { useMedia } from '../../lib/useMedia'

const navigation = [
  ['/dashboard', 'Overview', LayoutDashboard],
  ['/jobs', 'Discover jobs', Search],
  ['/workflows', 'Shortlists', ListChecks],
  ['/applications', 'Applications', Files],
  ['/follow-ups', 'Follow-ups', Clock3],
  ['/interviews', 'Interviews', CalendarDays],
  ['/notifications', 'Notifications', Bell],
] as const
export function AppShell() {
  const [menu, setMenu] = useState(false)
  const desktop = useMedia('(min-width: 641px)')
  const { demo, signOut } = useAuth()
  const { state, reset, hasProfile, loading, error, refresh } = useWorkspace()
  const location = useLocation()
  const navigate = useNavigate()
  const unread = state.notifications.filter((n) => !n.read).length
  const initials = state.profile.full_name
    ? state.profile.full_name
        .split(' ')
        .map((part) => part[0])
        .join('')
        .slice(0, 2)
        .toUpperCase()
    : 'JA'
  const title =
    [
      ...navigation,
      ['/profile', 'Your profile', UserRound] as const,
      ['/resume', 'Resume review', FileText] as const,
      ['/settings', 'Settings', Settings] as const,
      ['/onboarding', 'Get started', Sprout] as const,
    ].find(([path]) => location.pathname.startsWith(path))?.[1] || 'Workspace'
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <button
        className="mobile-toggle icon-button"
        aria-label={menu ? 'Close navigation' : 'Open navigation'}
        aria-expanded={menu}
        onClick={() => setMenu(!menu)}
      >
        {menu ? <X /> : <Menu />}
      </button>
      {menu && (
        <button
          aria-label="Close navigation overlay"
          className="nav-overlay"
          onClick={() => setMenu(false)}
        />
      )}
      <aside
        className={`sidebar ${menu ? 'open' : ''}`}
        aria-label="Main navigation"
        inert={!desktop && !menu}
      >
        <Link className="brand" to="/">
          <span className="brand-symbol">
            <Sprout size={25} />
          </span>
          jobagent<span className="brand-dot">.</span>
        </Link>
        <div className="workspace-label">
          <span className="avatar small">{demo ? 'AM' : initials}</span>
          <span>
            Your workspace<small>{demo ? 'Demo account' : 'Signed in'}</small>
          </span>
        </div>
        <nav>
          {navigation.map(([path, label, Icon]) => (
            <NavLink onClick={() => setMenu(false)} key={path} to={path}>
              <Icon size={19} />
              <span>{label}</span>
              {path === '/notifications' && unread > 0 && (
                <span className="nav-count">{unread}</span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Sprout size={22} />
            <strong>Make your next move count.</strong>
            <p>You review the work. You decide when to apply.</p>
            <Link to="/resume" onClick={() => setMenu(false)}>
              Review your resume <ArrowUpRight size={15} />
            </Link>
          </div>
          <nav>
            <NavLink to="/profile" onClick={() => setMenu(false)}>
              <UserRound size={19} />
              Your profile
            </NavLink>
            <NavLink to="/settings" onClick={() => setMenu(false)}>
              <Settings size={19} />
              Settings
            </NavLink>
          </nav>
          <button
            className="signout"
            onClick={async () => {
              await signOut()
              reset()
              navigate('/')
            }}
          >
            <LogOut size={18} />
            Sign out
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="breadcrumb">Workspace</span>
            <span className="slash">/</span>
            {title}
          </div>
          <div className="topbar-right">
            <span className="connection">
              <span />
              {demo ? 'Demo workspace' : 'Account connected'}
            </span>
            <Link className="icon-button" aria-label="Open notifications" to="/notifications">
              <Bell size={20} />
              {unread > 0 && <i />}
            </Link>
            <Link className="avatar" aria-label="Open profile" to="/profile">
              {demo ? 'AM' : initials}
            </Link>
          </div>
        </header>
        <main id="main" className="main-content" tabIndex={-1} key={location.pathname}>
          {demo ? (
            <div className="demo-ribbon">
              <span>Demo mode</span> Fictional jobs and sample data. Changes last until you reload.
              No applications are sent.
            </div>
          ) : error ? (
            <Alert kind="error">
              {error}{' '}
              <button className="text-button" onClick={() => void refresh()}>
                Try again
              </button>
            </Alert>
          ) : !hasProfile && !loading ? (
            <Alert>
              Your workspace is connected, but no profile is saved yet.{' '}
              <Link to="/onboarding">Complete your profile</Link> to unlock shortlists,
              applications, follow-ups, and interviews.
            </Alert>
          ) : null}
          <Outlet />
        </main>
        <footer className="app-footer">
          A little structure for your next chapter.
          <span>Employer applications are always manual.</span>
        </footer>
      </div>
    </div>
  )
}
