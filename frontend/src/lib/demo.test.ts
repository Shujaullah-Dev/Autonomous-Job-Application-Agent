import { describe, expect, it } from 'vitest'
import { seed, updateStatus, editDraft, prepareHandoff, interviewConflict } from './demo'
import { calendar, localInput } from './calendar'

describe('review and submission boundaries', () => {
  it('requires review before ready and independent external submission confirmation', () => {
    const draft = seed().applications[0]
    expect(() => updateStatus(draft, 'ready')).toThrow('Review')
    const ready = updateStatus(draft, 'ready', true)
    expect(() => updateStatus(ready, 'submitted')).toThrow('Confirm')
    expect(updateStatus(ready, 'submitted', false, true).history.at(-1)?.note).toContain(
      'reported by you',
    )
    expect(() => updateStatus(draft, 'offered')).toThrow('not allowed')
  })
  it('does not equate a prepared handoff with submission; requires both confirmations', () => {
    const ready = updateStatus(seed().applications[0], 'ready', true)
    expect(() => prepareHandoff(ready, 1, true, false)).toThrow()
    expect(() => prepareHandoff(ready, 2, true, true)).toThrow('changed')
    const prepared = prepareHandoff(ready, 1, true, true)
    expect(prepared.status).toBe('ready')
    expect(prepareHandoff(prepared, 1, true, true)).toEqual(prepared)
  })
  it('keeps revisions and invalidates old handoffs after edits', () => {
    const app = prepareHandoff(updateStatus(seed().applications[0], 'ready', true), 1, true, true)
    expect(() => editDraft(app, app.letter, 2)).toThrow('changed')
    const edited = editDraft(app, `${app.letter}\nUpdated.`, 1)
    expect(edited.revision).toBe(2)
    expect(edited.revisions[0].letter).toBe(app.letter)
    expect(edited.handoffRevision).toBeUndefined()
    expect(() => editDraft({ ...app, status: 'submitted' }, app.letter, 1)).toThrow('no longer')
  })
  it.each(['offered', 'rejected', 'withdrawn'] as const)('keeps %s terminal', (status) => {
    expect(() => updateStatus({ ...seed().applications[0], status }, 'withdrawn')).toThrow()
  })
  it('keeps the seeded draft snapshot independent of profile edits', () => {
    const state = seed()
    state.profile.skills.push('A new skill')
    expect(state.applications[0].resumeSnapshot.skills).not.toContain('A new skill')
  })
})
describe('interview scheduling and export', () => {
  const interview = {
    id: 'test',
    applicationId: 'example-draft',
    title: 'Review, demo;\nMeeting',
    start: '2026-11-20T09:00:00Z',
    end: '2026-11-20T10:00:00Z',
    mode: 'video' as const,
    location: 'Room 1',
    status: 'scheduled' as const,
    version: 1,
    reminders: [60],
  }
  it('detects overlap but permits adjacent interviews', () => {
    expect(interviewConflict([interview], '2026-11-20T09:30:00Z', '2026-11-20T10:30:00Z')).toBe(
      true,
    )
    expect(interviewConflict([interview], '2026-11-20T10:00:00Z', '2026-11-20T11:00:00Z')).toBe(
      false,
    )
    expect(interviewConflict([interview], interview.start, interview.end, interview.id)).toBe(false)
  })
  it('exports UTC, escapes text, and folds long Unicode lines at 75 octets', () => {
    const result = calendar(interview)
    expect(result).toContain('DTSTART:20261120T090000Z')
    expect(result).toContain('SUMMARY:Review\\, demo\\;\\nMeeting')
    const long = calendar({ ...interview, title: '会議'.repeat(70) })
    for (const line of long.split('\r\n'))
      expect(new TextEncoder().encode(line).length).toBeLessThanOrEqual(75)
    expect(new Date(localInput(interview.start)).getTime()).toBe(
      new Date(interview.start).getTime(),
    )
  })
})
