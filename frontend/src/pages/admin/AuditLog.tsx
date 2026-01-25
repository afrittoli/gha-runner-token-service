import { useState } from 'react'
import { useAuditLogs, AuditLog, AuditLogFilters } from '@hooks/useAdmin'
import { formatDate } from '@utils/formatters'

// Format event data for display, hiding empty arrays
function formatEventData(data: Record<string, unknown> | null): Record<string, unknown> {
  if (!data) return {}
  
  const formatted: Record<string, unknown> = {}
  
  for (const [key, value] of Object.entries(data)) {
    // Skip empty arrays
    if (Array.isArray(value) && value.length === 0) {
      continue
    }
    formatted[key] = value
  }
  
  return formatted
}

export default function AuditLogPage() {
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null)
  const [filters, setFilters] = useState<AuditLogFilters>({
    limit: 50,
    offset: 0,
  })
  const [searchTerm, setSearchTerm] = useState('')
  
  const { data, isLoading, error } = useAuditLogs(filters)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gh-blue"></div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 p-4 rounded-md">
        <p className="text-red-700">Error loading audit logs: {(error as Error).message}</p>
      </div>
    )
  }

  const handleFilterChange = (key: keyof AuditLogFilters, value: string) => {
    setFilters(prev => ({
      ...prev,
      [key]: value || undefined,
      offset: 0, // Reset pagination when filters change
    }))
  }

  const handleSearch = () => {
    setFilters(prev => ({
      ...prev,
      user_identity: searchTerm || undefined,
      offset: 0,
    }))
  }

  const handleClearFilters = () => {
    setFilters({ limit: 50, offset: 0 })
    setSearchTerm('')
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
      </div>

      {/* Filters */}
      <div className="bg-white shadow border border-gray-200 sm:rounded-lg p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Event Type</label>
            <select
              value={filters.event_type || ''}
              onChange={(e) => handleFilterChange('event_type', e.target.value)}
              className="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
            >
              <option value="">All Events</option>
              <option value="provision_runner">Provision Runner</option>
              <option value="deprovision_runner">Deprovision Runner</option>
              <option value="register_runner">Register Runner</option>
              <option value="update_runner">Update Runner</option>
              <option value="create_label_policy">Create Label Policy</option>
              <option value="update_label_policy">Update Label Policy</option>
              <option value="delete_label_policy">Delete Label Policy</option>
              <option value="create_user">Create User</option>
              <option value="update_user">Update User</option>
              <option value="deactivate_user">Deactivate User</option>
              <option value="activate_user">Activate User</option>
              <option value="batch_disable_users">Batch Disable Users</option>
              <option value="batch_delete_runners">Batch Delete Runners</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">User Identity</label>
            <div className="flex space-x-2">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search by user..."
                className="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
              />
              <button
                onClick={handleSearch}
                className="px-3 py-2 bg-gh-blue text-white rounded-md hover:bg-blue-700 whitespace-nowrap"
              >
                Search
              </button>
            </div>
          </div>

          <div className="flex items-end">
            <button
              onClick={handleClearFilters}
              className="w-full px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white shadow border border-gray-200 sm:rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
            <tr>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Timestamp
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Event
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                User
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Runner
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th scope="col" className="relative px-6 py-3">
                <span className="sr-only">Details</span>
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {data?.logs.map((log) => (
              <tr key={log.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatDate(log.timestamp)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                  {log.event_type}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {log.user_identity}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {log.runner_name || '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                    log.success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                  }`}>
                    {log.success ? 'Success' : 'Failed'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => setSelectedLog(log)}
                    className="text-gh-blue hover:text-blue-800"
                  >
                    Details
                  </button>
                </td>
              </tr>
            ))}
            </tbody>
          </table>
          {data?.logs.length === 0 && (
            <div className="px-6 py-8 text-center text-gray-500">
              No audit logs found.
            </div>
          )}
        </div>
      </div>

      {/* Details Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" onClick={() => setSelectedLog(null)}></div>

            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full sm:p-6">
              <div>
                <div className="flex justify-between items-start">
                  <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                    Event Details: {selectedLog.event_type}
                  </h3>
                  <button
                    onClick={() => setSelectedLog(null)}
                    className="bg-white rounded-md text-gray-400 hover:text-gray-500 focus:outline-none"
                  >
                    <span className="sr-only">Close</span>
                    <svg className="h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                <div className="mt-4 space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Timestamp</h4>
                      <p className="mt-1 text-sm text-gray-900">{formatDate(selectedLog.timestamp)}</p>
                    </div>
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</h4>
                      <p className="mt-1 text-sm text-gray-900">{selectedLog.success ? 'Success' : 'Failed'}</p>
                    </div>
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Actor</h4>
                      <p className="mt-1 text-sm text-gray-900">{selectedLog.user_identity}</p>
                    </div>
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">IP Address</h4>
                      <p className="mt-1 text-sm text-gray-900">{selectedLog.request_ip || 'N/A'}</p>
                    </div>
                  </div>

                  {selectedLog.error_message && (
                    <div className="bg-red-50 p-3 rounded-md border border-red-200">
                      <h4 className="text-xs font-semibold text-red-700 uppercase tracking-wider">Error Message</h4>
                      <p className="mt-1 text-sm text-red-800">{selectedLog.error_message}</p>
                    </div>
                  )}

                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Event Data</h4>
                    <div className="mt-1 bg-gray-50 rounded-md p-3 border border-gray-200 overflow-auto max-h-64">
                      <pre className="text-xs text-gray-700 whitespace-pre-wrap">
                        {JSON.stringify(formatEventData(selectedLog.event_data), null, 2)}
                      </pre>
                    </div>
                  </div>

                  <div className="text-xs text-gray-400 font-mono">
                    User Agent: {selectedLog.user_agent}
                  </div>
                </div>
              </div>
              <div className="mt-6">
                <button
                  type="button"
                  onClick={() => setSelectedLog(null)}
                  className="w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gh-blue sm:text-sm"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
