import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, safeUrl, validateResume, errorMessage } from './api'

afterEach(() => vi.unstubAllGlobals())
describe('API boundaries', () => {
  it('rejects paths that leave the API before making a network call', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    await expect(api('https://evil.example/api/v1/jobs')).rejects.toThrow('relative')
    await expect(api('//evil.example/api/v1/jobs')).rejects.toThrow('relative')
    await expect(api('/api/v1/jobs/1/../../candidates')).rejects.toThrow('not allowed')
    await expect(api('/api/v1/\\..\\secrets')).rejects.toThrow('not allowed')
    expect(fetch).not.toHaveBeenCalled()
  })
  it('treats empty and 204 responses as no content', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
    await expect(
      api('/api/v1/candidates/a/skills/b', { method: 'DELETE' }),
    ).resolves.toBeUndefined()
  })
  it.each([401, 403, 404, 409, 422, 429, 503])(
    'redacts server error bodies for %s',
    async (status) => {
      vi.stubGlobal(
        'fetch',
        vi.fn().mockResolvedValue(new Response('private database traceback', { status })),
      )
      await expect(api('/api/v1/jobs')).rejects.toThrow(errorMessage(status))
    },
  )
  it('sends bearer authentication and keeps cookies out', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{}'))
    vi.stubGlobal('fetch', fetch)
    await api('/api/v1/jobs', {}, 'sample-token')
    expect(fetch.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer sample-token')
    expect(fetch.mock.calls[0][1].credentials).toBe('omit')
    expect(fetch.mock.calls[0][1].headers.get('X-Dev-Job-Key')).toBeNull()
  })
  it('reports network failures safely', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('secret internal detail')))
    await expect(api('/health')).rejects.toThrow('Cannot reach')
  })
})
describe('external destinations and resume input', () => {
  it.each([
    'javascript:alert(1)',
    '//evil.example',
    'http://example.com',
    'https://user:pass@example.com',
    'data:text/html,test',
  ])('rejects unsafe URL %s', (value) => expect(safeUrl(value)).toBeUndefined())
  it('accepts HTTPS listing URLs', () =>
    expect(safeUrl('https://example.com/job')).toBe('https://example.com/job'))
  it('rejects empty, oversized, wrong-type, and mismatched files', () => {
    expect(validateResume(new File([], 'resume.pdf'))).toContain('empty')
    expect(validateResume(new File(['x'], 'resume.exe'))).toContain('PDF')
    expect(validateResume(new File(['x'], 'resume.pdf', { type: 'text/plain' }))).toContain('match')
    expect(validateResume(new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'resume.pdf'))).toContain(
      '5 MB',
    )
    expect(
      validateResume(new File(['%PDF'], 'resume.pdf', { type: 'application/pdf' })),
    ).toBeUndefined()
  })
})
