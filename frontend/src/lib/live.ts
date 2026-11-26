import { api, ApiError, type ApiSchema, type Job } from './api'
import type { Application, DemoState, Profile, Workflow } from './demo'

const nowIso = () => new Date().toISOString()
const jsonRequest = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})
const candidatePath = (candidateId: string) => `/api/v1/candidates/${candidateId}`

export const emptyProfile = (): Profile => ({
  full_name: '',
  email: '',
  location: '',
  years_experience: 0,
  professional_summary: '',
  skills: [],
  experiences: [],
  educations: [],
})
export const emptyState = (): DemoState => ({
  profile: emptyProfile(),
  jobs: [],
  applications: [],
  workflows: [],
  followUps: [],
  interviews: [],
  notifications: [],
})

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}
function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((row): row is string => typeof row === 'string') : []
}

function jobStub(
  id: number,
  title: string,
  companyName: string,
  description = '',
  workMode: Job['work_mode'] = null,
  jobUrl = '',
): Job {
  const stamp = nowIso()
  return {
    id,
    title,
    company_name: companyName,
    location: null,
    description,
    job_url: jobUrl,
    source: null,
    employment_type: null,
    work_mode: workMode,
    salary_min: null,
    salary_max: null,
    salary_currency: null,
    posted_at: null,
    is_active: true,
    created_at: stamp,
    updated_at: stamp,
  }
}

