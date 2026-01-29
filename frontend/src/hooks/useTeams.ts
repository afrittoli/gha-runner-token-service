import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@api/client'

// --- Team Types ---

export interface Team {
  id: string
  name: string
  description: string | null
  required_labels: string[]
  optional_label_patterns: string[]
  max_runners: number | null
  is_active: boolean
  created_at: string
  updated_at: string
  member_count?: number
  runner_count?: number
}

export interface TeamListResponse {
  teams: Team[]
  total: number
}

export interface TeamCreate {
  name: string
  description?: string
  required_labels: string[]
  optional_label_patterns?: string[]
  max_runners?: number
}

export interface TeamUpdate {
  description?: string
  required_labels?: string[]
  optional_label_patterns?: string[]
  max_runners?: number | null
  is_active?: boolean
}

export interface TeamMember {
  user_id: string
  email: string
  display_name: string | null
  joined_at: string
}

export interface TeamMemberListResponse {
  members: TeamMember[]
  total: number
}

export interface AddTeamMemberRequest {
  user_id: string
}

// --- Team Hooks ---

export function useTeams(includeInactive = false) {
  return useQuery<TeamListResponse>({
    queryKey: ['admin', 'teams', { includeInactive }],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/admin/teams', {
        params: { include_inactive: includeInactive }
      })
      return response.data
    },
  })
}

export function useTeam(teamId: string | undefined) {
  return useQuery<Team>({
    queryKey: ['admin', 'teams', teamId],
    queryFn: async () => {
      const response = await apiClient.get(`/api/v1/admin/teams/${teamId}`)
      return response.data
    },
    enabled: !!teamId,
  })
}

export function useCreateTeam() {
  const queryClient = useQueryClient()
  return useMutation<Team, Error, TeamCreate>({
    mutationFn: async (data: TeamCreate) => {
      const response = await apiClient.post('/api/v1/admin/teams', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'teams'] })
    },
  })
}

export function useUpdateTeam(teamId: string) {
  const queryClient = useQueryClient()
  return useMutation<Team, Error, TeamUpdate>({
    mutationFn: async (data: TeamUpdate) => {
      const response = await apiClient.patch(`/api/v1/admin/teams/${teamId}`, data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'teams'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'teams', teamId] })
    },
  })
}

export interface DeactivateTeamRequest {
  teamId: string
  reason: string
}

export function useDeactivateTeam() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, DeactivateTeamRequest>({
    mutationFn: async ({ teamId, reason }: DeactivateTeamRequest) => {
      await apiClient.post(`/api/v1/admin/teams/${teamId}/deactivate`, { reason })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'teams'] })
    },
  })
}

// --- Team Member Hooks ---

export function useTeamMembers(teamId: string | undefined) {
  return useQuery<TeamMemberListResponse>({
    queryKey: ['admin', 'teams', teamId, 'members'],
    queryFn: async () => {
      const response = await apiClient.get(`/api/v1/admin/teams/${teamId}/members`)
      return response.data
    },
    enabled: !!teamId,
  })
}

export function useAddTeamMember(teamId: string) {
  const queryClient = useQueryClient()
  return useMutation<void, Error, AddTeamMemberRequest>({
    mutationFn: async (data: AddTeamMemberRequest) => {
      await apiClient.post(`/api/v1/admin/teams/${teamId}/members`, data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'teams', teamId, 'members'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'teams', teamId] })
    },
  })
}

export function useRemoveTeamMember(teamId: string) {
  const queryClient = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: async (userId: string) => {
      await apiClient.delete(`/api/v1/admin/teams/${teamId}/members/${userId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'teams', teamId, 'members'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'teams', teamId] })
    },
  })
}


// Made with Bob
