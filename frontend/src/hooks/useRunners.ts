import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  apiClient,
  Runner,
  RunnerListResponse,
  ProvisionRunnerResponse,
  JitProvisionResponse
} from '@api/client'

export interface UserLabelPolicy {
  user_identity: string
  allowed_labels: string[]
  label_patterns: string[] | null
  max_runners: number
  description: string | null
}

export interface RunnerFilters {
  status?: string
  ephemeral?: boolean
  limit?: number
  offset?: number
}

export function useRunners(filters: RunnerFilters = {}) {
  return useQuery<RunnerListResponse>({
    queryKey: ['runners', filters],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/runners', { params: filters })
      return response.data
    },
    // Aggressive polling for demo: refetch every 5 seconds
    refetchInterval: 5000,
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
    // Aggressive polling for demo: refetch every 5 seconds
    refetchInterval: 5000,
    refetchIntervalInBackground: false, // Only when tab is active
  })
}

export interface ProvisionRunnerRequest {
  runner_name_prefix?: string
  labels?: string[]
  ephemeral?: boolean
}

export interface ProvisionRunnerJitRequest {
  runner_name_prefix?: string
  labels?: string[]
}

export function useProvisionRunner() {
  const queryClient = useQueryClient()
  
  return useMutation<ProvisionRunnerResponse, Error, ProvisionRunnerRequest>({
    mutationFn: async (data: ProvisionRunnerRequest) => {
      const response = await apiClient.post('/api/v1/runners/provision', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runners'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
    },
  })
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
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
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
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] })
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

export function useMyLabelPolicy() {
  return useQuery<UserLabelPolicy | null>({
    queryKey: ['my-label-policy'],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/auth/my-label-policy')
      return response.data
    },
  })
}
