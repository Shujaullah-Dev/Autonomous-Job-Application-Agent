import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Plus, Check, ArrowUpRight } from 'lucide-react'
import { useWorkspace } from '../app/workspace'
import { match } from '../lib/demo'
import { Alert, Badge, EmptyState, Modal, Skeleton } from '../components/ui'

export function Workflows() {
  const { state, demo, loading, startWorkflow, reviewWorkflow, createDraft } = useWorkspace()
  const navigate = useNavigate()
  const { workflowId } = useParams()
  const workflow = state.workflows.find((w) => w.id === workflowId)
  const [selected, setSelected] = useState<number[]>([])
  const [confirm, setConfirm] = useState(false)
  const [mode, setMode] = useState('')
  const [message, setMessage] = useState('')
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState(false)
  async function start() {
    setBusy(true)
    setMessage('')
    try {
      const id = await startWorkflow(mode)
      navigate(`/workflows/${id}`)
    } catch (e) {
      setFailed(true)
      setMessage((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  async function decide(approved: boolean) {
    if (!workflow || workflow.status !== 'pending_review' || (approved && !selected.length)) return
    setBusy(true)
    try {
      await reviewWorkflow(workflow.id, approved ? selected : [])
      setConfirm(false)
      setFailed(false)
      setMessage(
        approved
          ? 'Shortlist approved. You can now create drafts for the selected roles.'
          : 'Shortlist rejected. No drafts were created.',
      )
    } catch (e) {
      setFailed(true)
      setMessage((e as Error).message)
      setConfirm(false)
    } finally {
      setBusy(false)
    }
  }
  async function makeDraft(jobId: number) {
    if (!workflow?.approvedIds.includes(jobId) || state.applications.some((a) => a.jobId === jobId))
      return
    setBusy(true)
    setMessage('')
    try {
      const id = await createDraft(workflow.id, jobId)
      navigate(`/applications/${id}`)
    } catch (e) {
      setFailed(true)
      setMessage((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  if (loading && !workflow)
    return (
      <>
        <Skeleton />
      </>
    )
  if (workflowId && !workflow)
    return (
      <EmptyState title="Shortlist unavailable">
        This shortlist could not be loaded. <Link to="/workflows">Start a new shortlist</Link>. If
        the API restarted, saved shortlists reload from the workflow store.
      </EmptyState>
    )
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>
            {workflow ? 'Choose the roles worth your time.' : 'A shortlist you have a say in.'}
          </h1>
          <p>Review every suggestion. Approval prepares drafts; it never sends an application.</p>
        </div>
        {workflow && <Badge status={workflow.status}>{workflow.status.replaceAll('_', ' ')}</Badge>}
      </div>
      {message && <Alert kind={failed ? 'error' : 'success'}>{message}</Alert>}
      {!workflow ? (
        <>
          <section className="panel form-section">
            <h2>{demo ? 'Start a sample shortlist' : 'Start a shortlist'}</h2>
            <p>
              {demo
                ? 'Uses the local example jobs and demo keyword score. No AI service is called.'
                : 'Uses active roles from the job index and your verified profile. Nothing is sent to an employer.'}
            </p>
            <div className="inline-form">
              <label>
                Preferred work mode
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="">Any work mode</option>
                  <option value="remote">Remote</option>
                  <option value="hybrid">Hybrid</option>
                  <option value="onsite">Onsite</option>
                </select>
              </label>
              <button disabled={busy} onClick={start}>
                <Plus size={17} />
                {busy ? 'Building shortlist…' : 'Create shortlist'}
              </button>
            </div>
          </section>
          {state.workflows.length ? (
            <section className="panel table-panel">
              <h2>Recent shortlists</h2>
              {state.workflows.map((w) => (
                <Link className="list-row" key={w.id} to={`/workflows/${w.id}`}>
                  <div>
                    <strong>{w.jobIds.length} suggested roles</strong>
                    <small>Shortlist {w.id.slice(0, 8)}</small>
                  </div>
                  <Badge>{w.status.replaceAll('_', ' ')}</Badge>
                  <ArrowUpRight size={17} />
                </Link>
              ))}
            </section>
          ) : (
            <EmptyState title="Your first shortlist starts here">
              Choose a work mode and review the suggested roles.
            </EmptyState>
          )}
        </>
      ) : workflow.jobIds.length === 0 ? (
        <EmptyState title="No roles cleared the relevance bar">
          None of the active roles mention the skills on your profile yet.{' '}
          <Link to="/jobs">Browse the job index</Link> or{' '}
          <Link to="/workflows">start another shortlist</Link> with a different work mode.
        </EmptyState>
      ) : (
        <>
          <div className="panel table-panel">
            {workflow.jobIds.map((id) => {
              const job = state.jobs.find((j) => j.id === id)!
              const existing = state.applications.find((a) => a.jobId === id)
              return (
                <div className="list-row" key={id}>
                  {workflow.status === 'pending_review' && (
                    <input
                      type="checkbox"
                      aria-label={`Select ${job.title}`}
                      checked={selected.includes(id)}
                      onChange={(e) =>
                        setSelected(
                          e.target.checked ? [...selected, id] : selected.filter((v) => v !== id),
                        )
                      }
                    />
                  )}
                  <span className="company-mark">{job.company_name[0]}</span>
                  <div className="grow">
                    <Link to={`/jobs/${id}`}>
                      <strong>{job.title}</strong>
                    </Link>
                    <small>
                      {job.company_name} · {job.work_mode || 'Work mode unknown'}
                    </small>
                    <small>
                      {workflow.summaries?.[id] ||
                        match(job, state.profile.skills).matched.join(', ') ||
                        'No profile skills found in the listing'}{' '}
                      · Eligibility unverified
                    </small>
                  </div>
                  <Badge>
                    {workflow.scores?.[id] ?? match(job, state.profile.skills).score}% fit
                  </Badge>
                  {workflow.approvedIds.includes(id) &&
                    (existing ? (
                      <Link className="button secondary" to={`/applications/${existing.id}`}>
                        Open draft
                      </Link>
                    ) : (
                      <button className="secondary" disabled={busy} onClick={() => makeDraft(id)}>
                        Create draft
                      </button>
                    ))}
                </div>
              )
            })}
          </div>
          {workflow.status === 'pending_review' && (
            <div className="form-actions">
              <button className="secondary" disabled={busy} onClick={() => decide(false)}>
                Reject shortlist
              </button>
              <button disabled={!selected.length || busy} onClick={() => setConfirm(true)}>
                <Check size={17} />
                Approve {selected.length} selected
              </button>
            </div>
          )}
          <Modal
            open={confirm}
            onOpenChange={setConfirm}
            title="Approve selected roles?"
            description="You can create application drafts for these roles next. Nothing will be sent to an employer."
          >
            <p>
              {selected.length} role{selected.length === 1 ? '' : 's'} selected.
            </p>
            <div className="actions">
              <button onClick={() => decide(true)}>Confirm approval</button>
              <button className="secondary" onClick={() => setConfirm(false)}>
                Keep reviewing
              </button>
            </div>
          </Modal>
        </>
      )}
    </>
  )
}
