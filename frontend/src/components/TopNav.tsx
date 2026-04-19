import { Link } from 'react-router-dom'
import { useAuth } from 'react-oidc-context'
import { useAuthStore } from '@store/authStore'
import { useUIStore } from '@store/uiStore'

export default function TopNav() {
  const auth = useAuth()
  const { user } = useAuthStore()
  const { toggleSidebar } = useUIStore()

  const handleLogout = () => {
    auth.removeUser()
    auth.signoutRedirect()
  }

  const userDisplayName = user?.display_name || user?.email || user?.oidc_sub || auth.user?.profile?.email || auth.user?.profile?.name || 'User'

  return (
    <header className="h-16 bg-gh-gray-800 text-white flex items-center justify-between px-4 md:px-6 sticky top-0 z-20">
      <div className="flex items-center space-x-4">
        <button
          onClick={toggleSidebar}
          className="md:hidden p-2 hover:bg-gh-gray-700 rounded-md transition-colors"
          aria-label="Toggle Sidebar"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <Link to="/" className="flex items-center space-x-2">
          <img
            src="https://avatars.githubusercontent.com/u/124737001?s=200&v=4"
            alt="PyTorch Logo"
            className="h-8 w-8 rounded"
          />
          <span className="font-semibold text-lg hidden md:inline">
            GitHub Actions Runner Token Service (GHARTS)
          </span>
          <span className="font-semibold text-lg md:hidden">
            GHARTS
          </span>
        </Link>
      </div>

      <div className="flex items-center space-x-4">
        {/* User Info & Logout */}
        <div className="flex items-center space-x-4 border-l border-gh-gray-600 pl-4">
          <div className="text-right">
            <div className="text-sm font-medium leading-none mb-1">
              {userDisplayName}
            </div>
            <div className="flex items-center justify-end space-x-2">
              {user?.is_admin && (
                <div className="text-[10px] inline-block px-1.5 py-0.5 rounded uppercase font-bold tracking-wider bg-red-500/20 text-red-400">
                  Admin
                </div>
              )}
              {!user?.is_admin && user && (
                <div className="text-[10px] inline-block px-1.5 py-0.5 rounded uppercase font-bold tracking-wider bg-gh-blue/20 text-gh-blue">
                  User
                </div>
              )}
            </div>
          </div>

          <button
            onClick={handleLogout}
            className="p-1.5 text-gray-300 hover:text-white hover:bg-gh-gray-700 rounded-md transition-all"
            title="Sign out"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  )
}
