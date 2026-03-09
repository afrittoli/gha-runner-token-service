import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@api/client'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface OAuthClient {
  id: string
  client_id: string
  team_id: string
  description: string | null
  is_active: boolean
  created_at: string
  created_by: string | null
  last_used_at: string | null
}

export interface OAuthClientListResponse {
  clients: OAuthClient[]
  total: number
}

export interface OAuthClientCreate {
  client_id: string
  team_id: string
  description?: string
}

export interface OAuthClientUpdate {
  description?: string
  is_active?: boolean
}

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

const keys = {
  all: ['admin', 'oauth-clients'] as const,
  forTeam: (teamId: string) =>
    [...keys.all, { teamId }] as const,
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * Fetch the registered M2M client for a specific team.
 * Returns the single active client (or inactive, when active_only=false).
 * The backend enforces one active client per team, so we always get 0 or 1.
 */
export function useTeamOAuthClient(teamId: string | undefined) {
  return useQuery<OAuthClient | null>({
    queryKey: keys.forTeam(teamId ?? ''),
    queryFn: async () => {
      // Fetch all clients for this team (including inactive) so we can show
      // the full picture — registered-but-disabled is a meaningful state.
      const response = await apiClient.get<OAuthClientListResponse>(
        '/api/v1/admin/oauth-clients',
        { params: { team_id: teamId, active_only: false } }
      )
      const clients = response.data.clients
      // Return the most recently created one (should be at most one per team).
      if (clients.length === 0) return null
      return clients.sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      )[0]
    },
    enabled: !!teamId,
  })
}

/**
 * Register a new M2M client for a team.
 * The backend rejects the request if the team already has an active client.
 */
export function useRegisterOAuthClient() {
  const queryClient = useQueryClient()
  return useMutation<OAuthClient, Error, OAuthClientCreate>({
    mutationFn: async (data) => {
      const response = await apiClient.post<OAuthClient>(
        '/api/v1/admin/oauth-clients',
        data
      )
      return response.data
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: keys.forTeam(variables.team_id) })
    },
  })
}

/**
 * Update a registered M2M client (description or is_active flag).
 */
export function useUpdateOAuthClient(teamId: string) {
  const queryClient = useQueryClient()
  return useMutation<OAuthClient, Error, { clientRecordId: string; data: OAuthClientUpdate }>({
    mutationFn: async ({ clientRecordId, data }) => {
      const response = await apiClient.patch<OAuthClient>(
        `/api/v1/admin/oauth-clients/${clientRecordId}`,
        data
      )
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.forTeam(teamId) })
    },
  })
}

/**
 * Permanently delete a registered M2M client.
 * After deletion the team's machine member is unregistered and M2M
 * provisioning will be blocked until a new client is registered.
 */
export function useDeleteOAuthClient(teamId: string) {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: async (clientRecordId) => {
      await apiClient.delete(`/api/v1/admin/oauth-clients/${clientRecordId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.forTeam(teamId) })
    },
  })
}
