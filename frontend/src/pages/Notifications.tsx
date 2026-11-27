import { useState } from 'react'
import { Check, RefreshCw } from 'lucide-react'
import { useWorkspace } from '../app/workspace'
import { useClock } from '../lib/useClock'
import { Alert, Badge, EmptyState, Skeleton } from '../components/ui'

export function Notifications() {
  const { state, demo, loading, live, refreshNotifications, readNotification } = useWorkspace()
  const [message, setMessage] = useState('')
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState('unread')
  const now = useClock(1000)
  const scheduled = state.interviews
    .filter((i) => i.status === 'scheduled')
    .flatMap((i) =>
      i.reminders.map((m) => ({
        id: `${i.id}:${i.version}:${m}`,
        title: i.title,
        at: new Date(new Date(i.start).getTime() - m * 60000).toISOString(),
        start: i.start,
      })),
    )
  async function process() {
    setBusy(true)
    try {
      const result = await refreshNotifications()
      setFailed(false)
      setMessage(result)
    } catch (e) {
      setFailed(true)
      setMessage((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  async function markRead(notificationId: string) {
    try {
      await readNotification(notificationId)
      setFailed(false)
      setMessage('Reminder marked as read.')
    } catch (e) {
      setFailed(true)
      setMessage((e as Error).message)
    }
  }
  const available = state.notifications.filter((n) => tab === 'all' || !n.read)
  const future = scheduled.filter(
    (n) => new Date(n.at).getTime() > now && !state.notifications.some((row) => row.id === n.id),
  )
  if (live && loading && !state.interviews.length) return <Skeleton />
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>A heads-up, in one place.</h1>
          <p>In-app interview reminders. No email or push notifications are sent.</p>
        </div>
        <button className="secondary" disabled={busy} onClick={process}>
          <RefreshCw size={17} />
          {busy ? 'Checking…' : 'Check for due reminders'}
        </button>
      </div>
      <Alert>
        {demo
          ? 'This button simulates the reminder processor for sample data.'
          : 'The server’s reminder processor releases due items. This check asks the API to run it now.'}
      </Alert>
      {message && <Alert kind={failed ? 'error' : 'success'}>{message}</Alert>}
      <div className="tabs">
        <button
          aria-pressed={tab === 'unread'}
          className={tab === 'unread' ? 'active' : ''}
          onClick={() => setTab('unread')}
        >
          Unread
        </button>
        <button
          aria-pressed={tab === 'all'}
          className={tab === 'all' ? 'active' : ''}
          onClick={() => setTab('all')}
        >
          All available
        </button>
      </div>
      <section className="panel table-panel">
        {available.length ? (
          available.map((n) => (
            <div className="list-row" key={n.id}>
              <span className="notification-dot" />
              <div className="grow">
                <strong>{n.title}</strong>
                <small>Reminder due {new Date(n.at).toLocaleString()}</small>
              </div>
              <Badge>{n.read ? 'Read' : 'Available'}</Badge>
              {!n.read && (
                <button className="secondary" onClick={() => markRead(n.id)}>
                  <Check size={16} />
                  Mark read
                </button>
              )}
            </div>
          ))
        ) : (
          <EmptyState title="You’re caught up">
            Available interview reminders will appear here when they are due and processed.
          </EmptyState>
        )}
      </section>
      <section className="panel table-panel">
        <h2>Scheduled for later</h2>
        {future.map((n) => (
          <div className="list-row" key={n.id}>
            <div className="grow">
              <strong>{n.title}</strong>
              <small>{new Date(n.at).toLocaleString()}</small>
            </div>
            <Badge>Scheduled</Badge>
          </div>
        ))}
        {!future.length && (
          <p className="muted">No future reminders. Add reminders when scheduling an interview.</p>
        )}
      </section>
    </>
  )
}
