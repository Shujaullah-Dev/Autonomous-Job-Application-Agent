import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, X, FileText } from 'lucide-react'
import { useDemo } from '../app/store'
import { useAuth } from '../features/auth/AuthProvider'
import { Alert } from '../components/ui'
import { api, type ApiSchema } from '../lib/api'

const schema = z.object({
  full_name: z.string().trim().min(1, 'Enter your name.').max(150),
  email: z.email(),
  location: z.string().max(150),
  years_experience: z.number().int().min(0).max(80),
  professional_summary: z.string().max(5000),
})
export function Profile({ onboarding = false }: { onboarding?: boolean }) {
  const { state, setState } = useDemo()
  const { demo } = useAuth()
  const [skills, setSkills] = useState(state.profile.skills)
  const [skill, setSkill] = useState('')
  const [experiences, setExperiences] = useState(state.profile.experiences)
  const [educations, setEducations] = useState(state.profile.educations)
  const [message, setMessage] = useState('')
  const navigate = useNavigate()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: state.profile,
  })
  const submit = handleSubmit((values) => {
    if (
      experiences.some(
        (row) => !row.company_name.trim() || !row.job_title.trim() || !row.start_date,
      ) ||
      educations.some((row) => !row.institution.trim() || !row.degree.trim() || !row.start_date)
    ) {
      setMessage(
        'Complete the names and start dates in your work history and education, or remove the empty entry.',
      )
      return
    }
    if (
      [...experiences, ...educations].some(
        (row) => row.start_date && row.end_date && row.end_date < row.start_date,
      )
    ) {
      setMessage('An end date cannot be before its start date.')
      return
    }
    if (demo) {
      setState((s) => ({ ...s, profile: { ...values, skills, experiences, educations } }))
      setMessage('Profile saved for this demo visit.')
      if (onboarding) navigate('/resume')
      return
    }
    void (async () => {
      try {
        const storedId = sessionStorage.getItem('job-agent-candidate-id')
        const candidate = storedId
          ? await api<ApiSchema['CandidateResponse']>(`/api/v1/candidates/${storedId}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(values),
            })
          : await api<ApiSchema['CandidateResponse']>('/api/v1/candidates', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ ...values, phone: null }),
            })
        sessionStorage.setItem('job-agent-candidate-id', candidate.id)
        for (const name of skills)
          await api(`/api/v1/candidates/${candidate.id}/skills`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name }),
          })
        setState((s) => ({ ...s, profile: { ...values, skills, experiences, educations } }))
        setMessage(
          'Profile saved to the API. Keep this browser session to retain the candidate link.',
        )
        if (onboarding) navigate('/resume')
      } catch (e) {
        setMessage((e as Error).message)
      }
    })()
  })
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{onboarding ? 'Start with your experience.' : 'Your profile'}</h1>
          <p>Keep the details accurate. They guide your matches and application drafts.</p>
        </div>
        <Link className="button secondary" to="/resume">
          <FileText size={17} />
          Review a resume
        </Link>
      </div>
      {onboarding && (
        <div className="steps">
          <strong>1. Your profile</strong>
          <span>2. Resume review</span>
          <span>3. Find a role</span>
        </div>
      )}
      <form className="profile-form" onSubmit={submit} noValidate>
        {message && (
          <Alert kind={message.startsWith('Profile saved') ? 'success' : 'error'}>{message}</Alert>
        )}
        <section className="panel form-section">
          <h2>The basics</h2>
          <p>Use the details you want employers to see.</p>
          <div className="form-grid">
            {(['full_name', 'email', 'location', 'years_experience'] as const).map((key, index) => (
              <label key={key}>
                {['Full name', 'Email address', 'Location', 'Years of experience'][index]}
                <input
                  {...register(key, key === 'years_experience' ? { valueAsNumber: true } : {})}
                  type={key === 'years_experience' ? 'number' : key === 'email' ? 'email' : 'text'}
                  min={0}
                  max={key === 'years_experience' ? 80 : undefined}
                  aria-invalid={Boolean(errors[key])}
                />
                {errors[key] && <span className="field-error">{errors[key]?.message}</span>}
              </label>
            ))}
          </div>
          <label>
            Professional summary
            <textarea rows={4} {...register('professional_summary')} />
            {errors.professional_summary && (
              <span className="field-error">{errors.professional_summary.message}</span>
            )}
          </label>
        </section>
        <section className="panel form-section">
          <h2>Skills</h2>
          <p>Add skills you can support with experience.</p>
          <div className="chips">
            {skills.map((s) => (
              <span className="chip" key={s}>
                {s}
                <button
                  aria-label={`Remove ${s}`}
                  type="button"
                  className="icon-button"
                  onClick={() => setSkills(skills.filter((v) => v !== s))}
                >
                  <X size={14} />
                </button>
              </span>
            ))}
          </div>
          <div className="inline-form">
            <label>
              New skill
              <input value={skill} maxLength={100} onChange={(e) => setSkill(e.target.value)} />
            </label>
            <button
              type="button"
              className="secondary"
              disabled={!skill.trim()}
              onClick={() => {
                if (!skills.some((s) => s.toLowerCase() === skill.trim().toLowerCase()))
                  setSkills([...skills, skill.trim()])
                setSkill('')
              }}
            >
              <Plus size={16} />
              Add skill
            </button>
          </div>
        </section>
        <section className="panel form-section">
          <div className="section-heading">
            <h2>Work experience</h2>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setExperiences([
                  ...experiences,
                  { company_name: '', job_title: '', start_date: '', end_date: '' },
                ])
              }
            >
              <Plus size={16} />
              Add experience
            </button>
          </div>
          {experiences.map((row, i) => (
            <fieldset key={i}>
              <legend>Experience {i + 1}</legend>
              <div className="form-grid">
                {(['company_name', 'job_title', 'start_date', 'end_date'] as const).map(
                  (key, k) => (
                    <label key={key}>
                      {
                        ['Company', 'Job title', 'Start date', 'End date (leave blank if current)'][
                          k
                        ]
                      }
                      <input
                        value={row[key]}
                        required={k < 3}
                        type={key.includes('date') ? 'date' : 'text'}
                        onChange={(e) =>
                          setExperiences(
                            experiences.map((r, n) =>
                              n === i ? { ...r, [key]: e.target.value } : r,
                            ),
                          )
                        }
                      />
                    </label>
                  ),
                )}
              </div>
              <button
                className="text-button danger"
                type="button"
                onClick={() => setExperiences(experiences.filter((_, n) => n !== i))}
              >
                Remove experience {i + 1}
              </button>
            </fieldset>
          ))}
        </section>
        <section className="panel form-section">
          <div className="section-heading">
            <h2>Education</h2>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setEducations([
                  ...educations,
                  { institution: '', degree: '', start_date: '', end_date: '' },
                ])
              }
            >
              <Plus size={16} />
              Add education
            </button>
          </div>
          {educations.map((row, i) => (
            <fieldset key={i}>
              <legend>Education {i + 1}</legend>
              <div className="form-grid">
                {(['institution', 'degree', 'start_date', 'end_date'] as const).map((key, k) => (
                  <label key={key}>
                    {['Institution', 'Degree', 'Start date', 'End date'][k]}
                    <input
                      value={row[key]}
                      required={k < 2}
                      type={key.includes('date') ? 'date' : 'text'}
                      onChange={(e) =>
                        setEducations(
                          educations.map((r, n) => (n === i ? { ...r, [key]: e.target.value } : r)),
                        )
                      }
                    />
                  </label>
                ))}
              </div>
              <button
                type="button"
                className="text-button danger"
                onClick={() => setEducations(educations.filter((_, n) => n !== i))}
              >
                Remove education {i + 1}
              </button>
            </fieldset>
          ))}
        </section>
        <div className="form-actions">
          <small>Demo changes are cleared on reload.</small>
          <button>{onboarding ? 'Save and review resume' : 'Save profile'}</button>
        </div>
      </form>
    </>
  )
}
