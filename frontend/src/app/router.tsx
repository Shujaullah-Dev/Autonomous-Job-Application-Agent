import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Link, Outlet } from 'react-router-dom'
import { ProtectedRoute, useAuth } from '../features/auth/AuthProvider'
import { DemoProvider } from './store'
import { AppShell } from '../components/layout/AppShell'
import { Alert } from '../components/ui'
import { NotFound } from '../pages/NotFound'
import { Landing } from '../pages/Landing'
import { AuthPage } from '../pages/Auth'
const Dashboard = lazy(() => import('../pages/Dashboard').then((m) => ({ default: m.Dashboard })))
const Profile = lazy(() => import('../pages/Profile').then((m) => ({ default: m.Profile })))
const Resume = lazy(() => import('../pages/Resume').then((m) => ({ default: m.Resume })))
const Jobs = lazy(() => import('../pages/Jobs').then((m) => ({ default: m.Jobs })))
const JobDetail = lazy(() => import('../pages/Jobs').then((m) => ({ default: m.JobDetail })))
const Workflows = lazy(() => import('../pages/Workflows').then((m) => ({ default: m.Workflows })))
const Applications = lazy(() =>
  import('../pages/Applications').then((m) => ({ default: m.Applications })),
)
const ApplicationDetail = lazy(() =>
  import('../pages/Applications').then((m) => ({ default: m.ApplicationDetail })),
)
const FollowUps = lazy(() => import('../pages/FollowUps').then((m) => ({ default: m.FollowUps })))
const Interviews = lazy(() =>
  import('../pages/Interviews').then((m) => ({ default: m.Interviews })),
)
const Notifications = lazy(() =>
  import('../pages/Notifications').then((m) => ({ default: m.Notifications })),
)
const Settings = lazy(() => import('../pages/Settings').then((m) => ({ default: m.Settings })))

function DemoOnly({ children }: { children: ReactNode }) {
  const { demo } = useAuth()
  return demo ? (
    children
  ) : (
    <div className="blocked-page">
      <h1>Private workspace access is pending.</h1>
      <Alert>
        Sign-in is available, but the API does not yet verify account ownership for private records.
        These screens stay closed until that protection is ready.
      </Alert>
      <p>You can browse public jobs or sign out and explore the sample workspace.</p>
      <Link className="button" to="/jobs">
        Browse jobs
      </Link>
    </div>
  )
}
function ApiCandidatePage({ children }: { children: ReactNode }) {
  const { session, demo } = useAuth()
  return session && !demo && session.user.email_confirmed_at ? (
    children
  ) : (
    <DemoOnly>{children}</DemoOnly>
  )
}
function Workspace() {
  const { demo, session } = useAuth()
  return (
    <ProtectedRoute>
      <DemoProvider key={demo ? 'demo' : session?.user.id || 'guest'}>
        <Suspense
          fallback={
            <div className="loading" role="status">
              Loading workspace…
            </div>
          }
        >
          <AppShell />
        </Suspense>
      </DemoProvider>
    </ProtectedRoute>
  )
}
const privatePage = (page: ReactNode) => <DemoOnly>{page}</DemoOnly>
export const routes = [
  { path: '/', element: <Landing /> },
  { path: '/login', element: <AuthPage mode="login" /> },
  { path: '/signup', element: <AuthPage mode="signup" /> },
  { path: '/forgot-password', element: <AuthPage mode="forgot-password" /> },
  { path: '/auth/callback', element: <AuthPage mode="callback" /> },
  {
    element: <Workspace />,
    children: [
      { path: '/dashboard', element: privatePage(<Dashboard />) },
      {
        path: '/onboarding',
        element: (
          <ApiCandidatePage>
            <Profile onboarding />
          </ApiCandidatePage>
        ),
      },
      {
        path: '/profile',
        element: (
          <ApiCandidatePage>
            <Profile />
          </ApiCandidatePage>
        ),
      },
      {
        path: '/resume',
        element: (
          <ApiCandidatePage>
            <Resume />
          </ApiCandidatePage>
        ),
      },
      { path: '/jobs', element: <Jobs /> },
      { path: '/jobs/:jobId', element: <JobDetail /> },
      {
        path: '/workflows',
        element: privatePage(<Outlet />),
        children: [
          { index: true, element: <Workflows /> },
          { path: ':workflowId', element: <Workflows /> },
        ],
      },
      { path: '/applications', element: privatePage(<Applications />) },
      { path: '/applications/:applicationId', element: privatePage(<ApplicationDetail />) },
      { path: '/follow-ups', element: privatePage(<FollowUps />) },
      { path: '/interviews', element: privatePage(<Interviews />) },
      { path: '/interviews/:interviewId', element: privatePage(<Interviews />) },
      { path: '/notifications', element: privatePage(<Notifications />) },
      { path: '/settings', element: <Settings /> },
    ],
  },
  { path: '*', element: <NotFound /> },
]
export const router = createBrowserRouter(routes)
