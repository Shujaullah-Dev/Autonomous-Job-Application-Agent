import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useWorkspace } from '../app/workspace'
import { loadMatches, type MatchItem } from './live'

/**
 * Resume-based job ranking for the signed-in account.
 *
 * Ranking needs the structured profile the backend reads (skills and work
 * history), so it stays disabled until a profile with skills exists and the
 * demo store is not in use.
 */
export function useMatches() {
  const { live, profileId, state } = useWorkspace()
  const enabled = live && Boolean(profileId) && state.profile.skills.length > 0
  // Re-rank when an import or edit changes the skills the backend scores.
  const skillsKey = state.profile.skills
    .map((name) => name.toLowerCase())
    .sort()
    .join('|')
  const query = useQuery({
    queryKey: ['job-matches', profileId, skillsKey],
    enabled,
    staleTime: 60_000,
    queryFn: ({ signal }) => loadMatches(profileId as string, signal),
  })
  const byId = useMemo(
    () => new Map<number, MatchItem>((query.data?.items ?? []).map((item) => [item.job_id, item])),
    [query.data],
  )
  return {
    enabled,
    byId,
    data: query.data,
    pending: query.isPending,
    error: (query.error as Error | null) ?? null,
    refetch: query.refetch,
  }
}
