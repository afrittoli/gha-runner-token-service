import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  apiClient, 
  User, 
  SecurityEvent 
} from '@api/client'

// --- User Management ---

export interface UserListResponse {
  users: User[]
  total: number
}

export interface UserCreate {
  email?: string
  oidc_sub?: string
  display_name?: string
  is_admin?: boolean
  can_use_jit?: boolean
}

export interface UserUpdate {
  display_name?: string
  is_admin?: boolean
  can_use_jit?: boolean
  is_active?: boolean
}

export function useUsers(includeInactive = false) {
  return useQuery<UserListResponse>({
    queryKey: ['admin', 'users', { includeInactive }],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/admin/users', { 
        params: { include_inactive: includeInactive } 
      })
      return response.data
    },
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation<User, Error, UserCreate>({
    mutationFn: async (data: UserCreate) => {
      const response = await apiClient.post('/api/v1/admin/users', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}

export function useUpdateUser() {
  const queryClient = useQueryClient()
  return useMutation<User, Error, { userId: string; data: UserUpdate }>({
    mutationFn: async ({ userId, data }) => {
      const response = await apiClient.put(`/api/v1/admin/users/${userId}`, data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      // Virtual admin team members are derived from is_admin flag
      queryClient.invalidateQueries({ queryKey: ['admin', 'teams'] })
    },
  })
}

export interface DeactivateUserRequest {
  userId: string
  comment: string
}

export function useDeleteUser() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, DeactivateUserRequest>({
    mutationFn: async ({ userId, comment }: DeactivateUserRequest) => {
      await apiClient.request({
        method: 'DELETE',
        url: `/api/v1/admin/users/${userId}`,
        data: { comment }
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}

export function useActivateUser() {
  const queryClient = useQueryClient()
  return useMutation<User, Error, string>({
    mutationFn: async (userId: string) => {
      const response = await apiClient.post(`/api/v1/admin/users/${userId}/activate`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}

export interface BatchDisableUsersRequest {
  comment: string
  user_ids?: string[]
  exclude_admins?: boolean
}

export interface BatchRestoreUsersRequest {
  comment: string
  user_ids?: string[]
}

export interface BatchActionResponse {
  success: boolean
  action: string
  affected_count: number
  failed_count: number
  comment: string
  details?: Array<{
    user_id: string
    email: string
    status: string
    error?: string
  }>
}

export function useBatchDisableUsers() {
  const queryClient = useQueryClient()
  return useMutation<BatchActionResponse, Error, BatchDisableUsersRequest>({
    mutationFn: async (data: BatchDisableUsersRequest) => {
      const response = await apiClient.post('/api/v1/admin/batch/disable-users', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}

export function useBatchRestoreUsers() {
  const queryClient = useQueryClient()
  return useMutation<BatchActionResponse, Error, BatchRestoreUsersRequest>({
    mutationFn: async (data: BatchRestoreUsersRequest) => {
      const response = await apiClient.post('/api/v1/admin/batch/restore-users', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}

// --- Security Events ---

export interface SecurityEventListResponse {
  events: SecurityEvent[]
  total: number
}

export interface SecurityEventFilters {
  event_type?: string
  severity?: string
  user_identity?: string
  limit?: number
  offset?: number
}

export function useSecurityEvents(filters: SecurityEventFilters = {}) {
  return useQuery<SecurityEventListResponse>({
    queryKey: ['admin', 'security-events', filters],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/admin/security-events', { params: filters })
      return response.data
    },
  })
}

// --- Audit Logs ---

export interface AuditLog {
  id: number
  event_type: string
  runner_id: string | null
  runner_name: string | null
  user_identity: string
  oidc_sub: string | null
  request_ip: string | null
  user_agent: string | null
  event_data: Record<string, unknown> | null
  success: boolean
  error_message: string | null
  timestamp: string
}

export interface AuditLogListResponse {
  logs: AuditLog[]
  total: number
}

export interface AuditLogFilters {
  event_type?: string
  user_identity?: string
  limit?: number
  offset?: number
}

export type BulkDeprovisionRequest =
  | { comment: string; runner_ids: string[]; user_identity?: string }
  | { comment: string; user_identity: string; runner_ids?: string[] }

export function useAuditLogs(filters: AuditLogFilters = {}) {
  return useQuery<AuditLogListResponse>({
    queryKey: ['audit-logs', filters],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/audit-logs', { params: filters })
      return response.data
    },
  })
}

// --- Sync Service ---

export function useSyncStatus() {
  return useQuery({
    queryKey: ['admin', 'sync-status'],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/admin/sync/status')
      return response.data
    },
  })
}

export function useTriggerSync() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post('/api/v1/admin/sync/trigger')
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runners'] })
    },
  })
}

export function useBulkDeprovision() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: BulkDeprovisionRequest) => {
      const response = await apiClient.post('/api/v1/admin/batch/delete-runners', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['runners'] })
      queryClient.invalidateQueries({ queryKey: ['audit-logs'] })
    },
  })
}

export function useAdminStats() {
  return useQuery({
    queryKey: ['admin', 'stats'],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/admin/stats')
      return response.data
    },
  })
}

