import { useParams, Link } from 'react-router-dom'
import { useRunner } from '@hooks/useRunners'

export default function RunnerDetail() {
  const { runnerId } = useParams<{ runnerId: string }>()

  const { data: runner, isLoading, error } = useRunner(runnerId)

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-64 mb-4"></div>
          <div className="h-4 bg-gray-200 rounded w-32"></div>
        </div>
      </div>
    )
  }

  if (error || !runner) {
    return (
      <div className="space-y-6">
        <Link to="/runners" className="text-gh-blue hover:underline">
          &larr; Back to Runners
        </Link>
        <div className="card p-6 text-red-600">
          Runner not found or you don't have access to view it.
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <Link to="/runners" className="text-gh-blue hover:underline">
        &larr; Back to Runners
      </Link>

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {runner.runner_name}
          </h1>
          <div className="mt-1 flex items-center space-x-3">
            <span className={`status-badge status-${runner.status}`}>
              {runner.status}
            </span>
            {runner.ephemeral && (
              <span className="text-sm text-gray-500">Ephemeral</span>
            )}
          </div>
        </div>
        <div className="flex space-x-3">
          <button className="btn btn-secondary">Refresh Status</button>
          <button className="btn btn-danger">Delete Runner</button>
        </div>
      </div>

      {/* Details grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Runner info card */}
        <div className="card">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">
              Runner Information
            </h2>
          </div>
          <dl className="divide-y divide-gray-200">
            <div className="px-6 py-4 flex justify-between">
              <dt className="text-sm font-medium text-gray-500">Runner ID</dt>
              <dd className="text-sm text-gray-900 font-mono">
                {runner.runner_id}
              </dd>
            </div>
            <div className="px-6 py-4 flex justify-between">
              <dt className="text-sm font-medium text-gray-500">
                GitHub Runner ID
              </dt>
              <dd className="text-sm text-gray-900">
                {runner.github_runner_id || 'Not registered'}
              </dd>
            </div>
            <div className="px-6 py-4 flex justify-between">
              <dt className="text-sm font-medium text-gray-500">
                Runner Group ID
              </dt>
              <dd className="text-sm text-gray-900">{runner.runner_group_id}</dd>
            </div>
            <div className="px-6 py-4 flex justify-between">
              <dt className="text-sm font-medium text-gray-500">
                Provisioned By
              </dt>
              <dd className="text-sm text-gray-900">{runner.provisioned_by}</dd>
            </div>
            <div className="px-6 py-4 flex justify-between">
              <dt className="text-sm font-medium text-gray-500">Created</dt>
              <dd className="text-sm text-gray-900">
                {new Date(runner.created_at).toLocaleString()}
              </dd>
            </div>
            {runner.registered_at && (
              <div className="px-6 py-4 flex justify-between">
                <dt className="text-sm font-medium text-gray-500">Registered</dt>
                <dd className="text-sm text-gray-900">
                  {new Date(runner.registered_at).toLocaleString()}
                </dd>
              </div>
            )}
            {runner.deleted_at && (
              <div className="px-6 py-4 flex justify-between">
                <dt className="text-sm font-medium text-gray-500">Deleted</dt>
                <dd className="text-sm text-gray-900">
                  {new Date(runner.deleted_at).toLocaleString()}
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Labels card */}
        <div className="card">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">Labels</h2>
          </div>
          <div className="px-6 py-4">
            <div className="flex flex-wrap gap-2">
              {runner.labels.map((label) => (
                <span key={label} className="label-pill">
                  {label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

    </div>
  )
}
