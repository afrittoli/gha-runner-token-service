import { useAuth } from 'react-oidc-context'
import { Navigate } from 'react-router-dom'

export default function Login() {
  const auth = useAuth()

  // If already authenticated, redirect to dashboard
  if (auth.isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <svg
            className="mx-auto h-16 w-16 text-gh-gray-800"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
          </svg>
          <h2 className="mt-6 text-3xl font-bold text-gray-900">
            GitHub Runner Token Service
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Sign in to manage your self-hosted runners
          </p>
        </div>

        <div className="mt-8 space-y-6">
          <button
            onClick={() => auth.signinRedirect()}
            disabled={auth.isLoading}
            className="w-full flex justify-center py-3 px-4 border border-transparent
                     rounded-md shadow-sm text-sm font-medium text-white bg-gh-gray-800
                     hover:bg-gh-gray-700 focus:outline-none focus:ring-2
                     focus:ring-offset-2 focus:ring-gh-gray-500 disabled:opacity-50
                     disabled:cursor-not-allowed transition-colors"
          >
            {auth.isLoading ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-3 h-5 w-5 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Signing in...
              </>
            ) : (
              'Sign in with SSO'
            )}
          </button>

          <p className="text-center text-xs text-gray-500">
            You will be redirected to your organization's identity provider
          </p>
        </div>

        <div className="mt-8 text-center">
          <a
            href="http://localhost:8000/dashboard-legacy"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-gh-blue hover:underline"
          >
            View public dashboard (no auth required)
          </a>
        </div>
      </div>
    </div>
  )
}
