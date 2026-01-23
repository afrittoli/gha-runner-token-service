import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

// Create axios instance with base configuration
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Token storage (in-memory for security)
let accessToken: string | null = null

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response) {
      const status = error.response.status

      // Handle specific error codes
      switch (status) {
        case 401:
          // Token expired or invalid - trigger re-authentication
          console.error('Authentication required')
          // The OIDC context will handle redirect
          break
        case 403:
          console.error('Access forbidden')
          break
        case 404:
          console.error('Resource not found')
          break
        case 500:
          console.error('Server error')
          break
      }
    } else if (error.request) {
      console.error('Network error - no response received')
    } else {
      console.error('Request error:', error.message)
    }

    return Promise.reject(error)
  }
)

// API types
export interface Runner {
  runner_id: string
  runner_name: string
  status: 'pending' | 'active' | 'offline' | 'deleted'
  github_runner_id: number | null
  runner_group_id: number
  labels: string[]
  ephemeral: boolean
  provisioned_by: string
  created_at: string
  updated_at: string
  registered_at: string | null
  deleted_at: string | null
  audit_trail?: SecurityEvent[]
}

export interface RunnerListResponse {
  runners: Runner[]
  total: number
}

export interface DashboardStats {
  total_runners: number
  active_runners: number
  offline_runners: number
  pending_runners: number
  recent_events: SecurityEvent[]
}

export interface SecurityEvent {
  id: string
  event_type: string
  severity: 'low' | 'medium' | 'high'
  user_identity: string
  runner_id: string | null
  runner_name: string | null
  action_taken: string | null
  timestamp: string
}

export interface User {
  id: string
  email: string | null
  oidc_sub: string | null
  display_name: string | null
  is_admin: boolean
  is_active: boolean
  can_use_registration_token: boolean
  can_use_jit: boolean
  created_at: string
  last_login_at: string | null
}

export interface AuthInfo {
  user_id: string | null
  identity: string
  email: string | null
  oidc_sub: string | null
  is_admin: boolean
  roles: string[]
}
