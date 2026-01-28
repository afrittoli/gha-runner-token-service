import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from 'react-oidc-context'
import { useEffect } from 'react'
import MainLayout from '@components/MainLayout'
import Dashboard from '@pages/Dashboard'
import RunnersList from '@pages/RunnersList'
import RunnerDetail from '@pages/RunnerDetail'
import ProvisionRunner from '@pages/ProvisionRunner'
import Teams from '@pages/admin/Teams'
import LabelPolicies from '@pages/admin/LabelPolicies'
import UserManagement from '@pages/admin/UserManagement'
import SecurityEvents from '@pages/admin/SecurityEvents'
import AuditLog from '@pages/admin/AuditLog'
import AdminConsole from '@pages/admin/AdminConsole'
import LoginCallback from '@pages/LoginCallback'
import Login from '@pages/Login'
import { setAccessToken } from '@api/client'
import { useAuthStore } from '@store/authStore'

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const auth = useAuth()
  const { user, isLoading: isStoreLoading, fetchUser, error: storeError } = useAuthStore()

  useEffect(() => {
    if (auth.isAuthenticated && !user && !isStoreLoading && !storeError) {
      fetchUser()
    }
  }, [auth.isAuthenticated, user, isStoreLoading, fetchUser, storeError])

  if (auth.isLoading || (auth.isAuthenticated && isStoreLoading)) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gh-blue mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (auth.error || storeError) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center text-red-600 px-4">
          <p className="font-semibold">Authentication error</p>
          <p className="mt-2 text-sm text-gray-600">{auth.error?.message || storeError}</p>
          <button
            onClick={() => {
              if (auth.error) {
                auth.signinRedirect()
              } else {
                fetchUser()
              }
            }}
            className="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gh-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            {auth.error ? 'Try again' : 'Retry'}
          </button>
        </div>
      </div>
    )
  }

  if (!auth.isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function App() {
  const auth = useAuth()
  const { clearAuth } = useAuthStore()

  useEffect(() => {
    if (auth.isAuthenticated && auth.user?.access_token) {
      setAccessToken(auth.user.access_token)
    } else {
      setAccessToken(null)
      if (!auth.isLoading) {
        clearAuth()
      }
    }
  }, [auth.isAuthenticated, auth.user?.access_token, auth.isLoading, clearAuth])

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/callback" element={<LoginCallback />} />

      {/* Protected routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="runners" element={<RunnersList />} />
        <Route path="runners/provision" element={<ProvisionRunner />} />
        <Route path="runners/:runnerId" element={<RunnerDetail />} />
        
        {/* Admin routes */}
        <Route path="admin" element={<AdminConsole />} />
        <Route path="admin/teams" element={<Teams />} />
        <Route path="admin/policies" element={<LabelPolicies />} />
        <Route path="admin/users" element={<UserManagement />} />
        <Route path="admin/security" element={<SecurityEvents />} />
        <Route path="admin/audit" element={<AuditLog />} />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
