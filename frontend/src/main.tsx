import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from 'react-oidc-context'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
import { setQueryClient } from './store/authStore'
import { getRuntimeConfig, validateConfig } from './config/runtime'

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

// Make queryClient available to authStore for immediate cache invalidation
setQueryClient(queryClient)

// Get runtime configuration (from window.APP_CONFIG or .env.local)
const config = getRuntimeConfig()

// Validate configuration before starting the app
try {
  validateConfig(config)
} catch (error) {
  console.error('Configuration error:', error)
  // Show error to user
  document.body.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 20px;">
      <div style="max-width: 600px; text-align: center;">
        <h1 style="color: #dc2626; margin-bottom: 16px;">Configuration Error</h1>
        <p style="color: #374151; margin-bottom: 16px;">${error instanceof Error ? error.message : 'Unknown error'}</p>
        <p style="color: #6b7280; font-size: 14px;">Please contact your system administrator.</p>
      </div>
    </div>
  `
  throw error
}

// OIDC configuration using runtime config
const oidcConfig = {
  authority: config.oidc.authority,
  client_id: config.oidc.clientId,
  redirect_uri: config.oidc.redirectUri,
  post_logout_redirect_uri: config.oidc.postLogoutRedirectUri,
  scope: 'openid profile email',
  // Request audience to get a JWT access token (required for API validation)
  // Without this, Auth0 returns an opaque token that the backend can't validate
  extraQueryParams: {
    audience: config.oidc.audience,
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
