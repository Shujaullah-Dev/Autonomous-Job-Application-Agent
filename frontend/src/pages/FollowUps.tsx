import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Check, X } from 'lucide-react'
import { useWorkspace } from '../app/workspace'
import { useClock } from '../lib/useClock'
import { Alert, Badge, EmptyState, Modal, Skeleton } from '../components/ui'

export function FollowUps() {
  const { state, loading, live, createFollowUp, resolveFollowUp } = useWorkspace()
  const [open, setOpen] = useState(false)
  const [applicationId, setApplicationId] = useState('')
  const [due, setDue] = useState('')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [failed, setFailed] = useState(false)
  const eligible = state.applications.filter((a) => ['submitted', 'interview'].includes(a.status))
  const now = useClock()
  if (live && loading && !state.applications.length) return <Skeleton />
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Keep the conversation moving.</h1>
          <p>Plan a check-in. Follow-ups are reminders for you, and send no email.</p>
        </div>
        <button
          onClick={() => {
            setError('')
            setOpen(true)
          }}
        >
          <Plus size={17} />
          Schedule follow-up
        </button>
      </div>
      {message && <Alert kind={failed ? 'error' : 'success'}>{message}</Alert>}
      {(['Overdue', 'Upcoming', 'Resolved'] as const).map((group) => {
        const rows = state.followUps
          .filter((f) =>
            group === 'Resolved'
              ? f.state !== 'pending'
              : f.state === 'pending' &&
                (group === 'Overdue'
                  ? new Date(f.due).getTime() < now
                  : new Date(f.due).getTime() >= now),
          )
          .sort((a, b) => a.due.localeCompare(b.due))
        return (
          <section className="panel table-panel" key={group}>
            <h2>
              {group}
              <Badge>{rows.length}</Badge>
            </h2>
            {rows.length ? (
              rows.map((f) => {
                const app = state.applications.find((a) => a.id === f.applicationId)
                const job = state.jobs.find((j) => j.id === app?.jobId)
                return (
                  <div className="list-row" key={f.id}>
                    <div className="grow">
                      <Link to={app ? `/applications/${app.id}` : '/applications'}>
                        <strong>{job?.title || 'Application'}</strong>
                      </Link>
                      <small>
                        {job?.company_name ? `${job.company_name} · ` : ''}
                        {new Date(f.due).toLocaleString()}
                      </small>
                      <p>{f.note}</p>
                    </div>
                    <Badge status={group === 'Overdue' ? 'overdue' : f.state}>{f.state}</Badge>
                    {f.state === 'pending' && (
                      <>
                        <button
                          className="secondary"
                          aria-label={`Complete follow-up for ${job?.title || 'this application'}`}
                          onClick={async () => {
                            try {
                              await resolveFollowUp(f.applicationId, f.id, true)
                              setFailed(false)
                              setMessage('Follow-up marked complete.')
                            } catch (e) {
                              setFailed(true)
                              setMessage((e as Error).message)
                            }
                          }}
                        >
                          <Check size={16} />
                          Complete
                        </button>
                        <button
                          className="icon-button"
                          aria-label={`Dismiss follow-up for ${job?.title || 'this application'}`}
                          onClick={async () => {
                            try {
                              await resolveFollowUp(f.applicationId, f.id, false)
                              setFailed(false)
                              setMessage('Follow-up dismissed.')
                            } catch (e) {
                              setFailed(true)
                              setMessage((e as Error).message)
                            }
                          }}
                        >
                          <X size={17} />
                        </button>
                      </>
                    )}
                  </div>
                )
              })
            ) : (
              <EmptyState title={`No ${group.toLowerCase()} follow-ups`}>
                {group === 'Resolved'
                  ? 'Completed and dismissed reminders appear here.'
                  : 'Schedule a check-in for a submitted application.'}
              </EmptyState>
            )}
          </section>
        )
      })}
      <Modal
        open={open}
        onOpenChange={setOpen}
        title="Schedule a follow-up"
        description={`Times use ${Intl.DateTimeFormat().resolvedOptions().timeZone}. This reminder stays in your workspace and sends no email.`}
      >
        {error && <Alert kind="error">{error}</Alert>}
        {eligible.length ? (
          <form
            onSubmit={async (e) => {
              e.preventDefault()
              if (!applicationId || !due || !Number.isFinite(new Date(due).getTime())) {
                setError('Choose an application and a valid date.')
                return
              }
              try {
                await createFollowUp(applicationId, new Date(due).toISOString(), note)
                setOpen(false)
                setFailed(false)
                setMessage('Follow-up scheduled. No message has been sent.')
                setNote('')
                setDue('')
                setError('')
              } catch (err) {
                setError((err as Error).message)
              }
            }}
          >
            <label>
              Application
              <select
                required
                value={applicationId}
                onChange={(e) => setApplicationId(e.target.value)}
              >
                <option value="">Choose application</option>
                {eligible.map((a) => (
                  <option key={a.id} value={a.id}>
                    {state.jobs.find((j) => j.id === a.jobId)?.title || 'Application'}
                  </option>
                ))}
              </select>
            </label>
            <label>
              When
              <input
                type="datetime-local"
                required
                value={due}
                onChange={(e) => setDue(e.target.value)}
              />
            </label>
            <label>
              Note
              <textarea value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
            </label>
            <button>Schedule follow-up</button>
          </form>
        ) : (
          <Alert>
            Report a submission first. Follow-ups are available for submitted applications and
            interviews.
          </Alert>
        )}
      </Modal>
    </>
  )
}
