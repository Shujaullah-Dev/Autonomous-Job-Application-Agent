import { useState } from 'react'
import { Check, RefreshCw } from 'lucide-react'
import { useDemo } from '../app/store'
import { useClock } from '../lib/useClock'
import { Alert, Badge, EmptyState } from '../components/ui'

export function Notifications() {
  const { state, setState } = useDemo()
  const [message, setMessage] = useState('')
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
  function process() {
    const due = scheduled.filter(
      (n) =>
        new Date(n.at).getTime() <= now &&
        new Date(n.start).getTime() >= now &&
        !state.notifications.some((row) => row.id === n.id),
    )
    setState((s) => ({
      ...s,
      notifications: [
        ...s.notifications,
        ...due.map((n) => ({ id: n.id, title: n.title, at: n.at, read: false })),
      ],
    }))
    setMessage(
      due.length
        ? `${due.length} due reminder${due.length === 1 ? '' : 's'} made available in this demo.`
        : 'No new reminders are due. Future reminders stay scheduled.',
    )
  }
  const visible = state.notifications
    .filter((n) => scheduled.some((s) => s.id === n.id && new Date(s.start).getTime() >= now))
    .filter((n) => tab === 'all' || !n.read)
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>A heads-up, in one place.</h1>
          <p>In-app interview reminders. No email or push notifications are sent.</p>
        </div>
        <button className="secondary" onClick={process}>
          <RefreshCw size={17} />
          Check due demo reminders
        </button>
      </div>
      <Alert>
        In live use, the server’s reminder processor must run before due items appear. This button
        simulates that step for sample data only.
      </Alert>
      {message && <Alert kind="success">{message}</Alert>}
      <div className="tabs">
        <button className={tab === 'unread' ? 'active' : ''} onClick={() => setTab('unread')}>
          Unread
        </button>
        <button className={tab === 'all' ? 'active' : ''} onClick={() => setTab('all')}>
          All available
        </button>
      </div>
      <section className="panel table-panel">
        {visible.length ? (
          visible.map((n) => (
            <div className="list-row" key={n.id}>
              <span className="notification-dot" />
              <div className="grow">
                <strong>{n.title}</strong>
                <small>Reminder due {new Date(n.at).toLocaleString()}</small>
              </div>
              <Badge>{n.read ? 'Read' : 'Available'}</Badge>
              {!n.read && (
                <button
                  className="secondary"
                  onClick={() =>
                    setState((s) => ({
                      ...s,
                      notifications: s.notifications.map((row) =>
                        row.id === n.id ? { ...row, read: true } : row,
                      ),
                    }))
                  }
                >
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
        {scheduled
          .filter((n) => new Date(n.at).getTime() > now)
          .map((n) => (
            <div className="list-row" key={n.id}>
              <div className="grow">
                <strong>{n.title}</strong>
                <small>{new Date(n.at).toLocaleString()}</small>
              </div>
              <Badge>Scheduled</Badge>
            </div>
          ))}
        {!scheduled.some((n) => new Date(n.at).getTime() > now) && (
          <p className="muted">No future reminders. Add reminders when scheduling an interview.</p>
        )}
      </section>
    </>
  )
}
