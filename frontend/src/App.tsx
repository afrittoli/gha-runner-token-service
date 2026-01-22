import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from 'react-oidc-context'
import MainLayout from '@components/MainLayout'
import Dashboard from '@pages/Dashboard'
import RunnersList from '@pages/RunnersList'
import RunnerDetail from '@pages/RunnerDetail'
import LoginCallback from '@pages/LoginCallback'
import Login from '@pages/Login'

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const auth = useAuth()

  if (auth.isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-gh-blue mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (auth.error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center text-red-600">
          <p>Authentication error: {auth.error.message}</p>
          <button
            onClick={() => auth.signinRedirect()}
            className="mt-4 btn btn-primary"
          >
            Try again
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
        <Route path="runners/:runnerId" element={<RunnerDetail />} />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
