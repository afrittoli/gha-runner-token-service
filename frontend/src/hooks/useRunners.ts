import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  apiClient,
  Runner,
  RunnerListResponse,
  JitProvisionResponse
} from '@api/client'
import { getRuntimeConfig } from '@/config/runtime'

export interface RunnerFilters {
  status?: string
  ephemeral?: boolean
  limit?: number
  offset?: number
  /** Filter by team name. Individual users see all their team runners by
   *  default; this narrows to one specific team. */
  team?: string
}

const REFETCH_INTERVAL = getRuntimeConfig().refetchInterval

export function useRunners(filters: RunnerFilters = {}) {
  return useQuery<RunnerListResponse>({
    queryKey: ['runners', filters],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/runners', { params: filters })
      return response.data
    },
    refetchInterval: REFETCH_INTERVAL,
    refetchIntervalInBackground: false, // Only when tab is active
  })
}

export function useRunner(runnerId: string | undefined) {
  return useQuery<Runner>({
    queryKey: ['runner', runnerId],
    queryFn: async () => {
      const response = await apiClient.get(`/api/v1/runners/${runnerId}`)
      return response.data
    },
    enabled: !!runnerId,
    refetchInterval: REFETCH_INTERVAL,
    refetchIntervalInBackground: false, // Only when tab is active
  })
}

export interface ProvisionRunnerJitRequest {
  runner_name_prefix?: string
  labels?: string[]
  team_id?: string
}

export function useProvisionRunnerJit() {
  const queryClient = useQueryClient()
  
  return useMutation<JitProvisionResponse, Error, ProvisionRunnerJitRequest>({
    mutationFn: async (data: ProvisionRunnerJitRequest) => {
      const response = await apiClient.post('/api/v1/runners/jit', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runners'] })
    },
  })
}

export function useDeprovisionRunner() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (runnerId: string) => {
      const response = await apiClient.delete(`/api/v1/runners/${runnerId}`)
      return response.data
    },
    onSuccess: (_, runnerId) => {
      queryClient.invalidateQueries({ queryKey: ['runners'] })
      queryClient.invalidateQueries({ queryKey: ['runner', runnerId] })
    },
  })
}

export function useRefreshRunnerStatus() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async (runnerId: string) => {
      const response = await apiClient.post(`/api/v1/runners/${runnerId}/refresh`)
      return response.data
    },
    onSuccess: (_, runnerId) => {
      queryClient.invalidateQueries({ queryKey: ['runner', runnerId] })
    },
  })
}

