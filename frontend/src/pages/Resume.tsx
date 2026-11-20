import { useState } from 'react'
import { Upload, FileText } from 'lucide-react'
import { useDemo } from '../app/store'
import { validateResume } from '../lib/api'
import { Alert } from '../components/ui'

export function Resume() {
  const { setState } = useDemo()
  const [filename, setFilename] = useState('')
  const [error, setError] = useState('')
  const [preview, setPreview] = useState(false)
  const [reviewed, setReviewed] = useState(false)
  const [saved, setSaved] = useState(false)
  const [skills, setSkills] = useState('React, TypeScript, CSS')
  function choose(file?: File) {
    if (!file) return
    const problem = validateResume(file)
    setError(problem || '')
    setFilename(problem ? '' : file.name)
    setPreview(false)
    setReviewed(false)
    setSaved(false)
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Your experience, in your words.</h1>
          <p>Review extracted details before adding them to your profile.</p>
        </div>
        <FileText className="heading-icon" />
      </div>
      <Alert>
        Demo preview uses a fixed sample. Your file stays on your device and is not parsed or
        uploaded. Live resume processing is blocked until private API protection is available.
      </Alert>
      {error && <Alert kind="error">{error}</Alert>}
      {saved && (
        <Alert kind="success">
          Approved sample skills added to the demo profile. Existing skills were kept.
        </Alert>
      )}
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
        <button
          className="secondary"
          onClick={() => {
            setPreview(true)
            setSaved(false)
            setReviewed(false)
          }}
        >
          Open sample review
        </button>
      </section>
      {preview && (
        <section className="panel form-section">
          <div className="section-heading">
            <h2>Review sample details</h2>
            <span className="badge">Fixed demo fixture</span>
          </div>
          <p>
            This sample is independent of your selected file. Live previews will identify the parser
            and any fallback warnings.
          </p>
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
          <div className="resume-snapshot">
            <h3>Contact and history</h3>
            <p>
              Contact, work history and education are edited in your profile. No contact data is
              inferred from this demo.
            </p>
          </div>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(e) => setReviewed(e.target.checked)}
            />
            I reviewed these sample skills and want to add them.
          </label>
          <button
            disabled={!reviewed || saved || !skills.trim()}
            onClick={() => {
              setState((s) => ({
                ...s,
                profile: {
                  ...s.profile,
                  skills: [
                    ...new Map(
                      [
                        ...s.profile.skills,
                        ...skills
                          .split(',')
                          .map((v) => v.trim())
                          .filter(Boolean),
                      ].map((v) => [v.toLowerCase(), v]),
                    ).values(),
                  ],
                },
              }))
              setSaved(true)
            }}
          >
            Import approved sample skills
          </button>
        </section>
      )}
    </>
  )
}
