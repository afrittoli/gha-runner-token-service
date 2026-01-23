import { create } from 'zustand'
import { AxiosError } from 'axios'
import { AuthInfo, apiClient, setAccessToken } from '../api/client'

interface AuthState {
  user: AuthInfo | null
  isLoading: boolean
  error: string | null
  fetchUser: () => Promise<void>
  setUser: (user: AuthInfo | null) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  error: null,

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
    set({ user: null, error: null })
  },
}))
