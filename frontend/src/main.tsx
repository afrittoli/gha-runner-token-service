import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from 'react-oidc-context'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

// Configure React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // 30 seconds
      gcTime: 1000 * 60 * 5, // 5 minutes (garbage collection)
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

// OIDC configuration
// In production, these values should come from environment variables
const oidcConfig = {
  authority: import.meta.env.VITE_OIDC_AUTHORITY || 'https://your-auth0-domain.auth0.com',
  client_id: import.meta.env.VITE_OIDC_CLIENT_ID || 'your-client-id',
  redirect_uri: import.meta.env.VITE_OIDC_REDIRECT_URI || `${window.location.origin}/app/callback`,
  post_logout_redirect_uri: import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT_URI || `${window.location.origin}/app`,
  scope: 'openid profile email',
  // Request audience to get a JWT access token (required for API validation)
  // Without this, Auth0 returns an opaque token that the backend can't validate
  extraQueryParams: {
    audience: import.meta.env.VITE_OIDC_AUDIENCE || 'runner-token-service',
  },
  // Handle token refresh
  automaticSilentRenew: true,
  // Store tokens in memory (more secure than localStorage)
  userStore: undefined,
  // Force login prompt to allow switching users (don't reuse existing Auth0 session)
  prompt: 'login',
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider {...oidcConfig}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter basename="/app">
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </AuthProvider>
  </React.StrictMode>,
)
