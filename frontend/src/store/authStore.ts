import { create } from 'zustand'
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
    } catch (err: any) {
      console.error('Failed to fetch user info:', err)
      set({ 
        user: null, 
        isLoading: false, 
        error: err.response?.data?.detail || 'Failed to fetch user information' 
      })
      // If unauthorized, clear the access token
      if (err.response?.status === 401) {
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
