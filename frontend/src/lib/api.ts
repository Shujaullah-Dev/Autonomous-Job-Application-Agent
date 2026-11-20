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

export async function api<T>(
  path: string,
  options: RequestInit = {},
  accessToken?: string,
): Promise<T> {
  const method = (options.method || 'GET').toUpperCase()
  const publicRoute =
    /^\/health$|^\/api\/v1\/jobs(?:\?[^#]*|\/\d+)?$/.test(path) && ['GET'].includes(method)
  const candidateRoute =
    /^\/api\/v1\/candidates(?:\/[0-9a-f-]{36}(?:\/(?:skills(?:\/[0-9a-f-]{36})?|experiences(?:\/[0-9a-f-]{36})?|education(?:\/[0-9a-f-]{36})?|resume\/(?:preview|import)))?)?$/.test(
      path,
    )
  const candidateCreate = path === '/api/v1/candidates' && method === 'POST'
  const candidateRead =
    /^\/api\/v1\/candidates\/[0-9a-f-]{36}$/.test(path) && ['GET', 'PATCH'].includes(method)
  const candidateSubresource =
    candidateRoute && /\/(skills|experiences|education|resume\/preview|resume\/import)/.test(path)
  if (!(publicRoute || candidateCreate || candidateRead || candidateSubresource)) {
    throw new ApiError(
      403,
      'This endpoint requires the backend development key or account ownership support.',
    )
  }
  const headers = new Headers(options.headers)
  const currentToken =
    accessToken ?? (await supabase?.auth.getSession())?.data.session?.access_token
  if (currentToken) headers.set('Authorization', `Bearer ${currentToken}`)
  let response: Response
  try {
    response = await fetch(
      `${(import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')}${path}`,
      {
        ...options,
        headers,
        signal: options.signal ?? AbortSignal.timeout(15000),
        credentials: 'omit',
      },
    )
  } catch (error) {
    if (options.signal?.aborted) throw error
    throw new ApiError(0, 'Cannot reach the API. Check your connection and try again.')
  }
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status))
  return response.json() as Promise<T>
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
