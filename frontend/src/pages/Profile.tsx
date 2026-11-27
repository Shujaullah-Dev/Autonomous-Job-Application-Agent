import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, X, FileText } from 'lucide-react'
import { useWorkspace } from '../app/workspace'
import type { Profile as ProfileRecord } from '../lib/demo'
import { buildResumeImport, importResume, previewResume, type ResumePreview } from '../lib/live'
import { validateResume } from '../lib/api'
import { Alert, Skeleton } from '../components/ui'

const schema = z.object({
  full_name: z.string().trim().min(1, 'Enter your name.').max(150),
  email: z.email(),
  location: z.string().max(150),
  years_experience: z.number().int().min(0).max(80),
  professional_summary: z.string().max(5000),
})
export function Profile({ onboarding = false }: { onboarding?: boolean }) {
  const { state, demo, live, profileId, saveProfile, loading, error } = useWorkspace()
  // The form keeps editable copies of the profile, so it must mount only after
  // the saved record has arrived. Mounting earlier left the fields empty while
  // the account already had data, and saving that form deleted the missing rows.
  if (live && loading && !state.profile.email) return <Skeleton />
  if (live && error && !state.profile.email)
    return <Alert kind="error">Your profile could not be loaded. {error}</Alert>
  // Remount the form when the account record changes so the fields always show
  // the saved profile instead of stale sample values.
  const signature = live ? (profileId ?? 'new') : 'demo'
  return (
    <ProfileForm
      key={signature}
      onboarding={onboarding}
      demo={demo}
      live={live}
      profileId={profileId}
      profile={state.profile}
      saveProfile={saveProfile}
    />
  )
}

function ProfileForm({
  onboarding,
  demo,
  live,
  profileId,
  profile,
  saveProfile,
}: {
  onboarding: boolean
  demo: boolean
  live: boolean
  profileId: string | null
  profile: ProfileRecord
  saveProfile: (profile: ProfileRecord) => Promise<void>
}) {
  const [skills, setSkills] = useState(profile.skills)
  const [skill, setSkill] = useState('')
  const [experiences, setExperiences] = useState(profile.experiences)
  const [educations, setEducations] = useState(profile.educations)
  const [message, setMessage] = useState('')
  // Saving touches the profile plus skills, experience and education, so the
  // button reports progress until every request finished.
  const [saving, setSaving] = useState(false)
  const [savedCount, setSavedCount] = useState(0)
  // Enter in the skill field adds the skill instead of submitting the profile.
  const addSkill = () => {
    const next = skill.trim()
    if (!next) return
    if (!skills.some((s) => s.toLowerCase() === next.toLowerCase())) setSkills([...skills, next])
    setSkill('')
  }
  const navigate = useNavigate()
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: profile,
  })
  const submit = handleSubmit(async (values) => {
    if (saving) return
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
    setMessage('')
    setSaving(true)
    try {
      await saveProfile({ ...values, skills, experiences, educations })
      setSavedCount((count) => count + 1)
      setMessage(demo ? 'Profile saved for this demo visit.' : 'Profile saved to your account.')
      if (onboarding) navigate('/resume')
    } catch (e) {
      setMessage((e as Error).message)
    } finally {
      setSaving(false)
    }
  })
  const saveLabel = onboarding ? 'Save and review resume' : 'Save profile'
  const helperText = saving
    ? 'Saving your profile, skills, work history and education…'
    : demo
      ? 'Demo changes are cleared on reload.'
      : 'Saving updates your account profile and its skills, experience, and education.'
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
      {live && (
        <ResumeImportPanel
          profileId={profileId}
          onImported={(records) => {
            // Merge, never replace: saving the profile syncs removals to the API.
            setSkills((current) => [
              ...new Map(
                [...current, ...records.skills].map((name): [string, string] => [
                  name.toLowerCase(),
                  name,
                ]),
              ).values(),
            ])
            setExperiences((current) => mergeRows(current, records.experiences, experienceKey))
            setEducations((current) => mergeRows(current, records.educations, educationKey))
          }}
        />
      )}
      <form className="profile-form" onSubmit={submit} noValidate>
        {message && (
          <Alert
            key={`profile-message-${savedCount}`}
            kind={message.startsWith('Profile saved') ? 'success' : 'error'}
          >
            {message}
          </Alert>
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
              <input
                value={skill}
                maxLength={100}
                onChange={(e) => setSkill(e.target.value)}
                onKeyDown={(event) => {
                  if (event.key !== 'Enter') return
                  event.preventDefault()
                  addSkill()
                }}
              />
            </label>
            <button type="button" className="secondary" disabled={!skill.trim()} onClick={addSkill}>
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
        {saving && (
          <div
            className="save-progress"
            role="progressbar"
            aria-label="Saving your profile"
            aria-valuetext="Saving"
          />
        )}
        <div className="form-actions">
          <small aria-live="polite">{helperText}</small>
          <button className={saving ? 'busy' : undefined} disabled={saving} aria-busy={saving}>
            {saving ? (
              <>
                <span className="spinner" aria-hidden="true" />
                Saving…
              </>
            ) : (
              saveLabel
            )}
          </button>
        </div>
      </form>
    </>
  )
}

const experienceKey = (row: { company_name: string; job_title: string; start_date: string }) =>
  `${row.company_name.trim().toLowerCase()}|${row.job_title.trim().toLowerCase()}|${row.start_date.slice(0, 10)}`
const educationKey = (row: { institution: string; degree: string; start_date: string }) =>
  `${row.institution.trim().toLowerCase()}|${row.degree.trim().toLowerCase()}|${row.start_date.slice(0, 10)}`

