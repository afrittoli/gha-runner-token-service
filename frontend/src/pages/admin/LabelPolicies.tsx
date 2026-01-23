import { useState } from 'react'
import { useLabelPolicies, useDeleteLabelPolicy, useCreateLabelPolicy } from '@hooks/useAdmin'
import LabelPill from '@components/LabelPill'
import { formatDate } from '@utils/formatters'

export default function LabelPolicies() {
  const [showAddForm, setShowAddForm] = useState(false)
  const [newPolicy, setNewPolicy] = useState({
    user_identity: '',
    allowed_labels: '',
    description: '',
    max_runners: 5,
  })

  const { data, isLoading, error } = useLabelPolicies()
  const deletePolicy = useDeleteLabelPolicy()
  const createPolicy = useCreateLabelPolicy()

  const handleDelete = async (userIdentity: string) => {
    if (window.confirm(`Are you sure you want to delete the policy for ${userIdentity}?`)) {
      try {
        await deletePolicy.mutateAsync(userIdentity)
      } catch (err) {
        console.error('Failed to delete policy:', err)
      }
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createPolicy.mutateAsync({
        user_identity: newPolicy.user_identity,
        allowed_labels: newPolicy.allowed_labels.split(',').map(l => l.trim()).filter(l => l),
        description: newPolicy.description,
        max_runners: newPolicy.max_runners,
      })
      setShowAddForm(false)
      setNewPolicy({
        user_identity: '',
        allowed_labels: '',
        description: '',
        max_runners: 5,
      })
    } catch (err) {
      console.error('Failed to create policy:', err)
    }
  }

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
        <p className="text-red-700">Error loading label policies: {(error as Error).message}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Label Policies</h1>
        <button
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gh-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          onClick={() => setShowAddForm(!showAddForm)}
        >
          {showAddForm ? 'Cancel' : 'Add Policy'}
        </button>
      </div>

      {showAddForm && (
        <div className="bg-white shadow sm:rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Create New Policy</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">User Identity (Email or Sub)</label>
                <input
                  type="text"
                  required
                  value={newPolicy.user_identity}
                  onChange={(e) => setNewPolicy({ ...newPolicy, user_identity: e.target.value })}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
                  placeholder="user@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Max Runners</label>
                <input
                  type="number"
                  required
                  min="1"
                  value={newPolicy.max_runners}
                  onChange={(e) => setNewPolicy({ ...newPolicy, max_runners: parseInt(e.target.value) })}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Allowed Labels (comma separated)</label>
              <input
                type="text"
                required
                value={newPolicy.allowed_labels}
                onChange={(e) => setNewPolicy({ ...newPolicy, allowed_labels: e.target.value })}
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
                placeholder="linux, docker, x64"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Description</label>
              <input
                type="text"
                value={newPolicy.description}
                onChange={(e) => setNewPolicy({ ...newPolicy, description: e.target.value })}
                className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
                placeholder="Team A runners"
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gh-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Create Policy
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="bg-white shadow overflow-hidden sm:rounded-md border border-gray-200">
        <ul className="divide-y divide-gray-200">
          {data?.policies.map((policy) => (
            <li key={policy.user_identity}>
              <div className="px-4 py-4 sm:px-6">
                <div className="flex items-center justify-between">
                  <div className="flex flex-col">
                    <p className="text-sm font-medium text-gh-blue truncate">
                      {policy.user_identity}
                    </p>
                    {policy.description && (
                      <p className="text-xs text-gray-500 mt-1">
                        {policy.description}
                      </p>
                    )}
                  </div>
                  <div className="ml-2 flex-shrink-0 flex">
                    <button
                      onClick={() => handleDelete(policy.user_identity)}
                      className="text-red-600 hover:text-red-900 text-sm font-medium"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="mt-2 sm:flex sm:justify-between">
                  <div className="sm:flex">
                    <div className="flex flex-wrap gap-1">
                      {policy.allowed_labels.map((label) => (
                        <LabelPill key={label} label={label} />
                      ))}
                    </div>
                  </div>
                  <div className="mt-2 flex items-center text-xs text-gray-500 sm:mt-0">
                    <p>
                      Updated {formatDate(policy.updated_at)}
                    </p>
                  </div>
                </div>
              </div>
            </li>
          ))}
          {data?.policies.length === 0 && (
            <li className="px-4 py-8 text-center text-gray-500">
              No label policies configured.
            </li>
          )}
        </ul>
      </div>
    </div>
  )
}
