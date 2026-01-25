import { useState } from 'react'
import { useAdminStats, useAdminConfig } from '@hooks/useAdmin'

export default function AdminConsole() {
  const [showSensitive, setShowSensitive] = useState(false)
  const { data: stats, isLoading: statsLoading } = useAdminStats()
  const { data: config, isLoading: configLoading } = useAdminConfig(showSensitive)

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
        <div className="px-4 py-5 sm:px-6 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h3 className="text-lg leading-6 font-medium text-gray-900">System Configuration</h3>
            <p className="mt-1 max-w-2xl text-sm text-gray-500">Global environment variables and settings</p>
          </div>
          <div className="flex items-center space-x-2">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={showSensitive}
                onChange={(e) => setShowSensitive(e.target.checked)}
                className="h-4 w-4 text-gh-blue focus:ring-gh-blue border-gray-300 rounded"
              />
              <span className="ml-2 text-sm text-gray-700">Show sensitive values</span>
            </label>
          </div>
        </div>
        <div className="px-4 py-5 sm:p-0">
          <dl className="sm:divide-y sm:divide-gray-200">
            {config && Object.entries(config).map(([key, value]) => {
              const isSensitive = value === '********'
              const displayValue = isSensitive && !showSensitive ? '********' : value
              
              return (
                <div key={key} className="py-4 sm:py-5 sm:grid sm:grid-cols-3 sm:gap-4 sm:px-6 hover:bg-gray-50 transition-colors">
                  <dt className="text-sm font-medium text-gray-500 font-mono flex items-center">
                    {key}
                    {isSensitive && (
                      <svg className="ml-1 w-4 h-4 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </dt>
                  <dd className="mt-1 text-sm text-gray-900 sm:mt-0 sm:col-span-2">
                    {typeof displayValue === 'boolean' ? (
                      <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${displayValue ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                        {displayValue ? 'True' : 'False'}
                      </span>
                    ) : typeof displayValue === 'object' && displayValue !== null ? (
                      <pre className="text-xs bg-gray-50 p-2 rounded border border-gray-100">{JSON.stringify(displayValue, null, 2)}</pre>
                    ) : isSensitive && !showSensitive ? (
                      <span className="font-mono text-gray-400">{String(displayValue)}</span>
                    ) : (
                      <span className="font-mono">{String(displayValue)}</span>
                    )}
                  </dd>
                </div>
              )
            })}
          </dl>
        </div>
      </div>
    </div>
  )
}