function mergeRows<T>(current: T[], incoming: T[], key: (row: T) => string): T[] {
  const seen = new Set(current.map(key))
  return [
    ...current,
    ...incoming.filter((row) => {
      const id = key(row)
      if (seen.has(id)) return false
      seen.add(id)
      return true
    }),
  ]
}

type ImportedRecords = {
  skills: string[]
  experiences: ProfileRecord['experiences']
  educations: ProfileRecord['educations']
}

/**
 * Resume upload for the profile itself. The preview endpoint only reads the
 * file; nothing is written until the account holder approves the details.
 */
function ResumeImportPanel({
  profileId,
  onImported,
}: {
  profileId: string | null
  onImported: (records: ImportedRecords) => void
}) {
  const { refresh } = useWorkspace()
  const [preview, setPreview] = useState<ResumePreview | null>(null)
  const [skills, setSkills] = useState('')
  const [approved, setApproved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function analyze(chosen?: File) {
    if (!chosen) return
    setPreview(null)
    setApproved(false)
    setMessage('')
    const problem = validateResume(chosen)
    if (problem) {
      setError(problem)
      return
    }
    if (!profileId) {
      setError('Save this profile once, then analyze your resume here.')
      return
    }
    setError('')
    setBusy(true)
    try {
      const result = await previewResume(profileId, chosen)
      setPreview(result)
      setSkills((result.skills ?? []).join(', '))
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function importRecords() {
    if (!preview || !profileId) return
    const names = skills
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
    const { payload, skipped } = buildResumeImport(preview, names)
    if (!payload.skills.length && !payload.experiences.length && !payload.educations.length) {
      setError('Nothing could be imported. Add at least one skill, or fill in the dates below.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const result = await importResume(profileId, payload)
      await refresh()
      onImported({
        skills: payload.skills,
        experiences: payload.experiences.map((row) => ({
          company_name: row.company_name,
          job_title: row.job_title,
          start_date: row.start_date,
          end_date: row.end_date ?? '',
        })),
        educations: payload.educations.map((row) => ({
          institution: row.institution,
          degree: row.degree,
          start_date: row.start_date,
          end_date: row.end_date ?? '',
        })),
      })
      setApproved(false)
      setMessage(
        `Added ${result.skills.created} skill${result.skills.created === 1 ? '' : 's'}, ${result.experiences.created} role${result.experiences.created === 1 ? '' : 's'} and ${result.educations.created} education entr${result.educations.created === 1 ? 'y' : 'ies'}. ${result.skills.skipped + result.experiences.skipped + result.educations.skipped} already on your profile were skipped.${skipped ? ` ${skipped} entr${skipped === 1 ? 'y' : 'ies'} with unclear dates still need to be added below.` : ''}`,
      )
    } catch (failure) {
      setError((failure as Error).message)
    } finally {
      setBusy(false)
    }
  }

  // Only shown when the AI parser was not used, so the account holder knows
  // why the details are rougher and that a fallback ran.
  const parserNotice =
    preview?.parser_used === 'local'
      ? ((preview.warnings ?? []).find((warning) => /AI parser/i.test(warning)) ??
        'The AI parser is unavailable, so local extraction was used instead.')
      : ''

  return (
    <section className="panel form-section">
      <div className="section-heading">
        <div>
          <h2>Import from your resume</h2>
          <p>
            Upload a PDF or DOCX. The API reads it and suggests skills, roles and education. Only
            the details you approve are saved.
          </p>
        </div>
        <FileText size={20} />
      </div>
      {!profileId && <Alert>Save this profile once to enable resume import.</Alert>}
      {error && <Alert kind="error">{error}</Alert>}
      {message && <Alert kind="success">{message}</Alert>}
      <div className="inline-form">
        <label>
          Resume file (PDF or DOCX, up to 5 MB)
          <input
            type="file"
            accept=".pdf,.docx"
            disabled={!profileId || busy}
            onChange={(event) => void analyze(event.target.files?.[0])}
          />
        </label>
        {busy && <small>{preview ? 'Importing…' : 'Reading the file with the AI parser…'}</small>}
      </div>
      {preview && (
        <>
          {parserNotice && (
            <Alert kind={preview.fallback_used ? 'error' : 'info'}>{parserNotice}</Alert>
          )}
          <p>
            <strong>{preview.parser_used === 'groq' ? 'AI extraction' : 'Local extraction'}</strong>
            {preview.fallback_used ? ' (fallback used)' : ''} found {(preview.skills ?? []).length}{' '}
            skills, {(preview.experiences ?? []).length} roles and{' '}
            {(preview.educations ?? []).length} education entries.
          </p>
          {(preview.experiences ?? []).length > 0 && (
            <p className="evidence">
              {(preview.experiences ?? [])
                .map((row) => [row.job_title, row.company_name].filter(Boolean).join(' at '))
                .filter(Boolean)
                .join(' · ')}
            </p>
          )}
          {(preview.educations ?? []).length > 0 && (
            <p className="evidence">
              {(preview.educations ?? [])
                .map((row) => [row.degree, row.institution].filter(Boolean).join(' — '))
                .filter(Boolean)
                .join(' · ')}
            </p>
          )}
          <label>
            Skills to import (comma separated)
            <textarea
              rows={3}
              value={skills}
              onChange={(event) => {
                setSkills(event.target.value)
                setMessage('')
              }}
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={approved}
              onChange={(event) => setApproved(event.target.checked)}
            />
            I reviewed these details and want to add them to my profile.
          </label>
          <button type="button" disabled={!approved || busy} onClick={importRecords}>
            {busy ? 'Importing…' : 'Add reviewed details'}
          </button>
        </>
      )}
    </section>
  )
}
