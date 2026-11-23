import type { components } from './api-types'
import { supabase } from '../features/auth/AuthProvider'

export type ApiSchema = components['schemas']
export type Job = ApiSchema['JobRead']
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}
export const errorMessage = (status: number) =>
  ({
    401: 'Your session expired. Sign in again.',
    403: 'You do not have access to this record.',
    404: 'This record is no longer available.',
    409: 'This record changed. Reload it before trying again.',
    422: 'Some fields need attention. Check your entries.',
    429: 'Too many requests. Wait a moment and try again.',
    503: 'The service is unavailable. Try again later.',
  })[status] ?? 'The request failed. Try again later.'

const baseUrl = () =>
  (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

/**
 * Accept only relative paths this app owns. Absolute URLs, protocol-relative
 * URLs and traversal segments would send the auth token somewhere else.
 */
export function assertApiPath(path: string): string {
  if (!path.startsWith('/') || path.startsWith('//')) {
    throw new ApiError(403, 'Only relative API paths are allowed.')
  }
  const unsafeCharacter = [...path].some((character) => {
    const code = character.codePointAt(0) ?? 0
    return code < 0x20 || code === 0x7f
  })
  if (unsafeCharacter || path.includes('\\') || path.split(/[?#]/)[0].split('/').includes('..')) {
    throw new ApiError(403, 'This API path is not allowed.')
  }
  if (!/^\/(?:health(?:\/db)?|api\/v1\/[A-Za-z0-9._~\-/]+)(?:\?[^#]*)?$/.test(path)) {
    throw new ApiError(403, 'This API path is not allowed.')
  }
  return path
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string,
): Promise<T> {
  assertApiPath(path)
  const headers = new Headers(options.headers)
  const currentToken =
    accessToken ?? (await supabase?.auth.getSession())?.data.session?.access_token
  if (currentToken) headers.set('Authorization', `Bearer ${currentToken}`)
  let response: Response
  try {
    response = await fetch(`${baseUrl()}${path}`, {
      ...options,
      headers,
      signal: options.signal ?? AbortSignal.timeout(15000),
      credentials: 'omit',
    })
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new ApiError(0, 'Cannot reach the API. Check your connection and try again.')
  }
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status))
  if (response.status === 204) return undefined as T
  const body = await response.text()
  return (body ? JSON.parse(body) : undefined) as T
}
export function safeUrl(value: string | null | undefined): string | undefined {
  if (!value) return undefined
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && !url.username && !url.password ? url.href : undefined
  } catch {
    return undefined
  }
}

export function validateResume(file: File): string | undefined {
  const extension = file.name.split('.').pop()?.toLowerCase()
  if (!['pdf', 'docx'].includes(extension || '')) return 'Choose a PDF or DOCX file.'
  if (file.size === 0) return 'This file is empty. Choose another file.'
  if (file.size > 5 * 1024 * 1024) return 'Choose a file smaller than 5 MB.'
  const allowed =
    extension === 'pdf'
      ? 'application/pdf'
      : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  if (file.type && file.type !== allowed) return 'The file type does not match its extension.'
}
