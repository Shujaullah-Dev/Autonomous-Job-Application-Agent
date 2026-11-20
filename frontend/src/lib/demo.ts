import type { Job, ApiSchema } from './api'

export type Profile = {
  full_name: string
  email: string
  location: string
  years_experience: number
  professional_summary: string
  skills: string[]
  experiences: { company_name: string; job_title: string; start_date: string; end_date: string }[]
  educations: { institution: string; degree: string; start_date: string; end_date: string }[]
}
export type Status = ApiSchema['ApplicationSummary']['status']
export type Application = {
  id: string
  jobId: number
  status: Status
  revision: number
  letter: string
  resumeSnapshot: Profile
  revisions: { number: number; letter: string; at: string }[]
  history: { status: Status; at: string; note: string }[]
  handoffRevision?: number
}
export type Workflow = {
  id: string
  jobIds: number[]
  approvedIds: number[]
  status: 'pending_review' | 'approved' | 'rejected' | 'no_matches'
}
export type FollowUp = {
  id: string
  applicationId: string
  due: string
  note: string
  state: 'pending' | 'completed' | 'dismissed'
}
export type Interview = {
  id: string
  applicationId: string
  title: string
  start: string
  end: string
  mode: 'video' | 'phone' | 'onsite'
  location: string
  status: 'scheduled' | 'completed' | 'cancelled'
  version: number
  reminders: number[]
}
export type Notification = { id: string; title: string; at: string; read: boolean }
export type DemoState = {
  profile: Profile
  jobs: Job[]
  applications: Application[]
  workflows: Workflow[]
  followUps: FollowUp[]
  interviews: Interview[]
  notifications: Notification[]
}
const now = new Date().toISOString()
export const demoJobs: Job[] = [
  [
    1,
    'Frontend Engineer',
    'Northstar Studio',
    'Remote',
    'remote',
    'React, TypeScript, accessibility',
    85000,
    115000,
  ],
  [
    2,
    'Product Engineer',
    'Fieldwork',
    'London, UK',
    'hybrid',
    'React, Python, product design',
    70000,
    95000,
  ],
  [
    3,
    'Full Stack Developer',
    'Common Ground',
    'Remote',
    'remote',
    'TypeScript, FastAPI, PostgreSQL',
    80000,
    110000,
  ],
  [
    4,
    'UI Engineer',
    'Forma',
    'Berlin, Germany',
    'onsite',
    'CSS, React, design systems',
    65000,
    90000,
  ],
  [
    5,
    'Software Engineer',
    'Papertrail',
    'Toronto, Canada',
    null,
    'Python, APIs, testing',
    null,
    null,
  ],
  [
    6,
    'React Developer',
    'Cedar Labs',
    'Remote',
    'remote',
    'React, TypeScript, testing',
    75000,
    100000,
  ],
].map(([id, title, company, location, mode, description, min, max]) => ({
  id: id as number,
  title: title as string,
  company_name: company as string,
  location: location as string,
  work_mode: mode as Job['work_mode'],
  description: `Example role: ${description}. Build thoughtful software with a small team. These are fictional jobs for exploring the interface.`,
  salary_min: min as number | null,
  salary_max: max as number | null,
  salary_currency: min ? 'USD' : null,
  source: 'Synthetic demo',
  employment_type: 'Full-time',
  posted_at: now,
  created_at: now,
  updated_at: now,
  is_active: true,
  job_url: 'https://example.com',
}))
const initialProfile = (): Profile => ({
  full_name: 'Alex Morgan',
  email: 'alex@example.com',
  location: 'Remote',
  years_experience: 3,
  professional_summary:
    'Frontend developer building accessible web applications with React and TypeScript.',
  skills: ['React', 'TypeScript', 'CSS', 'Python'],
  experiences: [
    {
      company_name: 'Example Studio',
      job_title: 'Frontend Developer',
      start_date: '2023-01-01',
      end_date: '',
    },
  ],
  educations: [
    {
      institution: 'Example University',
      degree: 'BSc Computer Science',
      start_date: '2018-09-01',
      end_date: '2022-06-01',
    },
  ],
})
export const seed = (): DemoState => ({
  profile: initialProfile(),
  jobs: demoJobs,
  workflows: [],
  followUps: [],
  interviews: [],
  notifications: [],
  applications: [
    {
      id: 'example-draft',
      jobId: 1,
      status: 'draft',
      revision: 1,
      resumeSnapshot: initialProfile(),
      letter:
        'Hello Northstar Studio team,\n\nI would like to apply for the Frontend Engineer role. My experience with React, TypeScript and accessible interfaces fits the work described in your listing. I would welcome the chance to discuss how I can contribute.\n\nAlex Morgan',
      revisions: [],
      history: [
        { status: 'draft', at: now, note: 'Example draft created. Nothing has been submitted.' },
      ],
    },
  ],
})
export function match(job: Job, skills: string[]) {
  const matched = skills.filter((skill) =>
    job.description.toLowerCase().includes(skill.toLowerCase()),
  )
  return { score: Math.min(95, 35 + matched.length * 18), matched }
}
export const transitions: Record<Status, Status[]> = {
  draft: ['ready', 'withdrawn'],
  ready: ['submitted', 'withdrawn'],
  submitted: ['interview', 'rejected', 'withdrawn'],
  interview: ['offered', 'rejected', 'withdrawn'],
  offered: [],
  rejected: [],
  withdrawn: [],
}
export function updateStatus(
  app: Application,
  status: Status,
  reviewed = false,
  submitted = false,
): Application {
  if (!transitions[app.status].includes(status))
    throw new Error('This status change is not allowed.')
  if (status === 'ready' && !reviewed) throw new Error('Review your materials first.')
  if (status === 'submitted' && !submitted)
    throw new Error('Confirm that you submitted on the employer site.')
  return {
    ...app,
    status,
    history: [
      ...app.history,
      {
        status,
        at: new Date().toISOString(),
        note:
          status === 'submitted'
            ? 'Submission reported by you. No employer confirmation received.'
            : 'Status updated by you.',
      },
    ],
  }
}
export function editDraft(app: Application, letter: string, expected: number): Application {
  if (app.revision !== expected) throw new Error('This draft changed. Reload before saving.')
  if (!['draft', 'ready'].includes(app.status))
    throw new Error('This application can no longer be edited.')
  if (letter.trim().length < 20 || letter.length > 15000)
    throw new Error('Use between 20 and 15,000 characters.')
  return {
    ...app,
    letter,
    revision: app.revision + 1,
    handoffRevision: undefined,
    revisions: [
      ...app.revisions,
      { number: app.revision, letter: app.letter, at: new Date().toISOString() },
    ],
  }
}
export function prepareHandoff(
  app: Application,
  expected: number,
  reviewed: boolean,
  manual: boolean,
): Application {
  if (app.revision !== expected)
    throw new Error('This draft changed. Reload before preparing a handoff.')
  if (app.status !== 'ready' || !reviewed || !manual)
    throw new Error('Mark this draft ready and confirm both review checks.')
  return { ...app, handoffRevision: expected }
}
export function interviewConflict(
  interviews: Interview[],
  start: string,
  end: string,
  exclude?: string,
) {
  return interviews.some(
    (i) =>
      i.id !== exclude &&
      i.status === 'scheduled' &&
      new Date(start) < new Date(i.end) &&
      new Date(end) > new Date(i.start),
  )
}
