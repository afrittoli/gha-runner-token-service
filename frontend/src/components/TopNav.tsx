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

  const userDisplayName = user?.display_name || user?.email || auth.user?.profile?.email || auth.user?.profile?.name || 'User'

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
          <svg
            className="h-8 w-8 text-white"
            fill="currentColor"
            viewBox="0 0 24 24"
          >
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
          </svg>
          <span className="font-semibold text-lg hidden md:inline">
            GitHub Actions Runner Service
          </span>
          <span className="font-semibold text-lg md:hidden">
            GHA Service
          </span>
        </Link>
      </div>

      <div className="flex items-center space-x-6">
        {/* Search - placeholder for now */}
        <div className="hidden lg:flex items-center bg-gh-gray-700 rounded-md px-3 py-1.5 w-64">
          <svg className="w-4 h-4 text-gray-400 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input 
            type="text" 
            placeholder="Search..." 
            className="bg-transparent border-none text-sm focus:ring-0 text-white placeholder-gray-400 w-full"
          />
        </div>

        {/* User Info & Logout */}
        <div className="flex items-center space-x-4 border-l border-gh-gray-600 pl-6">
          <div className="text-right">
            <div className="text-sm font-medium leading-none mb-1">
              {userDisplayName}
            </div>
            {user && (
              <div className={`text-[10px] inline-block px-1.5 py-0.5 rounded uppercase font-bold tracking-wider ${
                user.is_admin ? 'bg-red-500/20 text-red-400' : 'bg-gh-blue/20 text-gh-blue'
              }`}>
                {user.is_admin ? 'Admin' : 'User'}
              </div>
            )}
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
