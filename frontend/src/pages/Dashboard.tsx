import { Link } from 'react-router-dom'
import { ArrowUpRight, Search, FileText, CalendarDays, CheckCircle2, Clock3 } from 'lucide-react'
import { useDemo } from '../app/store'
import { match } from '../lib/demo'
import { Badge, EmptyState } from '../components/ui'
import { useClock } from '../lib/useClock'

export function Dashboard() {
  const { state } = useDemo()
  const now = useClock()
  const submitted = state.applications.filter(
    (a) => !['draft', 'ready', 'withdrawn'].includes(a.status),
  ).length
  const drafts = state.applications.filter((a) => ['draft', 'ready'].includes(a.status))
  const interviews = state.interviews.filter(
    (i) => i.status === 'scheduled' && new Date(i.start).getTime() >= now,
  )
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="date-line">
            {new Intl.DateTimeFormat(undefined, {
              weekday: 'long',
              month: 'long',
              day: 'numeric',
            }).format(new Date())}
          </p>
          <h1>A little progress, every day.</h1>
          <p>
            Welcome back, {state.profile.full_name.split(' ')[0]}. Here’s where your search stands.
          </p>
        </div>
        <Link className="button" to="/jobs">
          <Search size={17} />
          Discover jobs
        </Link>
      </div>
      <section className="overview-grid" aria-label="Search summary">
        {[
          [Search, state.jobs.length, 'Roles to explore', '/jobs'],
          [FileText, drafts.length, 'Drafts to review', '/applications'],
          [CheckCircle2, submitted, 'Reported submissions', '/applications'],
          [CalendarDays, interviews.length, 'Upcoming interviews', '/interviews'],
        ].map(([Icon, number, label, route]) => {
          const I = Icon as typeof Search
          return (
            <Link to={String(route)} className="metric" key={String(label)}>
              <span className="metric-icon">
                <I size={21} />
              </span>
              <strong>{String(number).padStart(2, '0')}</strong>
              <span>{String(label)}</span>
              <ArrowUpRight size={16} />
            </Link>
          )
        })}
      </section>
      <section className="next-step">
        <div className="next-step-icon">
          <FileText size={32} />
        </div>
        <div>
          <Badge>Your next step</Badge>
          <h2>
            {drafts.length
              ? 'A draft is waiting for your review.'
              : 'Find a role worth applying for.'}
          </h2>
          <p>
            {drafts.length
              ? 'Check the details, make it sound like you, and mark it ready when it feels right.'
              : 'Start with your experience. Compare the evidence before approving a shortlist.'}
          </p>
          <Link className="button" to={drafts.length ? `/applications/${drafts[0].id}` : '/jobs'}>
            {drafts.length ? 'Review application' : 'Explore jobs'}
            <ArrowUpRight size={17} />
          </Link>
        </div>
        <div className="step-illustration" aria-hidden="true">
          <div />
          <FileText size={68} />
          <span>
            <CheckCircle2 size={24} />
          </span>
        </div>
      </section>
      <div className="dashboard-columns">
        <section className="panel">
          <div className="section-heading">
            <div>
              <h2>Worth a closer look</h2>
              <p>Example roles, ranked against your demo skills.</p>
            </div>
            <Link to="/jobs">
              View all <ArrowUpRight size={15} />
            </Link>
          </div>
          <div className="job-mini-list">
            {state.jobs.slice(0, 3).map((job) => (
              <Link key={job.id} to={`/jobs/${job.id}`} className="job-mini">
                <span className={`company-mark color-${job.id}`}>{job.company_name[0]}</span>
                <div>
                  <h3>{job.title}</h3>
                  <p>
                    {job.company_name}
                    <span className="dot-separator">·</span>
                    {job.location}
                  </p>
                </div>
                <span className="match-pill">
                  {match(job, state.profile.skills).score}%<small>Demo fit</small>
                </span>
                <ArrowUpRight size={17} />
              </Link>
            ))}
          </div>
          <div className="panel-footnote">
            A match is a starting point. Employer eligibility is unverified.
          </div>
        </section>
        <section className="panel attention">
          <div className="section-heading">
            <div>
              <h2>On your radar</h2>
              <p>The things that need a little attention.</p>
            </div>
            <Clock3 size={20} />
          </div>
          {interviews.length ? (
            interviews.map((i) => (
              <Link className="radar-item" to={`/interviews/${i.id}`} key={i.id}>
                <CalendarDays size={20} />
                <div>
                  <strong>{i.title}</strong>
                  <small>{new Date(i.start).toLocaleString()}</small>
                </div>
              </Link>
            ))
          ) : (
            <EmptyState title="Room for what’s next">
              Your scheduled interviews will appear here.
            </EmptyState>
          )}
          <Link className="radar-link" to="/follow-ups">
            Check your follow-ups <ArrowUpRight size={16} />
          </Link>
        </section>
      </div>
      <section className="journey-note">
        <span>
          <CheckCircle2 size={19} />A thoughtful search takes a few steps.
        </span>
        <p>Review your profile. Choose your roles. Apply on your terms.</p>
        <Link to="/profile">
          Check your profile <ArrowUpRight size={16} />
        </Link>
      </section>
    </>
  )
}
