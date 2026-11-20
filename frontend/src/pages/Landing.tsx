import { Link, useNavigate } from 'react-router-dom'
import { Sprout, ArrowUpRight, Check, Search, FileCheck2, CalendarDays } from 'lucide-react'
import { useAuth } from '../features/auth/AuthProvider'

export function Landing() {
  const { enterDemo } = useAuth()
  const navigate = useNavigate()
  return (
    <div className="landing">
      <header>
        <Link to="/" className="brand">
          <span className="brand-symbol">
            <Sprout />
          </span>
          jobagent.
        </Link>
        <nav>
          <Link to="/login">Sign in</Link>
          <Link className="button" to="/signup">
            Create account
          </Link>
        </nav>
      </header>
      <main>
        <section className="landing-hero">
          <div>
            <span className="pill">
              <span />
              Your search, with a plan
            </span>
            <h1>
              Your next role.
              <br />A clearer path there.
            </h1>
            <p>
              Find relevant jobs, review your application materials, and keep every follow-up in one
              place. You stay in charge of every application.
            </p>
            <div className="actions">
              <button
                onClick={() => {
                  enterDemo()
                  navigate('/dashboard')
                }}
              >
                Explore the demo <ArrowUpRight size={18} />
              </button>
              <Link className="button secondary" to="/signup">
                Get started
              </Link>
            </div>
            <small>No account needed for the demo. Sample data only.</small>
          </div>
          <div className="landing-preview">
            <div className="preview-bar">
              <span />
              <span />
              <span />
            </div>
            <p>Your next step</p>
            <h2>
              A good match deserves
              <br />a thoughtful application.
            </h2>
            <div className="preview-role">
              <span className="company-mark">N</span>
              <div>
                <strong>Frontend Engineer</strong>
                <small>Northstar Studio · Fictional example</small>
              </div>
              <span className="badge">Review</span>
            </div>
            <div className="preview-check">
              <Check size={18} /> Find roles that fit your experience
            </div>
            <div className="preview-check">
              <Check size={18} /> Review and edit before you apply
            </div>
            <div className="preview-check">
              <Check size={18} /> Apply yourself on the employer site
            </div>
            <div className="preview-bottom">
              Prepared is a step. Submitted is your confirmation.
            </div>
          </div>
        </section>
        <section className="landing-features">
          {[
            [
              Search,
              'Find a useful starting point',
              'Compare indexed roles and see the evidence behind a match.',
            ],
            [
              FileCheck2,
              'Put your name on work you trust',
              'Correct your profile, edit your drafts, and approve your shortlist.',
            ],
            [
              CalendarDays,
              'Know what needs attention',
              'Track reported submissions, follow-ups, and interview reminders.',
            ],
          ].map(([Icon, title, copy]) => {
            const I = Icon as typeof Search
            return (
              <article key={String(title)}>
                <I size={25} />
                <h3>{String(title)}</h3>
                <p>{String(copy)}</p>
              </article>
            )
          })}
        </section>
      </main>
      <footer>
        Built for a considered job search.
        <span>AI suggestions need your review. Reminders appear in the app.</span>
      </footer>
    </div>
  )
}
