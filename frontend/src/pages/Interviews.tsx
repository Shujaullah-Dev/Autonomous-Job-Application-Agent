import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Plus, CalendarDays, Download } from 'lucide-react'
import { useDemo } from '../app/store'
import { interviewConflict, type Interview } from '../lib/demo'
import { downloadCalendar, localInput } from '../lib/calendar'
import { safeUrl } from '../lib/api'
import { Alert, Badge, EmptyState, Modal } from '../components/ui'

const blank = {
  applicationId: '',
  title: '',
  start: '',
  end: '',
  mode: 'video' as Interview['mode'],
  location: '',
}
export function Interviews() {
  const { state, setState } = useDemo()
  const { interviewId } = useParams()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Interview | null>(null)
  const [form, setForm] = useState(blank)
  const [reminders, setReminders] = useState<number[]>([1440, 60])
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [action, setAction] = useState<{
    interview: Interview
    status: 'cancelled' | 'completed'
  } | null>(null)
  const [view, setView] = useState('list')
  const eligible = state.applications.filter((a) => ['submitted', 'interview'].includes(a.status))
  const rows = state.interviews
    .filter((i) => !interviewId || i.id === interviewId)
    .sort((a, b) => a.start.localeCompare(b.start))
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
  function schedule(i?: Interview) {
    setEditing(i || null)
    setForm(i ? { ...i, start: localInput(i.start), end: localInput(i.end) } : blank)
    setReminders(i?.reminders || [1440, 60])
    setError('')
    setOpen(true)
  }
  function save() {
    const start = new Date(form.start),
      end = new Date(form.end)
    if (
      !form.title.trim() ||
      !form.applicationId ||
      !Number.isFinite(start.getTime()) ||
      !Number.isFinite(end.getTime()) ||
      end <= start
    ) {
      setError('Choose an application, a title, and an end time after the start.')
      return
    }
    if (interviewConflict(state.interviews, start.toISOString(), end.toISOString(), editing?.id)) {
      setError('This overlaps another scheduled interview. Choose another time.')
      return
    }
    if (editing && state.interviews.find((i) => i.id === editing.id)?.version !== editing.version) {
      setError('This interview changed. Close this dialog and reload its details.')
      return
    }
    const next: Interview = {
      ...form,
      title: form.title.trim(),
      id: editing?.id || crypto.randomUUID(),
      start: start.toISOString(),
      end: end.toISOString(),
      status: 'scheduled',
      version: (editing?.version || 0) + 1,
      reminders,
    }
    setState((s) => ({
      ...s,
      interviews: editing
        ? s.interviews.map((i) => (i.id === editing.id ? next : i))
        : [...s.interviews, next],
    }))
    setMessage(
      editing ? 'Interview rescheduled.' : 'Interview scheduled. Reminders are in-app only.',
    )
    setOpen(false)
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Make space for the conversation.</h1>
          <p>Interview times are shown in {timezone}.</p>
        </div>
        <button onClick={() => schedule()}>
          <Plus size={17} />
          Schedule interview
        </button>
      </div>
      {message && <Alert kind="success">{message}</Alert>}
      <div className="tabs">
        <button
          aria-pressed={view === 'list'}
          className={view === 'list' ? 'active' : ''}
          onClick={() => setView('list')}
        >
          List
        </button>
        <button
          aria-pressed={view === 'calendar'}
          className={view === 'calendar' ? 'active' : ''}
          onClick={() => setView('calendar')}
        >
          Date agenda
        </button>
      </div>
      <Alert>
        Reminders appear in the app. Live reminders become available only after the server processor
        runs. The demo has a manual due-reminder check in Notifications.
      </Alert>
      {rows.length ? (
        <div className={view === 'calendar' ? 'agenda' : ''}>
          {rows.map((i) => (
            <section className="panel interview-card" key={i.id}>
              {view === 'calendar' && (
                <div className="agenda-date">
                  <strong>{new Date(i.start).getDate()}</strong>
                  <span>{new Date(i.start).toLocaleDateString(undefined, { month: 'short' })}</span>
                </div>
              )}
              <div className="grow">
                <div className="section-heading">
                  <h2>
                    <Link to={`/interviews/${i.id}`}>{i.title}</Link>
                  </h2>
                  <Badge status={i.status}>{i.status}</Badge>
                </div>
                <p>
                  <CalendarDays size={17} />
                  {new Date(i.start).toLocaleString()} –{' '}
                  {new Date(i.end).toLocaleTimeString(undefined, {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
                <p>
                  {i.mode} ·{' '}
                  {i.location && safeUrl(i.location) ? (
                    <a href={safeUrl(i.location)} target="_blank" rel="noopener noreferrer">
                      Open meeting link
                    </a>
                  ) : (
                    i.location || 'Location not added'
                  )}{' '}
                  · Version {i.version}
                </p>
                <div className="chips">
                  {i.reminders.map((minutes) => (
                    <Badge key={minutes}>
                      {minutes === 1440
                        ? '1 day before'
                        : minutes === 60
                          ? '1 hour before'
                          : 'At start'}{' '}
                      · scheduled
                    </Badge>
                  ))}
                </div>
                <div className="actions">
                  <button className="secondary" onClick={() => downloadCalendar(i)}>
                    <Download size={16} />
                    Download .ics
                  </button>
                  {i.status === 'scheduled' && (
                    <>
                      <button className="secondary" onClick={() => schedule(i)}>
                        Reschedule
                      </button>
                      <button
                        className="text-button"
                        onClick={() => setAction({ interview: i, status: 'completed' })}
                      >
                        Mark complete
                      </button>
                      <button
                        className="text-button danger"
                        onClick={() => setAction({ interview: i, status: 'cancelled' })}
                      >
                        Cancel interview
                      </button>
                    </>
                  )}
                </div>
              </div>
            </section>
          ))}
        </div>
      ) : (
        <EmptyState
          title={interviewId ? 'Interview unavailable' : 'Your next conversation goes here'}
        >
          Schedule an interview for an application you have reported as submitted.
        </EmptyState>
      )}
      <Modal
        open={open}
        onOpenChange={setOpen}
        title={editing ? 'Reschedule interview' : 'Schedule interview'}
        description={`Enter times in ${timezone}. They are stored as UTC for this demo visit.`}
      >
        {error && <Alert kind="error">{error}</Alert>}
        {eligible.length ? (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              save()
            }}
          >
            <label>
              Application
              <select
                value={form.applicationId}
                required
                disabled={Boolean(editing)}
                onChange={(e) => setForm({ ...form, applicationId: e.target.value })}
              >
                <option value="">Choose application</option>
                {eligible.map((a) => (
                  <option value={a.id} key={a.id}>
                    {state.jobs.find((j) => j.id === a.jobId)!.title}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Interview title
              <input
                required
                value={form.title}
                maxLength={150}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
              />
            </label>
            <div className="form-grid">
              <label>
                Start
                <input
                  type="datetime-local"
                  required
                  value={form.start}
                  onChange={(e) => setForm({ ...form, start: e.target.value })}
                />
              </label>
              <label>
                End
                <input
                  type="datetime-local"
                  required
                  value={form.end}
                  onChange={(e) => setForm({ ...form, end: e.target.value })}
                />
              </label>
            </div>
            <label>
              Format
              <select
                value={form.mode}
                onChange={(e) => setForm({ ...form, mode: e.target.value as Interview['mode'] })}
              >
                <option value="video">Video</option>
                <option value="phone">Phone</option>
                <option value="onsite">Onsite</option>
              </select>
            </label>
            <label>
              Location or meeting link
              <input
                value={form.location}
                maxLength={500}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
              />
            </label>
            <fieldset>
              <legend>In-app reminders</legend>
              {[
                [1440, '1 day before'],
                [60, '1 hour before'],
                [0, 'At start'],
              ].map(([value, title]) => (
                <label className="checkbox" key={value}>
                  <input
                    type="checkbox"
                    checked={reminders.includes(Number(value))}
                    onChange={(e) =>
                      setReminders(
                        e.target.checked
                          ? [...reminders, Number(value)]
                          : reminders.filter((m) => m !== value),
                      )
                    }
                  />
                  {title}
                </label>
              ))}
            </fieldset>
            <button>{editing ? 'Save schedule' : 'Schedule interview'}</button>
          </form>
        ) : (
          <Alert>Report a submission first to schedule an interview for that application.</Alert>
        )}
      </Modal>
      <Modal
        open={Boolean(action)}
        onOpenChange={(value) => {
          if (!value) setAction(null)
        }}
        title={
          action?.status === 'cancelled' ? 'Cancel this interview?' : 'Mark interview complete?'
        }
        description="Scheduled reminders for this interview will stop appearing in the demo."
      >
        <div className="actions">
          <button
            onClick={() => {
              if (!action) return
              const current = state.interviews.find((i) => i.id === action.interview.id)
              if (current?.version !== action.interview.version) {
                setMessage('This interview changed. Reload its details.')
                setAction(null)
                return
              }
              setState((s) => ({
                ...s,
                interviews: s.interviews.map((i) =>
                  i.id === current.id ? { ...i, status: action.status, version: i.version + 1 } : i,
                ),
              }))
              setMessage(`Interview ${action.status}.`)
              setAction(null)
            }}
          >
            Confirm
          </button>
          <button className="secondary" onClick={() => setAction(null)}>
            Keep scheduled
          </button>
        </div>
      </Modal>
    </>
  )
}
