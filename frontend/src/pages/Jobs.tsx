import { Link, useParams, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowUpRight, Check, MapPin, Search, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import { api, safeUrl, type ApiSchema, type Job } from '../lib/api'
import { useDemo } from '../app/store'
import { match } from '../lib/demo'
import { Alert, Badge, EmptyState, Skeleton } from '../components/ui'

function salary(job: Job) {
  return job.salary_min != null
    ? `${job.salary_currency} ${job.salary_min.toLocaleString()}${job.salary_max != null ? `–${job.salary_max.toLocaleString()}` : '+'}`
    : 'Salary not listed'
}
export function Jobs() {
  const [params, setParams] = useSearchParams()
  const [filters, setFilters] = useState(false)
  const change = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    next.delete('page')
    setParams(next)
  }
  const page = Math.max(1, Number(params.get('page')) || 1)
  const queryParams = new URLSearchParams({ limit: '6', offset: String((page - 1) * 6) })
  for (const key of [
    'q',
    'company',
    'location',
    'work_mode',
    'minimum_salary',
    'salary_currency',
  ]) {
    if (params.get(key)) queryParams.set(key, params.get(key)!)
  }
  const query = useQuery({
    queryKey: ['jobs', queryParams.toString()],
    enabled: true,
    queryFn: ({ signal }) =>
      api<ApiSchema['JobListResponse']>(`/api/v1/jobs?${queryParams}`, { signal }),
  })
  const rows = query.data?.items || []
  const total = query.data?.total || 0
  const jobs = rows
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Find your next good fit.</h1>
          <p>Browse active roles indexed by the API.</p>
        </div>
        <Badge>{total} roles</Badge>
      </div>
      <div className="search-toolbar">
        <label className="search-input">
          <Search size={19} />
          <span className="sr-only">Search jobs</span>
          <input
            placeholder="Job title or keyword"
            value={params.get('q') || ''}
            maxLength={100}
            onChange={(e) => change('q', e.target.value)}
          />
        </label>
        <button className="secondary" aria-expanded={filters} onClick={() => setFilters(!filters)}>
          <SlidersHorizontal size={17} />
          Filters
        </button>
        <label>
          <span className="sr-only">Sort jobs on this page</span>
          <select
            value={params.get('sort') || 'default'}
            onChange={(e) => change('sort', e.target.value)}
          >
            <option value="default">Source order</option>
            <option value="title">Title (this page)</option>
          </select>
        </label>
      </div>
      {filters && (
        <div className="panel filter-panel">
          {[
            ['company', 'Company'],
            ['location', 'Location'],
          ].map(([key, label]) => (
            <label key={key}>
              {label}
              <input
                value={params.get(key) || ''}
                onChange={(e) => change(key, e.target.value)}
                maxLength={150}
              />
            </label>
          ))}
          <label>
            Work mode
            <select
              value={params.get('work_mode') || ''}
              onChange={(e) => change('work_mode', e.target.value)}
            >
              <option value="">Any work mode</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="onsite">Onsite</option>
            </select>
          </label>
          <label>
            Minimum annual salary
            <input
              type="number"
              min="0"
              value={params.get('minimum_salary') || ''}
              onChange={(e) => {
                const next = new URLSearchParams(params)
                if (e.target.value) {
                  next.set('minimum_salary', e.target.value)
                  next.set('salary_currency', next.get('salary_currency') || 'USD')
                } else next.delete('minimum_salary')
                next.delete('page')
                setParams(next)
              }}
            />
          </label>
          <label>
            Currency
            <select
              value={params.get('salary_currency') || 'USD'}
              onChange={(e) => change('salary_currency', e.target.value)}
            >
              {['USD', 'GBP', 'EUR', 'CAD', 'PKR'].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <button className="text-button" onClick={() => setParams({})}>
            Clear filters
          </button>
        </div>
      )}
      {query.isPending ? (
        <Skeleton />
      ) : query.isError ? (
        <Alert kind="error">
          {query.error.message}{' '}
          <button className="text-button" onClick={() => query.refetch()}>
            Try again
          </button>
        </Alert>
      ) : jobs.length === 0 ? (
        <EmptyState title="No roles found">Try a broader keyword or clear your filters.</EmptyState>
      ) : (
        <div className="jobs-grid">
          {jobs.map((job) => (
            <article className="job-card" key={job.id}>
              <div className="job-card-top">
                <span className={`company-mark color-${job.id % 6}`}>{job.company_name[0]}</span>
              </div>
              <p>{job.company_name}</p>
              <h2>
                <Link to={`/jobs/${job.id}`}>{job.title}</Link>
              </h2>
              <div className="job-location">
                <MapPin size={15} />
                {job.location || 'Location not listed'}
              </div>
              <div className="chips">
                <Badge>{job.work_mode || 'Work mode unknown'}</Badge>
                <Badge>{job.employment_type || 'Type unknown'}</Badge>
              </div>
              <strong className="salary">{salary(job)}</strong>
              <div className="job-card-footer">
                <small>{job.source || 'Source unknown'}</small>
                <Link
                  to={`/jobs/${job.id}`}
                  aria-label={`View ${job.title} at ${job.company_name}`}
                >
                  <ArrowUpRight size={20} />
                </Link>
              </div>
            </article>
          ))}
        </div>
      )}
      <div className="pagination">
        <button
          className="secondary"
          disabled={page <= 1}
          onClick={() =>
            setParams((p) => {
              p.set('page', String(page - 1))
              return p
            })
          }
        >
          Previous
        </button>
        <span>Page {page}</span>
        <button
          className="secondary"
          disabled={page * 6 >= total}
          onClick={() =>
            setParams((p) => {
              p.set('page', String(page + 1))
              return p
            })
          }
        >
          Next
        </button>
      </div>
    </>
  )
}
export function JobDetail() {
  const { jobId } = useParams()
  const { state } = useDemo()
  const demo = state.profile.skills.length > 0
  const query = useQuery({
    queryKey: ['job', jobId],
    enabled: /^\d+$/.test(jobId || ''),
    queryFn: ({ signal }) => api<Job>(`/api/v1/jobs/${jobId}`, { signal }),
  })
  const job = query.data
  if (query.isPending && /^\d+$/.test(jobId || '')) return <Skeleton />
  if (query.isError) return <Alert kind="error">{query.error.message}</Alert>
  if (!job)
    return (
      <EmptyState title="Role unavailable">
        This listing could not be found. <Link to="/jobs">Back to jobs</Link>
      </EmptyState>
    )
  const fit = match(job, state.profile.skills)
  return (
    <>
      <Link className="back-link" to="/jobs">
        Back to jobs
      </Link>
      <div className="page-heading">
        <div>
          <p>{job.company_name}</p>
          <h1>{job.title}</h1>
          <p>
            {job.location || 'Location unknown'} · {job.work_mode || 'Work mode unknown'}
          </p>
        </div>
        <span className="company-mark large">{job.company_name[0]}</span>
      </div>
      <div className="detail-columns">
        <section className="panel form-section">
          <h2>About this role</h2>
          <p className="prose preserve-lines">{job.description}</p>
          <div className="detail-facts">
            <p>
              Salary<strong>{salary(job)}</strong>
            </p>
            <p>
              Source<strong>{job.source || 'Unknown'}</strong>
            </p>
            <p>
              Posted
              <strong>
                {job.posted_at ? new Date(job.posted_at).toLocaleDateString() : 'Date unknown'}
              </strong>
            </p>
          </div>
          {safeUrl(job.job_url) ? (
            <a
              className="button secondary"
              href={safeUrl(job.job_url)}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open original listing <ArrowUpRight size={17} />
            </a>
          ) : (
            <Alert>This listing has no safe HTTPS destination.</Alert>
          )}
        </section>
        <aside className="panel form-section">
          <h2>{demo ? `${fit.score}% demo fit` : 'Match explanation'}</h2>
          {demo ? (
            <>
              <p>
                Illustrative keyword score: 35 base points + 18 per matched profile skill, capped at
                95. This is not the backend ranking.
              </p>
              <h3>Evidence in the sample listing</h3>
              {fit.matched.map((skill) => (
                <p className="evidence" key={skill}>
                  <Check size={16} />
                  {skill}
                </p>
              ))}
              <h3>Check before applying</h3>
              <p className="evidence">
                <AlertTriangle size={18} />
                Work authorization and employer eligibility are unverified.
              </p>
              <Link className="button" to="/workflows">
                Review a shortlist
              </Link>
            </>
          ) : (
            <Alert>
              Personal matching needs verified private API access. Listing details are available
              above.
            </Alert>
          )}
        </aside>
      </div>
    </>
  )
}
