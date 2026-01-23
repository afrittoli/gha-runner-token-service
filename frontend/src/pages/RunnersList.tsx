import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useRunners } from '@hooks/useRunners'
import { useBulkDeprovision } from '@hooks/useAdmin'
import { useAuthStore } from '@store/authStore'
import StatusBadge from '@components/StatusBadge'
import LabelPill from '@components/LabelPill'
import { formatDate } from '@utils/formatters'

export default function RunnersList() {
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedRunners, setSelectedRunners] = useState<Set<string>>(new Set())
  const [showBulkModal, setShowBulkModal] = useState(false)
  const [bulkComment, setBulkComment] = useState('')

  const { user } = useAuthStore()
  const { data, isLoading, error } = useRunners({ 
    status: statusFilter || undefined 
  })

  const bulkDeprovision = useBulkDeprovision()

  const toggleRunner = (runnerId: string) => {
    const next = new Set(selectedRunners)
    if (next.has(runnerId)) {
      next.delete(runnerId)
    } else {
      next.add(runnerId)
    }
    setSelectedRunners(next)
  }

  const toggleAll = () => {
    if (selectedRunners.size === filteredRunners?.length) {
      setSelectedRunners(new Set())
    } else if (filteredRunners) {
      setSelectedRunners(new Set(filteredRunners.map(r => r.runner_id)))
    }
  }

  const handleBulkDeprovision = async () => {
    if (selectedRunners.size === 0 || !bulkComment) return

    try {
      await bulkDeprovision.mutateAsync({
        comment: bulkComment,
        runner_ids: Array.from(selectedRunners)
      })
      setSelectedRunners(new Set())
      setShowBulkModal(false)
      setBulkComment('')
    } catch (err) {
      console.error('Bulk deprovision failed:', err)
    }
  }

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
        <div className="flex items-center space-x-3">
          {user?.is_admin && selectedRunners.size > 0 && (
            <button
              onClick={() => setShowBulkModal(true)}
              className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm font-medium transition-colors"
            >
              Bulk Deprovision ({selectedRunners.size})
            </button>
          )}
          <Link to="/runners/provision" className="btn btn-primary">
            Provision Runner
          </Link>
        </div>
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
                {user?.is_admin && (
                  <th className="px-6 py-3 text-left">
                    <input
                      type="checkbox"
                      className="h-4 w-4 text-gh-blue rounded border-gray-300 focus:ring-gh-blue"
                      checked={selectedRunners.size > 0 && selectedRunners.size === filteredRunners?.length}
                      onChange={toggleAll}
                    />
                  </th>
                )}
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
                  {user?.is_admin && (
                    <td className="px-6 py-4 whitespace-nowrap">
                      <input
                        type="checkbox"
                        className="h-4 w-4 text-gh-blue rounded border-gray-300 focus:ring-gh-blue"
                        checked={selectedRunners.has(runner.runner_id)}
                        onChange={() => toggleRunner(runner.runner_id)}
                      />
                    </td>
                  )}
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
                    <StatusBadge status={runner.status} />
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-wrap gap-1">
                      {runner.labels.slice(0, 3).map((label) => (
                        <LabelPill key={label} label={label} />
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
                    {formatDate(runner.created_at)}
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

      {/* Bulk Deprovision Modal */}
      {showBulkModal && (
        <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" onClick={() => setShowBulkModal(false)}></div>
            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>
            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
              <div>
                <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-red-100">
                  <svg className="h-6 w-6 text-red-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div className="mt-3 text-center sm:mt-5">
                  <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                    Bulk Deprovision Runners
                  </h3>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500">
                      You are about to deprovision {selectedRunners.size} runners. This action will remove them from GitHub and mark them as deleted in the service.
                    </p>
                  </div>
                </div>
              </div>
              <div className="mt-4">
                <label htmlFor="comment" className="block text-sm font-medium text-gray-700">
                  Reason for deprovisioning
                </label>
                <div className="mt-1">
                  <textarea
                    id="comment"
                    rows={3}
                    className="shadow-sm focus:ring-gh-blue focus:border-gh-blue block w-full sm:text-sm border border-gray-300 rounded-md"
                    placeholder="Enter reason (min 10 characters)..."
                    value={bulkComment}
                    onChange={(e) => setBulkComment(e.target.value)}
                  />
                </div>
                {bulkComment.length > 0 && bulkComment.length < 10 && (
                  <p className="mt-2 text-sm text-red-600">Comment must be at least 10 characters.</p>
                )}
              </div>
              <div className="mt-5 sm:mt-6 sm:grid sm:grid-cols-2 sm:gap-3 sm:grid-flow-row-dense">
                <button
                  type="button"
                  disabled={bulkComment.length < 10 || bulkDeprovision.isPending}
                  onClick={handleBulkDeprovision}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:col-start-2 sm:text-sm disabled:opacity-50"
                >
                  {bulkDeprovision.isPending ? 'Processing...' : 'Deprovision'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowBulkModal(false)}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gh-blue sm:mt-0 sm:col-start-1 sm:text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
