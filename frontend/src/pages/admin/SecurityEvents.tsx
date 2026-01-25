import { useState } from 'react'
import { useSecurityEvents, SecurityEventFilters } from '@hooks/useAdmin'
import { formatDate } from '@utils/formatters'
import { SecurityEvent } from '@api/client'

export default function SecurityEvents() {
  const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null)
  const [filters, setFilters] = useState<SecurityEventFilters>({
    limit: 50,
    offset: 0,
  })
  const [searchTerm, setSearchTerm] = useState('')
  
  const { data, isLoading, error } = useSecurityEvents(filters)

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
        <p className="text-red-700">Error loading security events: {(error as Error).message}</p>
      </div>
    )
  }

  const getSeverityClass = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'bg-red-200 text-red-900 font-bold'
      case 'high':
        return 'bg-red-100 text-red-800'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800'
      case 'low':
        return 'bg-blue-100 text-blue-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const handleFilterChange = (key: keyof SecurityEventFilters, value: string) => {
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
        <h1 className="text-2xl font-bold text-gray-900">Security Events</h1>
      </div>

      {/* Filters */}
      <div className="bg-white shadow border border-gray-200 sm:rounded-lg p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Event Type</label>
            <select
              value={filters.event_type || ''}
              onChange={(e) => handleFilterChange('event_type', e.target.value)}
              className="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
            >
              <option value="">All Types</option>
              <option value="label_violation">Label Violation</option>
              <option value="quota_exceeded">Quota Exceeded</option>
              <option value="unauthorized_access">Unauthorized Access</option>
              <option value="batch_disable_users">Batch Disable Users</option>
              <option value="batch_delete_runners">Batch Delete Runners</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
            <select
              value={filters.severity || ''}
              onChange={(e) => handleFilterChange('severity', e.target.value)}
              className="block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
            >
              <option value="">All Severities</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
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
                Event Type
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Severity
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actor
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Target
              </th>
              <th scope="col" className="relative px-6 py-3">
                <span className="sr-only">Details</span>
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {data?.events.map((event) => (
              <tr key={event.id} className="hover:bg-gray-50 transition-colors">
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {formatDate(event.timestamp)}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="text-sm font-medium text-gray-900">{event.event_type}</span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getSeverityClass(event.severity)}`}>
                    {event.severity}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {event.user_identity}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {event.runner_name || '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => setSelectedEvent(event)}
                    className="text-gh-blue hover:text-blue-800"
                  >
                    Details
                  </button>
                </td>
              </tr>
            ))}
            </tbody>
          </table>
          {data?.events.length === 0 && (
            <div className="px-6 py-8 text-center text-gray-500">
              No security events found.
            </div>
          )}
        </div>
      </div>

      {/* Details Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" onClick={() => setSelectedEvent(null)}></div>

            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-2xl sm:w-full sm:p-6">
              <div>
                <div className="flex justify-between items-start">
                  <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                    Security Event Details
                  </h3>
                  <button
                    onClick={() => setSelectedEvent(null)}
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
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Type</h4>
                      <p className="mt-1 text-sm text-gray-900 font-medium">{selectedEvent.event_type}</p>
                    </div>
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Severity</h4>
                      <span className={`mt-1 px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getSeverityClass(selectedEvent.severity)}`}>
                        {selectedEvent.severity}
                      </span>
                    </div>
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Timestamp</h4>
                      <p className="mt-1 text-sm text-gray-900">{formatDate(selectedEvent.timestamp)}</p>
                    </div>
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Actor</h4>
                      <p className="mt-1 text-sm text-gray-900">{selectedEvent.user_identity}</p>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Action Taken</h4>
                    <p className="mt-1 text-sm text-gray-900">{selectedEvent.action_taken || 'None recorded'}</p>
                  </div>

                  <div>
                    <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Violation Data</h4>
                    <div className="mt-1 bg-gray-50 rounded-md p-3 border border-gray-200 overflow-auto max-h-64">
                      <pre className="text-xs text-gray-700 whitespace-pre-wrap">
                        {JSON.stringify(selectedEvent.violation_data, null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              </div>
              <div className="mt-6">
                <button
                  type="button"
                  onClick={() => setSelectedEvent(null)}
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
