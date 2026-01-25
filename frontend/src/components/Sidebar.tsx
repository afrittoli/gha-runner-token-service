import { Link, useLocation } from 'react-router-dom'
import { useAuthStore } from '@store/authStore'
import { useUIStore } from '@store/uiStore'
import { useEffect } from 'react'

const navigation = [
  { 
    name: 'Dashboard', 
    href: '/', 
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    )
  },
  { 
    name: 'Runners', 
    href: '/runners', 
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
      </svg>
    )
  },
]

const adminNavigation = [
  { 
    name: 'Admin Console', 
    href: '/admin', 
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    )
  },
  { 
    name: 'Label Policies', 
    href: '/admin/policies', 
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    )
  },
  { 
    name: 'User Management', 
    href: '/admin/users', 
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
      </svg>
    )
  },
  { 
    name: 'Security Events', 
    href: '/admin/security', 
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    )
  },
  { 
    name: 'Audit Log', 
    href: '/admin/audit', 
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 002-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
      </svg>
    )
  },
]

export default function Sidebar() {
  const location = useLocation()
  const { user } = useAuthStore()
  const { sidebarOpen, closeSidebar, sidebarCollapsed, toggleSidebarCollapse } = useUIStore()

  // Close sidebar on route change (for mobile)
  useEffect(() => {
    closeSidebar()
  }, [location.pathname, closeSidebar])

  const renderLink = (item: typeof navigation[0]) => {
    const isActive = location.pathname === item.href
    return (
      <Link
        key={item.name}
        to={item.href}
        className={`flex items-center ${sidebarCollapsed ? 'justify-center px-2' : 'space-x-3 px-4'} py-2 text-sm font-medium rounded-md transition-colors ${
          isActive
            ? 'bg-gh-gray-100 text-gh-blue'
            : 'text-gray-600 hover:bg-gh-gray-100 hover:text-gh-gray-900'
        }`}
        title={sidebarCollapsed ? item.name : undefined}
      >
        <span className={isActive ? 'text-gh-blue' : 'text-gray-400'}>
          {item.icon}
        </span>
        {!sidebarCollapsed && <span>{item.name}</span>}
      </Link>
    )
  }

  return (
    <>
      {/* Mobile Backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={closeSidebar}
        />
      )}

      <aside className={`
        fixed top-16 bottom-0 left-0 z-10 bg-white border-r border-gray-200 flex flex-col overflow-y-auto transition-all duration-300 transform
        md:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        ${sidebarCollapsed ? 'w-16' : 'w-64'}
      `}>
        {/* Collapse Toggle Button */}
        <div className="flex items-center justify-between p-3 border-b border-gray-200 bg-white">
          {!sidebarCollapsed && (
            <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
              Menu
            </span>
          )}
          <button
            onClick={toggleSidebarCollapse}
            type="button"
            className="p-2 text-gray-600 hover:text-white hover:bg-gh-blue rounded-lg transition-all shadow-sm hover:shadow-md border border-gray-300 bg-white ml-auto"
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {sidebarCollapsed ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
              )}
            </svg>
          </button>
        </div>

        <div className="flex-1 py-6 space-y-8">
          <nav className="px-4 space-y-1">
            {!sidebarCollapsed && (
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-4">
                General
              </div>
            )}
            {navigation.map(renderLink)}
          </nav>

          {user?.is_admin && (
            <nav className="px-4 space-y-1">
              {!sidebarCollapsed && (
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-4">
                  Administration
                </div>
              )}
              {adminNavigation.map(renderLink)}
            </nav>
          )}
        </div>
        
        {!sidebarCollapsed && (
          <div className="p-4 border-t border-gray-200">
            <div className="bg-gh-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">Status</p>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 rounded-full bg-green-500"></div>
                <span className="text-xs font-medium text-gray-700">Service Operational</span>
              </div>
            </div>
          </div>
        )}
        
        {/* Collapsed Status Indicator */}
        {sidebarCollapsed && (
          <div className="p-2 border-t border-gray-200 flex justify-center">
            <div className="w-2 h-2 rounded-full bg-green-500" title="Service Operational"></div>
          </div>
        )}
      </aside>
    </>
  )
}
