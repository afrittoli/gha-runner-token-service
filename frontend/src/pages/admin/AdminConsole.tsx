import { useAdminStats } from '@hooks/useAdmin'

export default function AdminConsole() {
  const { data: stats, isLoading: statsLoading } = useAdminStats()

  if (statsLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gh-blue"></div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Admin Console</h1>
        <p className="mt-1 text-sm text-gray-500">System overview</p>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">Runners</h3>
          <div className="mt-2 flex items-baseline">
            <p className="text-2xl font-semibold text-gray-900">{stats?.runners.total}</p>
            <p className="ml-2 text-sm text-green-600 font-medium">{stats?.runners.active} active</p>
          </div>
        </div>
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">Security</h3>
          <div className="mt-2 flex items-baseline">
            <p className="text-2xl font-semibold text-gray-900">{stats?.security.total_events}</p>
            <p className="ml-2 text-sm text-red-600 font-medium">{stats?.security.critical_events} critical</p>
          </div>
        </div>
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">Teams</h3>
          <div className="mt-2 flex items-baseline">
            <p className="text-2xl font-semibold text-gray-900">{stats?.teams?.total || 0}</p>
            <p className="ml-2 text-sm text-blue-600 font-medium">{stats?.teams?.active || 0} active</p>
          </div>
        </div>
      </div>
    </div>
  )
}
