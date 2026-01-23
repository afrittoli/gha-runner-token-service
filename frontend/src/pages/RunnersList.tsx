import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useRunners } from '@hooks/useRunners'

export default function RunnersList() {
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState<string>('')

  const { data, isLoading, error } = useRunners({ 
    status: statusFilter || undefined 
  })

  const filteredRunners = data?.runners.filter((runner) => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      runner.runner_name.toLowerCase().includes(query) ||
      runner.provisioned_by.toLowerCase().includes(query) ||
      runner.labels.some((label) => label.toLowerCase().includes(query))
    )
  })

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    { value: 'active', label: 'Active' },
    { value: 'offline', label: 'Offline' },
    { value: 'pending', label: 'Pending' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Runners</h1>
        <button className="btn btn-primary">Provision Runner</button>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search by name, user, or label..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-md
                       focus:outline-none focus:ring-2 focus:ring-gh-blue focus:border-transparent"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-md
                     focus:outline-none focus:ring-2 focus:ring-gh-blue"
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Runners table */}
      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gh-blue mx-auto"></div>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-red-600">
            Failed to load runners. Please try again.
          </div>
        ) : filteredRunners && filteredRunners.length > 0 ? (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Labels
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Provisioned By
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredRunners.map((runner) => (
                <tr key={runner.runner_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Link
                      to={`/runners/${runner.runner_id}`}
                      className="text-gh-blue hover:underline font-medium"
                    >
                      {runner.runner_name}
                    </Link>
                    {runner.ephemeral && (
                      <span className="ml-2 text-xs text-gray-400">
                        (ephemeral)
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`status-badge status-${runner.status}`}>
                      {runner.status}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {runner.labels.slice(0, 3).map((label) => (
                        <span key={label} className="label-pill">
                          {label}
                        </span>
                      ))}
                      {runner.labels.length > 3 && (
                        <span className="text-xs text-gray-400">
                          +{runner.labels.length - 3} more
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {runner.provisioned_by}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(runner.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="p-8 text-center text-gray-500">
            No runners found. Provision a new runner to get started.
          </div>
        )}
      </div>

      {/* Pagination */}
      {data && data.total > 0 && (
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>
            Showing {filteredRunners?.length || 0} of {data.total} runners
          </span>
        </div>
      )}
    </div>
  )
}
