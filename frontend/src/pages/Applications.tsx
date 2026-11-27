import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ArrowUpRight, FileText, CheckCircle2 } from 'lucide-react'
import { useWorkspace } from '../app/workspace'
import { transitions, type Status } from '../lib/demo'
import { Alert, Badge, EmptyState, Modal, Skeleton } from '../components/ui'

const statusLabel = (status: string) =>
  status === 'submitted' ? 'Submitted by you' : status[0].toUpperCase() + status.slice(1)
export function Applications() {
  const { state, loading, live } = useWorkspace()
  const [params, setParams] = useSearchParams()
  const status = params.get('status') || 'all'
  const search = params.get('q') || ''
  const jobOf = (jobId: number) =>
    state.jobs.find((j) => j.id === jobId) ?? {
      id: jobId,
      title: 'Role unavailable',
      company_name: '',
    }
  const rows = state.applications.filter((a) => {
    const job = jobOf(a.jobId)
    return (
      (status === 'all' || a.status === status) &&
      `${job.title} ${job.company_name}`.toLowerCase().includes(search.toLowerCase())
    )
  })
  if (live && loading && !state.applications.length) return <Skeleton />
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Every application, accounted for.</h1>
          <p>Drafts, handoffs, and submissions you’ve reported.</p>
        </div>
        <Link className="button" to="/workflows">
          Review a shortlist
        </Link>
      </div>
      <div className="tabs" aria-label="Filter by status">
        {[
          'all',
          'draft',
          'ready',
          'submitted',
          'interview',
          'offered',
          'rejected',
          'withdrawn',
        ].map((s) => (
          <button
            key={s}
            className={status === s ? 'active' : ''}
            aria-pressed={status === s}
            onClick={() =>
              setParams((p) => {
                p.set('status', s)
                return p
              })
            }
          >
            {statusLabel(s)}
            <span>{state.applications.filter((a) => s === 'all' || a.status === s).length}</span>
          </button>
        ))}
      </div>
      <label className="search-label">
        Search applications
        <input
          type="search"
          value={search}
          placeholder="Job title or company"
          onChange={(e) =>
            setParams((p) => {
              p.set('q', e.target.value)
              return p
            })
          }
        />
      </label>
      {rows.length ? (
        <section className="panel table-panel">
          <div className="table-heading">
            <span>Role and company</span>
            <span>Status</span>
            <span>Revision</span>
          </div>
          {rows.map((a) => {
            const job = jobOf(a.jobId)
            return (
              <Link className="list-row" to={`/applications/${a.id}`} key={a.id}>
                <span className="company-mark">{job.company_name[0]}</span>
                <div className="grow">
                  <strong>{job.title}</strong>
                  <small>{job.company_name}</small>
                  {a.handoffRevision && (
                    <small>Manual handoff prepared · revision {a.handoffRevision}</small>
                  )}
                </div>
                <Badge status={a.status}>{statusLabel(a.status)}</Badge>
                <span>v{a.revision}</span>
                <ArrowUpRight size={18} />
              </Link>
            )
          })}
        </section>
      ) : (
        <EmptyState title="No applications here yet">
          Approve a role in your shortlist to create a draft, or change your filters.
        </EmptyState>
      )}
    </>
  )
}
export function ApplicationDetail() {
  const { applicationId } = useParams()
  const { state, demo, live, loading, saveDraft, changeStatus, prepareHandoff } = useWorkspace()
  const application = state.applications.find((a) => a.id === applicationId)
  const [letter, setLetter] = useState(application?.letter || '')
  const [revision, setRevision] = useState(application?.revision || 1)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [action, setAction] = useState<Status | 'handoff' | null>(null)
  const [reviewed, setReviewed] = useState(false)
  const [manual, setManual] = useState(false)
  // This screen can render before the live workspace has loaded the record, so
  // the editable copy is filled the first time that record is available rather
  // than showing an empty letter that could then be saved over the stored
  // draft.
  const [loadedId, setLoadedId] = useState<string | null>(null)
  if (application && loadedId !== application.id) {
    setLoadedId(application.id)
    setLetter(application.letter)
    setRevision(application.revision)
  }
  if (live && loading && !application) return <Skeleton />
  if (!application)
    return (
      <EmptyState title="Application unavailable">
        This record could not be loaded. <Link to="/applications">Back to applications</Link>
      </EmptyState>
    )
  const job = state.jobs.find((j) => j.id === application.jobId)
  const dirty = letter !== application.letter
  const canEdit = ['draft', 'ready'].includes(application.status)
  async function save() {
    try {
      await saveDraft(application!.id, letter, revision)
      setRevision(revision + 1)
      setMessage(`Revision ${revision + 1} saved.`)
      setError('')
    } catch (e) {
      setError((e as Error).message)
    }
  }
  async function confirm() {
    try {
      if (action === 'handoff') await prepareHandoff(application!.id, revision)
      else await changeStatus(application!.id, action as Status, reviewed, manual)
      setMessage(
        action === 'handoff'
          ? demo
            ? 'Prepared — open the employer site and apply yourself. This fictional role has no employer destination.'
            : 'Handoff prepared. Open the employer listing and apply yourself.'
          : action === 'submitted'
            ? 'Recorded your submission report. No employer confirmation was received.'
            : `Status changed to ${action}.`,
      )
      setAction(null)
      setError('')
      setReviewed(false)
      setManual(false)
    } catch (e) {
      setError((e as Error).message)
      setAction(null)
    }
  }
  const open = (next: Status | 'handoff') => {
    setReviewed(false)
    setManual(false)
    setAction(next)
  }
  return (
    <>
      <Link className="back-link" to="/applications">
        Back to applications
      </Link>
      <div className="page-heading">
        <div>
          <p>{job?.company_name || 'Company unavailable'}</p>
          <h1>{job?.title || 'Role unavailable'}</h1>
          <p>Review every claim before use</p>
        </div>
        <Badge status={application.status}>{statusLabel(application.status)}</Badge>
      </div>
      {error && (
        <Alert kind="error">
          {error}{' '}
          <button
            className="text-button"
            onClick={() => {
              setLetter(application.letter)
              setRevision(application.revision)
              setError('')
            }}
          >
            Reload saved draft
          </button>
        </Alert>
      )}
      {message && <Alert kind="success">{message}</Alert>}
      <div className="detail-columns">
        <section className="panel form-section">
          <div className="section-heading">
            <h2>
              <FileText size={20} />
              Cover letter
            </h2>
            <Badge>Revision {application.revision}</Badge>
          </div>
          <label>
            <span className="sr-only">Cover letter</span>
            <textarea
              className="letter-editor"
              rows={14}
              value={letter}
              maxLength={15000}
              disabled={!canEdit}
              onChange={(e) => setLetter(e.target.value)}
            />
          </label>
          <div className="form-actions">
            <small>{letter.length.toLocaleString()} / 15,000 characters</small>
            <button disabled={!canEdit || !dirty || letter.trim().length < 20} onClick={save}>
              Save revision
            </button>
          </div>
          <details>
            <summary>Previous revisions ({application.revisions.length})</summary>
            {application.revisions.map((r) => (
              <article key={r.number}>
                <h3>Revision {r.number}</h3>
                <p className="preserve-lines">{r.letter}</p>
              </article>
            ))}
          </details>
        </section>
        <aside>
          <section className="panel form-section">
            <h2>Resume snapshot</h2>
            <h3>{application.resumeSnapshot.full_name}</h3>
            <p>{application.resumeSnapshot.professional_summary}</p>
            <div className="chips">
              {application.resumeSnapshot.skills.map((skill) => (
                <Badge key={skill}>{skill}</Badge>
              ))}
            </div>
            <p className="muted">
              Saved when this draft was created. Later profile edits do not change this snapshot.
            </p>
          </section>
          <section className="panel form-section">
            <h2>Before you apply</h2>
            <p>Review the content, mark it ready, then prepare a manual handoff.</p>
            {transitions[application.status].map((s) => (
              <button
                className={s === 'withdrawn' ? 'text-button danger' : 'secondary full-width'}
                disabled={dirty}
                key={s}
                onClick={() => open(s)}
              >
                {s === 'submitted' ? 'I submitted this application' : `Mark ${s}`}
              </button>
            ))}
            {application.status === 'ready' && (
              <button className="full-width" disabled={dirty} onClick={() => open('handoff')}>
                {application.handoffRevision === revision
                  ? 'Review prepared handoff'
                  : 'Prepare Manual Handoff'}
              </button>
            )}
            {dirty && <small>Save your draft before changing its status.</small>}
            <p className="muted">
              You apply on the employer’s website. This app never submits for you.
            </p>
          </section>
        </aside>
      </div>
      <section className="panel form-section">
        <h2>Status history</h2>
        <ol className="timeline">
          {application.history.map((event, index) => (
            <li key={index}>
              <CheckCircle2 size={18} />
              <div>
                <strong>{statusLabel(event.status)}</strong>
                <p>{event.note}</p>
                <small>{new Date(event.at).toLocaleString()}</small>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <Modal
        open={action !== null}
        onOpenChange={(value) => {
          if (!value) setAction(null)
        }}
        title={
          action === 'handoff'
            ? 'Prepare a manual handoff'
            : action === 'submitted'
              ? 'Record your submission?'
              : `Mark application ${action}?`
        }
        description={
          action === 'submitted'
            ? 'Only confirm after completing the application on the employer site. This records your report.'
            : 'This action updates your tracking record. Nothing is sent to an employer.'
        }
      >
        {(action === 'handoff' || action === 'ready') && (
          <label className="checkbox">
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(e) => setReviewed(e.target.checked)}
            />
            I reviewed the cover letter and resume details.
          </label>
        )}
        {(action === 'handoff' || action === 'submitted') && (
          <label className="checkbox">
            <input type="checkbox" checked={manual} onChange={(e) => setManual(e.target.checked)} />
            {action === 'handoff'
              ? 'I understand I must open the employer site and apply myself.'
              : 'I confirm I completed submission on the employer site.'}
          </label>
        )}
        {action === 'handoff' && (
          <div className="preflight">
            <p>
              <CheckCircle2 size={16} />
              Current saved revision: {revision}
            </p>
            <p>
              <CheckCircle2 size={16} />
              Application marked ready
            </p>
            <Alert>
              No employer destination is available for this fictional role. This action only
              demonstrates preparation.
            </Alert>
          </div>
        )}
        <div className="actions">
          <button
            disabled={
              ((action === 'ready' || action === 'handoff') && !reviewed) ||
              ((action === 'submitted' || action === 'handoff') && !manual)
            }
            onClick={confirm}
          >
            Confirm {action === 'handoff' ? 'preparation' : 'status change'}
          </button>
          <button className="secondary" onClick={() => setAction(null)}>
            Keep reviewing
          </button>
        </div>
      </Modal>
    </>
  )
}
