import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useWorkspace } from '../app/workspace'
import { useAuth } from '../features/auth/AuthProvider'
import { Alert, Modal } from '../components/ui'

export function Settings() {
  const { reset } = useWorkspace()
  const { demo, session, signOut } = useAuth()
  const [confirm, setConfirm] = useState(false)
  const [message, setMessage] = useState('')
  const navigate = useNavigate()
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Your account, your decisions.</h1>
          <p>Session, privacy, and a clear view of what this app does.</p>
        </div>
      </div>
      {message && <Alert kind="success">{message}</Alert>}
      <section className="panel form-section">
        <h2>Current session</h2>
        <p>{demo ? 'Demo account. No real candidate record is connected.' : session?.user.email}</p>
        <button
          className="secondary"
          onClick={async () => {
            await signOut()
            reset()
            navigate('/login')
          }}
        >
          Sign out
        </button>
      </section>
      <section className="panel form-section">
        <h2>Your data</h2>
        <p>
          {demo
            ? 'Demo profile edits and application records live in memory and are cleared on reload or sign-out. Resume files are not uploaded in this version.'
            : 'Your profile, applications, follow-ups, and interviews are stored in the account database. Resume previews send the file for extraction without storing it.'}
        </p>
        {demo && (
          <button className="secondary" onClick={() => setConfirm(true)}>
            Reset demo data
          </button>
        )}
        <h3>Account export and deletion</h3>
        <p>
          Server-backed export and deletion are not available yet. Signing out does not delete an
          account. Do not upload personal CV data until private API access and retention controls
          are verified.
        </p>
      </section>
      <section className="panel form-section">
        <h2>What to expect</h2>
        <p>
          Matching and generated text can miss context or make mistakes. Review every claim in a
          draft. A match score does not verify work authorization or guarantee an interview.
        </p>
        <p>
          Applications are manual. Preparing a handoff does not submit to an employer. Only your
          separate submission report changes tracking status.
        </p>
        <p>
          Reminders are in-app only. Email, push delivery, and unattended applications are not
          available.
        </p>
        <Link to="/resume">Review resume handling</Link>
      </section>
      <Modal
        open={confirm}
        onOpenChange={setConfirm}
        title="Reset this demo?"
        description="Your edits, shortlists, applications and interviews will be replaced with the original sample data."
      >
        <div className="actions">
          <button
            onClick={() => {
              reset()
              setConfirm(false)
              setMessage('Demo data reset.')
            }}
          >
            Reset demo
          </button>
          <button className="secondary" onClick={() => setConfirm(false)}>
            Keep my changes
          </button>
        </div>
      </Modal>
    </>
  )
}