/** Resolve the candidate profile owned by the verified account, or null. */
export async function resolveCandidate(): Promise<string | null> {
  try {
    const profile = await api<ApiSchema['CandidateResponse']>('/api/v1/candidates/me')
    return profile.id
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

function mapSnapshot(raw: Record<string, unknown> | undefined, profile: Profile): Profile {
  if (!raw) return { ...profile }
  const experiences = Array.isArray(raw.experiences)
    ? raw.experiences.map((row) => {
        if (typeof row === 'string')
          return { company_name: row, job_title: '', start_date: '', end_date: '' }
        const item = row as Record<string, unknown>
        return {
          company_name: text(item.company_name),
          job_title: text(item.job_title),
          start_date: text(item.start_date),
          end_date: text(item.end_date),
        }
      })
    : []
  const educations = Array.isArray(raw.educations)
    ? raw.educations.map((row) => {
        const item = row as Record<string, unknown>
        return {
          institution: text(item.institution),
          degree: text(item.degree),
          start_date: text(item.start_date),
          end_date: text(item.end_date),
        }
      })
    : []
  return {
    full_name: text(raw.candidate_name, profile.full_name),
    email: text(raw.candidate_email, profile.email),
    location: profile.location,
    years_experience: profile.years_experience,
    professional_summary: profile.professional_summary,
    skills: stringList(raw.relevant_skills ?? raw.skills),
    experiences,
    educations,
  }
}

function ensureJob(jobs: Job[], jobId: number, title: string, company: string): void {
  if (jobs.some((job) => job.id === jobId)) return
  jobs.push(jobStub(jobId, title, company))
}

function ensureApplication(
  applications: Application[],
  jobs: Job[],
  applicationId: string,
  jobTitle: string,
): void {
  if (applications.some((application) => application.id === applicationId)) return
  const jobId = -applications.length - 1
  ensureJob(jobs, jobId, jobTitle, '')
  applications.push({
    id: applicationId,
    jobId,
    status: 'submitted',
    revision: 1,
    letter: '',
    resumeSnapshot: emptyProfile(),
    revisions: [],
    history: [],
  })
}

const workflowKey = (userId: string) => `job-agent-workflows:${userId}`
function readWorkflowIds(userId: string): string[] {
  try {
    const raw = localStorage.getItem(workflowKey(userId))
    const parsed: unknown = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed)
      ? parsed.filter((row): row is string => typeof row === 'string')
      : []
  } catch {
    return []
  }
}
export function rememberWorkflow(userId: string, workflowId: string): void {
  const ids = readWorkflowIds(userId)
  if (!ids.includes(workflowId)) ids.push(workflowId)
  try {
    localStorage.setItem(workflowKey(userId), JSON.stringify(ids.slice(-10)))
  } catch {
    // Storage can be unavailable in private modes; the workflow still works in this visit.
  }
}

export async function loadLiveState(
  candidateId: string | null,
  userId: string,
): Promise<{ state: DemoState; hasProfile: boolean }> {
  const state = emptyState()
  const jobList = await api<ApiSchema['JobListResponse']>('/api/v1/jobs?limit=50')
  state.jobs = jobList.items

  if (!candidateId) return { state, hasProfile: false }

  const [profile, skills, experiences, educations, applicationList, followList, interviewList] =
    await Promise.all([
      api<ApiSchema['CandidateResponse']>('/api/v1/candidates/me'),
      api<ApiSchema['SkillResponse'][]>(`${candidatePath(candidateId)}/skills`),
      api<ApiSchema['ExperienceResponse'][]>(`${candidatePath(candidateId)}/experiences`),
      api<ApiSchema['EducationResponse'][]>(`${candidatePath(candidateId)}/education`),
      api<ApiSchema['ApplicationListResponse']>(
        `${candidatePath(candidateId)}/applications?limit=50`,
      ),
      api<ApiSchema['FollowUpListResponse']>(`${candidatePath(candidateId)}/follow-ups?limit=100`),
      api<ApiSchema['InterviewList']>(`${candidatePath(candidateId)}/interviews?limit=50`),
    ])

  state.profile = {
    full_name: profile.full_name,
    email: profile.email,
    location: profile.location ?? '',
    years_experience: profile.years_experience ?? 0,
    professional_summary: profile.professional_summary ?? '',
    skills: skills.map((row) => row.name),
    experiences: experiences.map((row) => ({
      company_name: row.company_name,
      job_title: row.job_title,
      start_date: row.start_date,
      end_date: row.end_date ?? '',
    })),
    educations: educations.map((row) => ({
      institution: row.institution,
      degree: row.degree,
      start_date: row.start_date,
      end_date: row.end_date ?? '',
    })),
  }

  const details = await Promise.all(
    applicationList.items
      .slice(0, 25)
      .map((summary) =>
        api<ApiSchema['ApplicationDetailResponse']>(
          `${candidatePath(candidateId)}/applications/${summary.id}`,
        ).catch(() => null),
      ),
  )
  state.applications = applicationList.items.map((summary, index) => {
    ensureJob(state.jobs, summary.job_id, summary.job_title, summary.company_name)
    const detail = details[index]
    return {
      id: summary.id,
      jobId: summary.job_id,
      status: summary.status,
      revision: summary.current_revision,
      letter: detail?.latest_draft.cover_letter ?? '',
      resumeSnapshot: mapSnapshot(detail?.latest_draft.resume_snapshot, state.profile),
      revisions:
        detail?.revisions.map((revision) => ({
          number: revision.revision_number,
          letter: revision.cover_letter,
          at: revision.created_at,
        })) ?? [],
      history:
        detail?.history.map((event) => ({
          status: event.new_status,
          at: event.created_at,
          note: event.note || `Status changed to ${event.new_status}.`,
        })) ?? [],
    }
  })

  state.followUps = followList.items.map((row) => {
    ensureApplication(state.applications, state.jobs, row.application_id, row.job_title)
    return {
      id: row.id,
      applicationId: row.application_id,
      due: row.due_at,
      note: row.note ?? '',
      state: row.state,
    }
  })

  const interviewDetails = await Promise.all(
    interviewList.items.map((row) =>
      api<ApiSchema['InterviewDetail']>(`${candidatePath(candidateId)}/interviews/${row.id}`).catch(
        () => null,
      ),
    ),
  )
  state.interviews = interviewList.items.map((row, index) => {
    ensureApplication(state.applications, state.jobs, row.application_id, 'Application')
    return {
      id: row.id,
      applicationId: row.application_id,
      title: row.title,
      start: row.starts_at,
      end: row.ends_at,
      mode: row.mode,
      location: row.location_or_link ?? '',
      status: row.status,
      version: row.version,
      reminders:
        interviewDetails[index]?.reminders
          .filter((reminder) => reminder.state !== 'cancelled')
          .map((reminder) => reminder.minutes_before) ?? [],
    }
  })

  const notificationList = await api<ApiSchema['NotificationList']>(
    `${candidatePath(candidateId)}/interview-notifications?unread_only=false&limit=100`,
  )
  const versionById = new Map(
    state.interviews.map((interview) => [interview.id, interview.version]),
  )
  state.notifications = notificationList.items.map((row) => ({
    id: `${row.interview_id}:${versionById.get(row.interview_id) ?? 0}:${row.minutes_before}`,
    title: `${row.interview_title} · ${row.job_title}`,
    at: row.due_at,
    read: row.state === 'read',
    apiId: row.id,
  }))

  const workflowIds = readWorkflowIds(userId)
  const workflowRows = await Promise.all(
    workflowIds.map((workflowId) =>
      api<ApiSchema['WorkflowResponse']>(
        `${candidatePath(candidateId)}/workflows/${workflowId}`,
      ).catch(() => null),
    ),
  )
  state.workflows = workflowRows
    .filter((row): row is ApiSchema['WorkflowResponse'] => row !== null)
    .map((row) => {
      const scores: Record<number, number> = {}
      const summaries: Record<number, string> = {}
      for (const job of row.shortlist) {
        scores[job.job_id] = Math.round(job.score)
        summaries[job.job_id] = job.summary
        if (!state.jobs.some((existing) => existing.id === job.job_id)) {
          state.jobs.push(
            jobStub(job.job_id, job.title, '', job.summary, job.work_mode as Job['work_mode']),
          )
        }
      }
      const workflow: Workflow = {
        id: row.workflow_id,
        jobIds: row.shortlist.map((job) => job.job_id),
        approvedIds: row.approved_job_ids,
        status: row.status,
        scores,
        summaries,
      }
      return workflow
    })

  return { state, hasProfile: true }
}

export async function startWorkflow(
  candidateId: string,
  userId: string,
  workMode: string,
): Promise<string> {
  const workflow = await api<ApiSchema['WorkflowResponse']>(
    `${candidatePath(candidateId)}/workflows`,
    // The ranker's default threshold (50) is above the scores most profiles
    // reach, which made every shortlist empty. Mirror the ranked job list.
    jsonRequest('POST', { work_mode: workMode || null, min_score: 0, limit: 5 }),
  )
  rememberWorkflow(userId, workflow.workflow_id)
  return workflow.workflow_id
}
export async function reviewWorkflow(
  candidateId: string,
  workflowId: string,
  decision: 'approve' | 'reject',
  approvedJobIds: number[],
): Promise<void> {
  await api(`${candidatePath(candidateId)}/workflows/${workflowId}/review`, {
    ...jsonRequest('POST', { decision, approved_job_ids: approvedJobIds }),
  })
}
export async function createTrackedApplication(
  candidateId: string,
  workflowId: string,
  jobId: number,
): Promise<string> {
  const application = await api<ApiSchema['ApplicationDetailResponse']>(
    `${candidatePath(candidateId)}/workflows/${workflowId}/tracked-applications/${jobId}`,
    { method: 'POST' },
  )
  return application.id
}
export async function saveDraft(
  candidateId: string,
  applicationId: string,
  letter: string,
  expectedRevision: number,
): Promise<void> {
  await api(`${candidatePath(candidateId)}/applications/${applicationId}/draft`, {
    ...jsonRequest('PATCH', {
      expected_revision: expectedRevision,
      cover_letter: letter,
    }),
  })
}
export async function changeStatus(
  candidateId: string,
  applicationId: string,
  status: string,
  reviewed: boolean,
  submitted: boolean,
): Promise<void> {
  await api(`${candidatePath(candidateId)}/applications/${applicationId}/status`, {
    ...jsonRequest('POST', {
      new_status: status,
      confirm_reviewed: reviewed,
      confirm_external_submission: submitted,
    }),
  })
}
export async function prepareHandoff(
  candidateId: string,
  applicationId: string,
  expectedRevision: number,
): Promise<void> {
  await api(`${candidatePath(candidateId)}/applications/${applicationId}/manual-handoff`, {
    ...jsonRequest('POST', {
      expected_revision: expectedRevision,
      confirm_reviewed: true,
      confirm_manual_handoff: true,
    }),
  })
}
export async function createFollowUp(
  candidateId: string,
  applicationId: string,
  dueAt: string,
  note: string,
): Promise<void> {
  await api(`${candidatePath(candidateId)}/applications/${applicationId}/follow-ups`, {
    ...jsonRequest('POST', { kind: 'follow_up', due_at: dueAt, note: note || null }),
  })
}
export async function resolveFollowUp(
  candidateId: string,
  applicationId: string,
  followUpId: string,
  complete: boolean,
): Promise<void> {
  await api(
    `${candidatePath(candidateId)}/applications/${applicationId}/follow-ups/${followUpId}/resolve`,
    jsonRequest('POST', { action: complete ? 'complete' : 'dismiss' }),
  )
}
export async function createInterview(
  candidateId: string,
  applicationId: string,
  input: {
    title: string
    starts_at: string
    ends_at: string
    mode: string
    location_or_link: string | null
    reminder_minutes: number[]
  },
): Promise<void> {
  await api(`${candidatePath(candidateId)}/applications/${applicationId}/interviews`, {
    ...jsonRequest('POST', input),
  })
}
export async function updateInterview(
  candidateId: string,
  interviewId: string,
  input: {
    expected_version: number
    starts_at: string
    ends_at: string
    reminder_minutes: number[]
  },
): Promise<void> {
  await api(`${candidatePath(candidateId)}/interviews/${interviewId}`, {
    ...jsonRequest('PATCH', input),
  })
}
export async function interviewAction(
  candidateId: string,
  interviewId: string,
  action: 'cancel' | 'complete',
  expectedVersion: number,
): Promise<void> {
  await api(`${candidatePath(candidateId)}/interviews/${interviewId}/action`, {
    ...jsonRequest('POST', { action, expected_version: expectedVersion }),
  })
}
export async function refreshNotifications(candidateId: string): Promise<string> {
  const result = await api<ApiSchema['NotificationRefreshResult']>(
    `${candidatePath(candidateId)}/interview-notifications/refresh`,
    { method: 'POST' },
  )
  return result.message
}
export async function readNotification(candidateId: string, notificationId: string): Promise<void> {
  await api(`${candidatePath(candidateId)}/interview-notifications/${notificationId}/read`, {
    method: 'POST',
  })
}

export async function addSkill(candidateId: string, name: string): Promise<void> {
  await api(`${candidatePath(candidateId)}/skills`, jsonRequest('POST', { name }))
}

async function syncSkills(candidateId: string, desired: string[]): Promise<void> {
  const stored = await api<ApiSchema['SkillResponse'][]>(`${candidatePath(candidateId)}/skills`)
  const wanted = new Set(desired.map((name) => name.toLowerCase()))
  for (const row of stored) {
    if (!wanted.has(row.name.toLowerCase())) {
      await api(`${candidatePath(candidateId)}/skills/${row.id}`, { method: 'DELETE' })
    }
  }
  const saved = new Set(stored.map((row) => row.name.toLowerCase()))
  for (const name of desired) {
    if (!saved.has(name.toLowerCase())) {
      await api(`${candidatePath(candidateId)}/skills`, jsonRequest('POST', { name }))
    }
  }
}

async function syncExperiences(
  candidateId: string,
  desired: Profile['experiences'],
): Promise<void> {
  const stored = await api<ApiSchema['ExperienceResponse'][]>(
    `${candidatePath(candidateId)}/experiences`,
  )
  const key = (row: { company_name: string; job_title: string; start_date: string }) =>
    `${row.company_name.trim().toLowerCase()}|${row.job_title.trim().toLowerCase()}|${row.start_date.slice(0, 10)}`
  const wanted = new Set(desired.map(key))
  for (const row of stored) {
    if (!wanted.has(key(row))) {
      await api(`${candidatePath(candidateId)}/experiences/${row.id}`, { method: 'DELETE' })
    }
  }
  const saved = new Set(stored.map(key))
  for (const row of desired) {
    if (saved.has(key(row))) continue
    await api(
      `${candidatePath(candidateId)}/experiences`,
      jsonRequest('POST', {
        company_name: row.company_name,
        job_title: row.job_title,
        start_date: row.start_date,
        end_date: row.end_date || null,
        is_current: !row.end_date,
      }),
    )
  }
}

async function syncEducations(candidateId: string, desired: Profile['educations']): Promise<void> {
  const stored = await api<ApiSchema['EducationResponse'][]>(
    `${candidatePath(candidateId)}/education`,
  )
  const key = (row: { institution: string; degree: string; start_date: string }) =>
    `${row.institution.trim().toLowerCase()}|${row.degree.trim().toLowerCase()}|${row.start_date.slice(0, 10)}`
  const wanted = new Set(desired.map(key))
  for (const row of stored) {
    if (!wanted.has(key(row))) {
      await api(`${candidatePath(candidateId)}/education/${row.id}`, { method: 'DELETE' })
    }
  }
  const saved = new Set(stored.map(key))
  for (const row of desired) {
    if (saved.has(key(row))) continue
    await api(
      `${candidatePath(candidateId)}/education`,
      jsonRequest('POST', {
        institution: row.institution,
        degree: row.degree,
        start_date: row.start_date,
        end_date: row.end_date || null,
      }),
    )
  }
}

export type JobRefreshStatus = {
  running: boolean
  trigger: string | null
  started_at: string | null
  finished_at: string | null
  created: number
  updated: number
  skipped: number
  deactivated: number
  possible_duplicates: number
  sources_total: number
  sources_ok: number
  failures: { source: string; reason: string }[]
  enabled: boolean
  interval_hours: number
  message: string | null
}

/** Latest import run, and whether one is in progress. */
export function jobRefreshStatus(): Promise<JobRefreshStatus> {
  return api<JobRefreshStatus>('/api/v1/jobs/refresh/status')
}

/** Ask the API to import current listings in the background. */
export function startJobRefresh(): Promise<{
  started: boolean
  reason: string
  status: JobRefreshStatus
}> {
  return api('/api/v1/jobs/refresh', { method: 'POST' })
}

export async function saveProfile(candidateId: string | null, profile: Profile): Promise<void> {
  const payload = {
    full_name: profile.full_name,
    email: profile.email,
    phone: null,
    location: profile.location || null,
    professional_summary: profile.professional_summary || null,
    years_experience: profile.years_experience,
  }
  const saved = candidateId
    ? await api<ApiSchema['CandidateResponse']>(candidatePath(candidateId), {
        ...jsonRequest('PATCH', payload),
      })
    : await api<ApiSchema['CandidateResponse']>('/api/v1/candidates', {
        ...jsonRequest('POST', payload),
      })
  await syncSkills(saved.id, profile.skills)
  await syncExperiences(saved.id, profile.experiences)
  await syncEducations(saved.id, profile.educations)
}

/* ------------------------------------------------------------------ */
/* Resume upload: preview, normalise and import into the profile.      */
/* ------------------------------------------------------------------ */

export type ResumePreview = ApiSchema['ResumeAnalysisResponse']
export type MatchItem = ApiSchema['RecommendationItem']
export type MatchResult = {
  items: MatchItem[]
  mode: ApiSchema['RecommendationResponse']['ranking_mode']
  warnings: string[]
  evaluated: number
}
export type ResumeImportPayload = {
  approved: true
  skills: string[]
  experiences: {
    company_name: string
    job_title: string
    start_date: string
    end_date: string | null
    is_current: boolean
  }[]
  educations: {
    institution: string
    degree: string
    start_date: string
    end_date: string | null
  }[]
}

const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
const pad = (value: number) => String(value).padStart(2, '0')

/**
 * Normalise a resume date into `YYYY-MM-DD`. Extraction returns ISO dates for
 * some parsers and free text such as `2021`, `Mar 2021` or `Present` for
 * others, while the import API only accepts real dates.
 */
export function resumeDate(value: string | null | undefined): string | null {
  if (!value) return null
  const text = value.trim()
  if (!text) return null
  if (/^\d{4}-\d{2}-\d{2}/.test(text)) return text.slice(0, 10)
  if (/\b(present|current|now|ongoing|today)\b/i.test(text)) return null
  const monthYear = text.match(/(\d{1,2})[/.](\d{4})/)
  if (monthYear) return `${monthYear[2]}-${pad(Number(monthYear[1]))}-01`
  const year = text.match(/(?:19|20)\d{2}/)
  if (!year) return null
  const month = MONTHS.findIndex((name) => new RegExp(`(^|[^a-z])${name}`, 'i').test(text))
  return `${year[0]}-${pad(month >= 0 ? month + 1 : 1)}-01`
}

/**
 * Build the reviewed import payload. Records whose dates cannot be
 * normalised are skipped instead of being written with invented dates.
 */
export function buildResumeImport(
  preview: ResumePreview,
  skills: string[],
): { payload: ResumeImportPayload; skipped: number } {
  let skipped = 0
  const experiences: ResumeImportPayload['experiences'] = []
  for (const row of preview.experiences ?? []) {
    const start = resumeDate(row.start_date) ?? resumeDate(row.start_date_text)
    const end = resumeDate(row.end_date) ?? resumeDate(row.end_date_text)
    const company = row.company_name?.trim() ?? ''
    const title = row.job_title?.trim() ?? ''
    if (!company || !title || !start || (end && end < start)) {
      skipped += 1
      continue
    }
    experiences.push({
      company_name: company,
      job_title: title,
      start_date: start,
      end_date: end,
      is_current: !end,
    })
  }

  const educations: ResumeImportPayload['educations'] = []
  for (const row of preview.educations ?? []) {
    const start = resumeDate(row.start_date) ?? resumeDate(row.start_date_text)
    const end = resumeDate(row.end_date) ?? resumeDate(row.end_date_text)
    const institution = row.institution?.trim() ?? ''
    const degree = row.degree?.trim() ?? ''
    if (!institution || !degree || !start || (end && end < start)) {
      skipped += 1
      continue
    }
    educations.push({ institution, degree, start_date: start, end_date: end })
  }

  const unique = [
    ...new Map(
      skills
        .map((name) => name.trim())
        .filter((name) => name && name.length <= 100)
        .map((name): [string, string] => [name.toLowerCase(), name]),
    ).values(),
  ].slice(0, 100)

  return {
    payload: { approved: true, skills: unique, experiences, educations },
    skipped,
  }
}

export async function previewResume(candidateId: string, file: File): Promise<ResumePreview> {
  const form = new FormData()
  form.append('file', file)
  return api<ResumePreview>(`${candidatePath(candidateId)}/resume/preview`, {
    method: 'POST',
    body: form,
  })
}

export async function importResume(
  candidateId: string,
  payload: ResumeImportPayload,
): Promise<ApiSchema['ResumeImportResponse']> {
  return api<ApiSchema['ResumeImportResponse']>(
    `${candidatePath(candidateId)}/resume/import`,
    jsonRequest('POST', payload),
  )
}

/**
 * Resume-based job ranking. Uses the hybrid ranker and falls back to the
 * rule-based ranker when vector search is unavailable, so a scoring outage
 * never hides the job list.
 */
export async function loadMatches(candidateId: string, signal?: AbortSignal): Promise<MatchResult> {
  const request = (mode: 'hybrid' | 'rules') => {
    const params = new URLSearchParams({ mode, min_score: '0', limit: '50' })
    return api<ApiSchema['RecommendationResponse']>(
      `${candidatePath(candidateId)}/recommendations?${params}`,
      { signal },
    )
  }
  const result = await request('hybrid').catch((error: unknown) => {
    if (error instanceof ApiError && error.status === 503) return request('rules')
    throw error
  })
  return {
    items: result.items,
    mode: result.ranking_mode,
    warnings: result.warnings,
    evaluated: result.evaluated_jobs,
  }
}
