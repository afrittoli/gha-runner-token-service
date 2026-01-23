import { useAdminStats, useAdminConfig } from '@hooks/useAdmin'

export default function AdminConsole() {
  const { data: stats, isLoading: statsLoading, error: statsError } = useAdminStats()
  const { data: config, isLoading: configLoading, error: configError } = useAdminConfig()

  if (statsLoading || configLoading) {
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
        <p className="mt-1 text-sm text-gray-500">System overview and configuration</p>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">Runners</h3>
          <div className="mt-2 flex items-baseline">
            <p className="text-2xl font-semibold text-gray-900">{stats?.runners.total}</p>
            <p className="ml-2 text-sm text-green-600 font-medium">{stats?.runners.active} active</p>
          </div>
        </div>
        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">Users</h3>
          <div className="mt-2 flex items-baseline">
            <p className="text-2xl font-semibold text-gray-900">{stats?.users.total}</p>
            <p className="ml-2 text-sm text-blue-600 font-medium">{stats?.users.admins} admins</p>
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
          <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wider">Label Policies</h3>
          <div className="mt-2 flex items-baseline">
            <p className="text-2xl font-semibold text-gray-900">{stats?.policies.total}</p>
          </div>
        </div>
      </div>

      {/* Configuration Viewer */}
      <div className="bg-white shadow overflow-hidden border border-gray-200 sm:rounded-lg">
        <div className="px-4 py-5 sm:px-6 bg-gray-50 border-b border-gray-200">
          <h3 className="text-lg leading-6 font-medium text-gray-900">System Configuration</h3>
          <p className="mt-1 max-w-2xl text-sm text-gray-500">Global environment variables and settings (sanitized)</p>
        </div>
        <div className="px-4 py-5 sm:p-0">
          <dl className="sm:divide-y sm:divide-gray-200">
            {config && Object.entries(config).map(([key, value]) => (
              <div key={key} className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6 hover:bg-gray-50 transition-colors">
                <dt className="text-sm font-medium text-gray-500 font-mono">{key}</dt>
                <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                  {typeof value === 'boolean' ? (
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${value ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                      {value ? 'True' : 'False'}
                    </span>
                  ) : typeof value === 'object' && value !== null ? (
                    <pre className="text-xs bg-gray-50 p-2 rounded border border-gray-100">{JSON.stringify(value, null, 2)}</pre>
                  ) : (
                    <span className="font-mono">{String(value)}</span>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </div>
  )
}
