import { Outlet } from 'react-router-dom'
import TopNav from './TopNav'
import Sidebar from './Sidebar'
import { useUIStore } from '@store/uiStore'

export default function MainLayout() {
  const { sidebarCollapsed } = useUIStore()
  
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <TopNav />
      <div className="flex-1 flex overflow-hidden">
        <Sidebar />
        <main className={`flex-1 overflow-y-auto px-6 py-8 transition-all duration-300 ${sidebarCollapsed ? 'md:ml-16' : 'md:ml-64'}`}>
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
