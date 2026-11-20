import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Plus, Check, ArrowUpRight } from 'lucide-react'
import { useDemo } from '../app/store'
import { match, type Application } from '../lib/demo'
import { Alert, Badge, EmptyState, Modal } from '../components/ui'

export function Workflows() {
  const { state, setState } = useDemo()
  const navigate = useNavigate()
  const { workflowId } = useParams()
  const workflow = state.workflows.find((w) => w.id === workflowId)
  const [selected, setSelected] = useState<number[]>([])
  const [confirm, setConfirm] = useState(false)
  const [mode, setMode] = useState('')
  const [message, setMessage] = useState('')
  function start() {
    const id = crypto.randomUUID()
    const jobIds = state.jobs
      .filter((j) => !mode || j.work_mode === mode)
      .sort((a, b) => match(b, state.profile.skills).score - match(a, state.profile.skills).score)
      .slice(0, 5)
      .map((j) => j.id)
    setState((s) => ({
      ...s,
      workflows: [
        ...s.workflows,
        { id, jobIds, approvedIds: [], status: jobIds.length ? 'pending_review' : 'no_matches' },
      ],
    }))
    navigate(`/workflows/${id}`)
  }
  function decide(approved: boolean) {
    if (!workflow || workflow.status !== 'pending_review' || (approved && !selected.length)) return
    setState((s) => ({
      ...s,
      workflows: s.workflows.map((w) =>
        w.id === workflow.id
          ? {
              ...w,
              approvedIds: approved ? selected : [],
              status: approved ? 'approved' : 'rejected',
            }
          : w,
      ),
    }))
    setConfirm(false)
    setMessage(
      approved
        ? 'Shortlist approved. You can now create drafts for the selected roles.'
        : 'Shortlist rejected. No drafts were created.',
    )
  }
  function createDraft(jobId: number) {
    if (!workflow?.approvedIds.includes(jobId) || state.applications.some((a) => a.jobId === jobId))
      return
    const job = state.jobs.find((j) => j.id === jobId)!
    const id = crypto.randomUUID()
    const application: Application = {
      id,
      jobId,
      status: 'draft',
      revision: 1,
      resumeSnapshot: structuredClone(state.profile),
      revisions: [],
      history: [
        {
          status: 'draft',
          at: new Date().toISOString(),
          note: 'Draft created from an explicitly approved demo shortlist.',
        },
      ],
      letter: `Hello ${job.company_name} team,\n\nI would like to apply for the ${job.title} role. My experience includes ${state.profile.skills.filter((skill) => job.description.toLowerCase().includes(skill.toLowerCase())).join(', ') || 'the skills listed in my profile'}. I would welcome a conversation about the work and the experience your team needs.\n\n${state.profile.full_name}`,
    }
    setState((s) => ({ ...s, applications: [...s.applications, application] }))
    navigate(`/applications/${id}`)
  }
  if (workflowId && !workflow)
    return (
      <EmptyState title="Shortlist unavailable">
        Demo state is cleared on reload. <Link to="/workflows">Start a new shortlist</Link>. A live
        workflow may also be lost when the API restarts until durable checkpoints are available.
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
      {message && <Alert kind="success">{message}</Alert>}
      {!workflow ? (
        <>
          <section className="panel form-section">
            <h2>Start a sample shortlist</h2>
            <p>Uses the local example jobs and demo keyword score. No AI service is called.</p>
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
              <button onClick={start}>
                <Plus size={17} />
                Create shortlist
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
                    <small>Demo shortlist {w.id.slice(0, 8)}</small>
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
                      {match(job, state.profile.skills).matched.join(', ') ||
                        'No profile skills found in sample description'}{' '}
                      · Eligibility unverified
                    </small>
                  </div>
                  <Badge>{match(job, state.profile.skills).score}% demo fit</Badge>
                  {workflow.approvedIds.includes(id) &&
                    (existing ? (
                      <Link className="button secondary" to={`/applications/${existing.id}`}>
                        Open draft
                      </Link>
                    ) : (
                      <button className="secondary" onClick={() => createDraft(id)}>
                        Create draft
                      </button>
                    ))}
                </div>
              )
            })}
          </div>
          {workflow.status === 'pending_review' && (
            <div className="form-actions">
              <button className="secondary" onClick={() => decide(false)}>
                Reject shortlist
              </button>
              <button disabled={!selected.length} onClick={() => setConfirm(true)}>
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
