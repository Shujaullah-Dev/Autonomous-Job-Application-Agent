import { useState } from 'react'
import { Upload, FileText } from 'lucide-react'
import { useWorkspace } from '../app/workspace'
import { validateResume } from '../lib/api'
import { buildResumeImport, importResume, previewResume, type ResumePreview } from '../lib/live'
import { Alert } from '../components/ui'

const sampleSkills = ['React', 'TypeScript', 'CSS']

export function Resume() {
  const { demo, profileId, addSkills, refresh } = useWorkspace()
  const [file, setFile] = useState<File | null>(null)
  const [filename, setFilename] = useState('')
  const [error, setError] = useState('')
  const [preview, setPreview] = useState<ResumePreview | null>(null)
  const [sample, setSample] = useState(false)
  const [reviewed, setReviewed] = useState(false)
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [skills, setSkills] = useState(sampleSkills.join(', '))

  function choose(next?: File) {
    if (!next) return
    const problem = validateResume(next)
    setError(problem || '')
    setFilename(problem ? '' : next.name)
    setFile(problem ? null : next)
    setPreview(null)
    setSample(false)
    setReviewed(false)
    setSaved(false)
    setMessage('')
  }

  async function analyze() {
    if (!file) {
      setError('Choose a PDF or DOCX file first.')
      return
    }
    if (demo) {
      setSample(true)
      setSkills(sampleSkills.join(', '))
      setPreview(null)
      setReviewed(false)
      setSaved(false)
      return
    }
    if (!profileId) {
      setError('Complete your profile before analyzing a resume.')
      return
    }
    setBusy(true)
    setError('')
    setMessage('')
    try {
      const result = await previewResume(profileId, file)
      setPreview(result)
      setSkills((result.skills ?? []).join(', '))
      setReviewed(false)
      setSaved(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function importRecords() {
    const names = skills
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean)
    if (demo) {
      if (!names.length) {
        setError('Add at least one skill to import.')
        return
      }
      await addSkills(names)
      setSaved(true)
      setMessage('Approved sample skills added to the demo profile. Existing skills were kept.')
      return
    }
    if (!profileId) {
      setError('Complete your profile before importing resume details.')
      return
    }
    if (!preview) {
      setError('Analyze a resume first so its details can be imported.')
      return
    }
    const { payload, skipped } = buildResumeImport(preview, names)
    if (!payload.skills.length && !payload.experiences.length && !payload.educations.length) {
      setError('Nothing could be imported. Add a skill, or check the dates in the preview.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const result = await importResume(profileId, payload)
      setSaved(true)
      setMessage(
        `Added ${result.skills.created} skill${result.skills.created === 1 ? '' : 's'}, ${result.experiences.created} role${result.experiences.created === 1 ? '' : 's'} and ${result.educations.created} education entr${result.educations.created === 1 ? 'y' : 'ies'}. ${result.skills.skipped + result.experiences.skipped + result.educations.skipped} already on your profile were skipped.${skipped ? ` ${skipped} entr${skipped === 1 ? 'y' : 'ies'} with unclear dates were not imported.` : ''}`,
      )
      await refresh()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const openReview = Boolean(preview || sample)
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Your experience, in your words.</h1>
          <p>Review extracted details before adding them to your profile.</p>
        </div>
        <FileText className="heading-icon" />
      </div>
      {demo ? (
        <Alert>
          Demo preview uses a fixed sample. Your file stays on your device and is not parsed or
          uploaded.
        </Alert>
      ) : (
        <Alert>
          A preview sends the selected file to the API for text extraction. The file is not stored.
          Review every extracted detail before importing it.
        </Alert>
      )}
      {error && <Alert kind="error">{error}</Alert>}
      {message && <Alert kind="success">{message}</Alert>}
      <section className="panel form-section">
        <h2>Choose a resume</h2>
        <div
          className="upload-zone"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault()
            choose(e.dataTransfer.files[0])
          }}
        >
          <Upload size={30} />
          <h3>{filename || 'Drop a resume here'}</h3>
          <p>PDF or DOCX, up to 5 MB</p>
          <label className="file-picker">
            Choose file
            <input
              type="file"
              accept=".pdf,.docx"
              aria-label="Choose resume file"
              onChange={(e) => choose(e.target.files?.[0])}
            />
          </label>
        </div>
        <button className="secondary" disabled={busy} onClick={analyze}>
          {busy ? 'Analyzing…' : demo ? 'Open sample review' : 'Analyze resume'}
        </button>
      </section>
      {openReview && (
        <section className="panel form-section">
          <div className="section-heading">
            <h2>{demo ? 'Review sample details' : 'Review extracted details'}</h2>
            <span className="badge">
              {demo
                ? 'Fixed demo fixture'
                : preview
                  ? `${preview.parser_used} parser${preview.fallback_used ? ' · fallback used' : ''}`
                  : 'Preview'}
            </span>
          </div>
          {preview ? (
            <>
              {preview.parser_used === 'local' && (
                <Alert kind={preview.fallback_used ? 'error' : 'info'}>
                  {(preview.warnings ?? []).find((warning) => /AI parser/i.test(warning)) ??
                    'The AI parser is unavailable, so local extraction was used instead.'}
                </Alert>
              )}
              {preview.warnings?.length ? (
                <Alert>
                  {preview.warnings.length} warning{preview.warnings.length === 1 ? '' : 's'} from
                  extraction. Check the details below carefully.
                </Alert>
              ) : null}
              <div className="resume-snapshot">
                <h3>Detected history</h3>
                <p>
                  {(preview.experiences ?? [])
                    .map((row) => [row.job_title, row.company_name].filter(Boolean).join(' at '))
                    .filter(Boolean)
                    .join(' · ') || 'No work history detected.'}
                </p>
                <p>
                  {(preview.educations ?? [])
                    .map((row) => [row.degree, row.institution].filter(Boolean).join(' — '))
                    .filter(Boolean)
                    .join(' · ') || 'No education detected.'}
                </p>
              </div>
            </>
          ) : (
            <p>
              This sample is independent of your selected file. Contact, work history and education
              are edited in your profile.
            </p>
          )}
          <label>
            Skills to import (comma separated)
            <textarea
              value={skills}
              onChange={(e) => {
                setSkills(e.target.value)
                setSaved(false)
                setReviewed(false)
              }}
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(e) => setReviewed(e.target.checked)}
            />
            {demo
              ? 'I reviewed these sample skills and want to add them.'
              : 'I reviewed these details and want to add them to my profile.'}
          </label>
          <button disabled={!reviewed || saved || busy || !skills.trim()} onClick={importRecords}>
            {demo ? 'Import approved sample skills' : 'Import reviewed details'}
          </button>
        </section>
      )}
    </>
  )
}
