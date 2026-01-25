import { useState, useEffect, useRef } from 'react'
import { useAuth } from 'react-oidc-context'
import { useAuthStore } from '@store/authStore'
import { useQuery } from '@tanstack/react-query'
import { apiClient, User } from '@api/client'

export default function UserSwitcher() {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const auth = useAuth()
  const { user, impersonation, startImpersonation, stopImpersonation } = useAuthStore()

  // Fetch list of users for impersonation
  const { data: usersData } = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: async () => {
      const response = await apiClient.get<{ users: User[] }>('/api/v1/admin/users')
      return response.data
    },
    enabled: isOpen, // Only fetch when dropdown is open
  })

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  // Only admins can impersonate (check if currently admin OR if impersonating)
  if (!user?.is_admin && !impersonation.isImpersonating) {
    return null
  }

  const handleImpersonate = async (userId: string) => {
    // Get the current OIDC token or use the stored original token if already impersonating
    const oidcToken = impersonation.originalOidcToken || auth.user?.access_token
    if (!oidcToken) {
      console.error('No OIDC token available for impersonation')
      return
    }
    await startImpersonation(userId, oidcToken)
    setIsOpen(false)
  }

  const handleStopImpersonation = async () => {
    await stopImpersonation()
    setIsOpen(false)
  }

  // Filter out admin users and current user
  const availableUsers = usersData?.users.filter(
    (u) => !u.is_admin && u.is_active && u.id !== user?.user_id
  ) || []

  return (
    <div className="relative" ref={dropdownRef}>
      {/* User Switcher Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center space-x-2 px-3 py-1.5 bg-gh-gray-700 hover:bg-gh-gray-600 rounded-md transition-colors text-sm"
        title="Switch User (Demo)"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
        </svg>
        <span className="hidden md:inline">Switch User</span>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-gh-gray-800 border border-gh-gray-600 rounded-md shadow-lg z-50 max-h-96 overflow-y-auto">
          <div className="px-4 py-2 border-b border-gh-gray-600">
            <p className="text-xs text-gray-400 font-medium">DEMO: Switch User View</p>
          </div>
          
          <div className="py-1">
            {/* Return to Admin option when impersonating */}
            {impersonation.isImpersonating && (
              <button
                onClick={handleStopImpersonation}
                className="w-full text-left px-4 py-2 text-sm hover:bg-gh-gray-700 transition-colors border-b border-gh-gray-600"
              >
                <div className="flex items-center space-x-2">
                  <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                  </svg>
                  <div>
                    <div className="font-medium text-red-400">Return to Admin</div>
                    <div className="text-xs text-gray-400">{impersonation.originalAdmin}</div>
                  </div>
                </div>
              </button>
            )}
            
            {/* List of users to impersonate */}
            {availableUsers.length === 0 && !impersonation.isImpersonating ? (
              <div className="px-4 py-3 text-sm text-gray-400">
                No users available for impersonation
              </div>
            ) : (
              availableUsers.map((u) => (
                <button
                  key={u.id}
                  onClick={() => handleImpersonate(u.id)}
                  className="w-full text-left px-4 py-2 text-sm hover:bg-gh-gray-700 transition-colors flex items-center justify-between"
                >
                  <div>
                    <div className="font-medium text-white">
                      {u.display_name || u.email || 'Unknown User'}
                    </div>
                    {u.email && u.display_name && (
                      <div className="text-xs text-gray-400">{u.email}</div>
                    )}
                  </div>
                  {impersonation.isImpersonating && impersonation.impersonatedUser?.id === u.id && (
                    <span className="text-yellow-500 text-xs">✓ Active</span>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// Made with Bob
