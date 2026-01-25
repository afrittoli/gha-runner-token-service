import { create } from 'zustand'
import { AxiosError } from 'axios'
import { AuthInfo, apiClient, setAccessToken, User, impersonateUser, stopImpersonation } from '../api/client'

interface ImpersonationState {
  isImpersonating: boolean
  impersonatedUser: User | null
  originalAdmin: string | null
  impersonationToken: string | null
  originalOidcToken: string | null  // Store original OIDC token
}

interface AuthState {
  user: AuthInfo | null
  isLoading: boolean
  error: string | null
  impersonation: ImpersonationState
  fetchUser: () => Promise<void>
  setUser: (user: AuthInfo | null) => void
  clearAuth: () => void
  startImpersonation: (userId: string, oidcToken: string) => Promise<void>
  stopImpersonation: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isLoading: false,
  error: null,
  impersonation: {
    isImpersonating: false,
    impersonatedUser: null,
    originalAdmin: null,
    impersonationToken: null,
    originalOidcToken: null,
  },

  fetchUser: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await apiClient.get<AuthInfo>('/api/v1/auth/me')
      set({ user: response.data, isLoading: false })
    } catch (err: unknown) {
      const axiosError = err as AxiosError<{ detail?: string }>
      console.error('Failed to fetch user info:', axiosError)
      set({
        user: null,
        isLoading: false,
        error: axiosError.response?.data?.detail || 'Failed to fetch user information'
      })
      // If unauthorized, clear the access token
      if (axiosError.response?.status === 401) {
        setAccessToken(null)
      }
    }
  },

  setUser: (user) => set({ user }),

  clearAuth: () => {
    setAccessToken(null)
    set({
      user: null,
      error: null,
      impersonation: {
        isImpersonating: false,
        impersonatedUser: null,
        originalAdmin: null,
        impersonationToken: null,
        originalOidcToken: null,
      }
    })
  },

  startImpersonation: async (userId: string, oidcToken: string) => {
    set({ isLoading: true, error: null })
    try {
      // IMPORTANT: Set admin token BEFORE calling the API
      // The impersonate endpoint requires admin privileges
      setAccessToken(oidcToken)
      
      // Now call the endpoint with admin token
      const response = await impersonateUser(userId)
      
      // Switch to impersonation token
      setAccessToken(response.impersonation_token)
      
      set({
        isLoading: false,
        impersonation: {
          isImpersonating: true,
          impersonatedUser: response.user,
          originalAdmin: response.original_admin,
          impersonationToken: response.impersonation_token,
          originalOidcToken: oidcToken,  // Store original token
        }
      })
      
      // Fetch the impersonated user's info
      await get().fetchUser()
    } catch (err: unknown) {
      const axiosError = err as AxiosError<{ detail?: string }>
      console.error('Failed to start impersonation:', axiosError)
      set({
        isLoading: false,
        error: axiosError.response?.data?.detail || 'Failed to start impersonation'
      })
    }
  },

  stopImpersonation: async () => {
    set({ isLoading: true, error: null })
    try {
      const originalToken = get().impersonation.originalOidcToken
      
      // IMPORTANT: Restore original OIDC token BEFORE calling the API
      // The stop-impersonation endpoint requires admin privileges
      if (originalToken) {
        setAccessToken(originalToken)
      }
      
      // Now call the endpoint with admin token
      await stopImpersonation()
      
      // Clear impersonation state
      set({
        isLoading: false,
        impersonation: {
          isImpersonating: false,
          impersonatedUser: null,
          originalAdmin: null,
          impersonationToken: null,
          originalOidcToken: null,
        }
      })
      
      // Fetch user info with original token
      await get().fetchUser()
    } catch (err: unknown) {
      const axiosError = err as AxiosError<{ detail?: string }>
      console.error('Failed to stop impersonation:', axiosError)
      set({
        isLoading: false,
        error: axiosError.response?.data?.detail || 'Failed to stop impersonation'
      })
    }
  },
}))
