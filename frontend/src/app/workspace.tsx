import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useAuth } from '../features/auth/AuthProvider'
import { useDemo } from './store'
import {
  editDraft,
  interviewConflict,
  match,
  prepareHandoff as prepareDemoHandoff,
  updateStatus,
  type Application,
  type DemoState,
  type Interview,
  type Profile,
  type Status,
} from '../lib/demo'
import * as live from '../lib/live'

type InterviewInput = {
  id?: string
  applicationId: string
  title: string
  start: string | Date
  end: string | Date
  mode: Interview['mode']
  location: string
  reminders: number[]
  version?: number
}

type Workspace = {
  demo: boolean
  live: boolean
  loading: boolean
  error: string
  profileId: string | null
  hasProfile: boolean
  state: DemoState
  refresh: () => Promise<void>
  reset: () => void
  saveProfile: (profile: Profile) => Promise<void>
  addSkills: (names: string[]) => Promise<void>
  startWorkflow: (workMode: string) => Promise<string>
  reviewWorkflow: (workflowId: string, approvedJobIds: number[]) => Promise<void>
  createDraft: (workflowId: string, jobId: number) => Promise<string>
  saveDraft: (applicationId: string, letter: string, expected: number) => Promise<void>
  changeStatus: (
    applicationId: string,
    status: Status,
    reviewed: boolean,
    submitted: boolean,
  ) => Promise<void>
  prepareHandoff: (applicationId: string, expected: number) => Promise<void>
  createFollowUp: (applicationId: string, dueISO: string, note: string) => Promise<void>
  resolveFollowUp: (applicationId: string, followUpId: string, complete: boolean) => Promise<void>
  saveInterview: (input: InterviewInput) => Promise<void>
  interviewAction: (
    interviewId: string,
    action: 'cancelled' | 'completed',
    version: number,
  ) => Promise<void>
  refreshNotifications: () => Promise<string>
  readNotification: (notificationId: string) => Promise<void>
}

const Context = createContext<Workspace | null>(null)

const errorText = (error: unknown) =>
  error instanceof Error ? error.message : 'The request failed. Try again later.'

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { state: demoState, setState: setDemoState, reset: resetDemo } = useDemo()
  const { demo, session } = useAuth()
  const [liveState, setLiveState] = useState<DemoState | null>(null)
  const [profileId, setProfileId] = useState<string | null>(null)
  const [hasProfile, setHasProfile] = useState(false)
  const [loading, setLoading] = useState(!demo)
  const [error, setError] = useState('')

  const userId = session?.user.id

  const refresh = useCallback(async () => {
    if (demo || !userId) {
      setLiveState(null)
      setProfileId(null)
      setHasProfile(false)
      setLoading(false)
      setError('')
      return
    }
    setLoading(true)
    try {
      const candidateId = await live.resolveCandidate()
      setProfileId(candidateId)
      const loaded = await live.loadLiveState(candidateId, userId)
      setLiveState(loaded.state)
      setHasProfile(loaded.hasProfile)
      setError('')
    } catch (failure) {
      setError(errorText(failure))
    } finally {
      setLoading(false)
    }
  }, [demo, userId])

  useEffect(() => {
    let active = true
    void (async () => {
      // Defer the first fetch so the effect never sets state synchronously.
      await Promise.resolve()
      if (active) await refresh()
    })()
    return () => {
      active = false
    }
  }, [refresh])

  // Without a session nothing inside the protected workspace is reachable, so
  // the sample state is safe as a placeholder and keeps the demo flows intact.
  const state = demo || !userId ? demoState : (liveState ?? live.emptyState())

  const runLive = useCallback(
    async (action: (candidateId: string) => Promise<unknown>) => {
      if (!profileId) throw new Error('Complete your profile first.')
      try {
        await action(profileId)
        await refresh()
      } catch (failure) {
        throw new Error(errorText(failure), { cause: failure })
      }
    },
    [profileId, refresh],
  )

  const value = useMemo<Workspace>(() => {
    const updateApplications = (updater: (application: Application) => Application) =>
      setDemoState((current) => ({
        ...current,
        applications: current.applications.map(updater),
      }))

    const workspace: Workspace = {
      demo,
      live: !demo,
      loading,
      error,
      profileId,
      hasProfile: demo || !userId ? true : hasProfile,
      state,
      refresh,
      reset: resetDemo,
      saveProfile: async (profile) => {
        if (demo) {
          setDemoState((current) => ({ ...current, profile }))
          return
        }
        try {
          await live.saveProfile(profileId, profile)
          await refresh()
        } catch (failure) {
          throw new Error(errorText(failure), { cause: failure })
        }
      },
      addSkills: async (names) => {
        if (!names.length) return
        if (demo) {
          setDemoState((current) => ({
            ...current,
            profile: {
              ...current.profile,
              skills: [
                ...new Map(
                  [...current.profile.skills, ...names].map((name) => [name.toLowerCase(), name]),
                ).values(),
              ],
            },
          }))
          return
        }
        if (!profileId) throw new Error('Complete your profile first.')
        try {
          for (const name of names) {
            await live.addSkill(profileId, name)
          }
          await refresh()
        } catch (failure) {
          throw new Error(errorText(failure), { cause: failure })
        }
      },
      startWorkflow: async (workMode) => {
        if (demo) {
          const jobIds = demoState.jobs
            .filter((job) => !workMode || job.work_mode === workMode)
            .sort(
              (a, b) =>
                match(b, demoState.profile.skills).score - match(a, demoState.profile.skills).score,
            )
            .slice(0, 5)
            .map((job) => job.id)
          const id = crypto.randomUUID()
          setDemoState((current) => ({
            ...current,
            workflows: [
              ...current.workflows,
              {
                id,
                jobIds,
                approvedIds: [],
                status: jobIds.length ? 'pending_review' : 'no_matches',
              },
            ],
          }))
          return id
        }
        if (!profileId || !userId) throw new Error('Complete your profile first.')
        try {
          const id = await live.startWorkflow(profileId, userId, workMode)
          await refresh()
          return id
        } catch (failure) {
          throw new Error(errorText(failure), { cause: failure })
        }
      },
      reviewWorkflow: async (workflowId, approvedJobIds) => {
        if (demo) {
          setDemoState((current) => ({
            ...current,
            workflows: current.workflows.map((workflow) =>
              workflow.id === workflowId
                ? {
                    ...workflow,
                    approvedIds: approvedJobIds,
                    status: approvedJobIds.length ? 'approved' : 'rejected',
                  }
                : workflow,
            ),
          }))
          return
        }
        await runLive((candidateId) =>
          live.reviewWorkflow(
            candidateId,
            workflowId,
            approvedJobIds.length ? 'approve' : 'reject',
            approvedJobIds,
          ),
        )
      },
      createDraft: async (workflowId, jobId) => {
        if (demo) {
          const workflow = demoState.workflows.find((row) => row.id === workflowId)
          if (!workflow?.approvedIds.includes(jobId)) throw new Error('This role is not approved.')
          const existing = demoState.applications.find((row) => row.jobId === jobId)
          if (existing) return existing.id
          const job = demoState.jobs.find((row) => row.id === jobId)
          if (!job) throw new Error('This role is no longer available.')
          const id = crypto.randomUUID()
          const application: Application = {
            id,
            jobId,
            status: 'draft',
            revision: 1,
            resumeSnapshot: structuredClone(demoState.profile),
            revisions: [],
            history: [
              {
                status: 'draft',
                at: new Date().toISOString(),
                note: 'Draft created from an approved shortlist.',
              },
            ],
            letter: `Hello ${job.company_name} team,\n\nI would like to apply for the ${job.title} role. My experience includes ${
              demoState.profile.skills
                .filter((skill) => job.description.toLowerCase().includes(skill.toLowerCase()))
                .join(', ') || 'the skills listed in my profile'
            }. I would welcome a conversation about the work and the experience your team needs.\n\n${demoState.profile.full_name}`,
          }
          setDemoState((current) => ({
            ...current,
            applications: [...current.applications, application],
          }))
          return id
        }
        if (!profileId) throw new Error('Complete your profile first.')
        try {
          const id = await live.createTrackedApplication(profileId, workflowId, jobId)
          await refresh()
          return id
        } catch (failure) {
          throw new Error(errorText(failure), { cause: failure })
        }
      },
      saveDraft: async (applicationId, letter, expected) => {
        if (demo) {
          const application = demoState.applications.find((row) => row.id === applicationId)
          if (!application) throw new Error('This application is no longer available.')
          const next = editDraft(application, letter, expected)
          updateApplications((row) => (row.id === next.id ? next : row))
          return
        }
        await runLive((candidateId) => live.saveDraft(candidateId, applicationId, letter, expected))
      },
      changeStatus: async (applicationId, status, reviewed, submitted) => {
        if (demo) {
          const application = demoState.applications.find((row) => row.id === applicationId)
          if (!application) throw new Error('This application is no longer available.')
          const next = updateStatus(application, status, reviewed, submitted)
          setDemoState((current) => ({
            ...current,
            applications: current.applications.map((row) => (row.id === next.id ? next : row)),
            followUps: ['offered', 'rejected', 'withdrawn'].includes(next.status)
              ? current.followUps.map((row) =>
                  row.applicationId === next.id && row.state === 'pending'
                    ? { ...row, state: 'dismissed' }
                    : row,
                )
              : current.followUps,
            interviews: ['offered', 'rejected', 'withdrawn'].includes(next.status)
              ? current.interviews.map((row) =>
                  row.applicationId === next.id && row.status === 'scheduled'
                    ? { ...row, status: 'cancelled', version: row.version + 1 }
                    : row,
                )
              : current.interviews,
          }))
          return
        }
        await runLive((candidateId) =>
          live.changeStatus(candidateId, applicationId, status, reviewed, submitted),
        )
      },
      prepareHandoff: async (applicationId, expected) => {
        if (demo) {
          const application = demoState.applications.find((row) => row.id === applicationId)
          if (!application) throw new Error('This application is no longer available.')
          const next = prepareDemoHandoff(application, expected, true, true)
          updateApplications((row) => (row.id === next.id ? next : row))
          return
        }
        await runLive((candidateId) => live.prepareHandoff(candidateId, applicationId, expected))
        setLiveState((current) =>
          current
            ? {
                ...current,
                applications: current.applications.map((row) =>
                  row.id === applicationId ? { ...row, handoffRevision: expected } : row,
                ),
              }
            : current,
        )
      },
      createFollowUp: async (applicationId, dueISO, note) => {
        if (demo) {
          setDemoState((current) => ({
            ...current,
            followUps: [
              ...current.followUps,
              {
                id: crypto.randomUUID(),
                applicationId,
                due: dueISO,
                note,
                state: 'pending',
              },
            ],
          }))
          return
        }
        await runLive((candidateId) =>
          live.createFollowUp(candidateId, applicationId, dueISO, note),
        )
      },
      resolveFollowUp: async (applicationId, followUpId, complete) => {
        if (demo) {
          setDemoState((current) => ({
            ...current,
            followUps: current.followUps.map((row) =>
              row.id === followUpId ? { ...row, state: complete ? 'completed' : 'dismissed' } : row,
            ),
          }))
          return
        }
        await runLive((candidateId) =>
          live.resolveFollowUp(candidateId, applicationId, followUpId, complete),
        )
      },
      saveInterview: async (input) => {
        if (demo) {
          if (
            interviewConflict(
              demoState.interviews,
              new Date(input.start).toISOString(),
              new Date(input.end).toISOString(),
              input.id,
            )
          ) {
            throw new Error('This overlaps another scheduled interview. Choose another time.')
          }
          if (
            input.id &&
            demoState.interviews.find((row) => row.id === input.id)?.version !== input.version
          ) {
            throw new Error('This interview changed. Reload its details before saving.')
          }
          const next: Interview = {
            id: input.id || crypto.randomUUID(),
            applicationId: input.applicationId,
            title: input.title,
            start: new Date(input.start).toISOString(),
            end: new Date(input.end).toISOString(),
            mode: input.mode,
            location: input.location,
            status: 'scheduled',
            version: (input.version || 0) + 1,
            reminders: input.reminders,
          }
          setDemoState((current) => ({
            ...current,
            interviews: input.id
              ? current.interviews.map((row) => (row.id === input.id ? next : row))
              : [...current.interviews, next],
          }))
          return
        }
        const reminders = input.reminders.filter((value) => [0, 60, 1440].includes(value))
        await runLive((candidateId) =>
          input.id
            ? live.updateInterview(candidateId, input.id, {
                expected_version: input.version ?? 1,
                starts_at: new Date(input.start).toISOString(),
                ends_at: new Date(input.end).toISOString(),
                reminder_minutes: reminders,
              })
            : live.createInterview(candidateId, input.applicationId, {
                title: input.title,
                starts_at: new Date(input.start).toISOString(),
                ends_at: new Date(input.end).toISOString(),
                mode: input.mode,
                location_or_link: input.location || null,
                reminder_minutes: reminders,
              }),
        )
      },
      interviewAction: async (interviewId, action, version) => {
        if (demo) {
          const current = demoState.interviews.find((row) => row.id === interviewId)
          if (!current) throw new Error('This interview is no longer available.')
          if (current.version !== version) throw new Error('This interview changed. Reload it.')
          setDemoState((stateNow) => ({
            ...stateNow,
            interviews: stateNow.interviews.map((row) =>
              row.id === interviewId ? { ...row, status: action, version: row.version + 1 } : row,
            ),
          }))
          return
        }
        await runLive((candidateId) =>
          live.interviewAction(
            candidateId,
            interviewId,
            action === 'cancelled' ? 'cancel' : 'complete',
            version,
          ),
        )
      },
      refreshNotifications: async () => {
        if (demo) {
          const now = Date.now()
          const scheduled = demoState.interviews
            .filter((row) => row.status === 'scheduled')
            .flatMap((row) =>
              row.reminders.map((minutes) => ({
                id: `${row.id}:${row.version}:${minutes}`,
                title: row.title,
                at: new Date(new Date(row.start).getTime() - minutes * 60000).toISOString(),
                start: row.start,
              })),
            )
          const due = scheduled.filter(
            (row) =>
              new Date(row.at).getTime() <= now &&
              new Date(row.start).getTime() >= now &&
              !demoState.notifications.some((existing) => existing.id === row.id),
          )
          if (due.length) {
            setDemoState((current) => ({
              ...current,
              notifications: [
                ...current.notifications,
                ...due.map((row) => ({ id: row.id, title: row.title, at: row.at, read: false })),
              ],
            }))
          }
          return due.length
            ? `${due.length} due reminder${due.length === 1 ? '' : 's'} made available.`
            : 'No new reminders are due. Future reminders stay scheduled.'
        }
        if (!profileId) throw new Error('Complete your profile first.')
        try {
          const message = await live.refreshNotifications(profileId)
          await refresh()
          return message
        } catch (failure) {
          throw new Error(errorText(failure), { cause: failure })
        }
      },
      readNotification: async (notificationId) => {
        if (demo) {
          setDemoState((current) => ({
            ...current,
            notifications: current.notifications.map((row) =>
              row.id === notificationId ? { ...row, read: true } : row,
            ),
          }))
          return
        }
        const target = state.notifications.find((row) => row.id === notificationId)
        if (!target?.apiId) throw new Error('This reminder is no longer available.')
        await runLive((candidateId) => live.readNotification(candidateId, target.apiId!))
      },
    }
    return workspace
  }, [
    demo,
    loading,
    error,
    profileId,
    hasProfile,
    state,
    refresh,
    resetDemo,
    runLive,
    setDemoState,
    demoState,
    userId,
  ])

  return <Context.Provider value={value}>{children}</Context.Provider>
}

export function useWorkspace() {
  const workspace = useContext(Context)
  if (!workspace) throw new Error('Workspace provider is missing')
  return workspace
}
