import { useState } from 'react'
import { useTeams, useCreateTeam, useDeactivateTeam, TeamCreate } from '@hooks/useTeams'
import TeamMembers from './TeamMembers'

export default function Teams() {
  const { data, isLoading } = useTeams()
  const createTeam = useCreateTeam()
  const deactivateTeam = useDeactivateTeam()

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null)
  const [selectedTeamName, setSelectedTeamName] = useState<string>('')
  const [deactivateDialog, setDeactivateDialog] = useState<{
    teamId: string
    teamName: string
  } | null>(null)
  const [deactivateReason, setDeactivateReason] = useState('')
  const [formData, setFormData] = useState<TeamCreate>({
    name: '',
    description: '',
    required_labels: [],
    optional_label_patterns: [],
    max_runners: undefined,
  })
  const [labelInput, setLabelInput] = useState('')
  const [patternInput, setPatternInput] = useState('')

  const handleCreateTeam = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createTeam.mutateAsync(formData)
      setShowCreateModal(false)
      resetForm()
    } catch (error) {
      console.error('Failed to create team:', error)
    }
  }

  const handleDeactivateTeam = async (teamId: string, teamName: string) => {
    setDeactivateDialog({ teamId, teamName })
  }

  const handleConfirmDeactivate = async () => {
    if (!deactivateDialog || !deactivateReason.trim()) {
      return
    }

    try {
      await deactivateTeam.mutateAsync({
        teamId: deactivateDialog.teamId,
        reason: deactivateReason.trim(),
      })
      setDeactivateDialog(null)
      setDeactivateReason('')
    } catch (error) {
      console.error('Failed to deactivate team:', error)
    }
  }

  const handleCancelDeactivate = () => {
    setDeactivateDialog(null)
    setDeactivateReason('')
  }

  const resetForm = () => {
    setFormData({
      name: '',
      description: '',
      required_labels: [],
      optional_label_patterns: [],
      max_runners: undefined,
    })
    setLabelInput('')
    setPatternInput('')
  }

  const addLabel = () => {
    if (labelInput.trim() && !formData.required_labels.includes(labelInput.trim())) {
      setFormData({
        ...formData,
        required_labels: [...formData.required_labels, labelInput.trim()],
      })
      setLabelInput('')
    }
  }

  const removeLabel = (label: string) => {
    setFormData({
      ...formData,
      required_labels: formData.required_labels.filter(l => l !== label),
    })
  }

  const addPattern = () => {
    const patterns = formData.optional_label_patterns || []
    if (patternInput.trim() && !patterns.includes(patternInput.trim())) {
      setFormData({
        ...formData,
        optional_label_patterns: [...patterns, patternInput.trim()],
      })
      setPatternInput('')
    }
  }

  const removePattern = (pattern: string) => {
    setFormData({
      ...formData,
      optional_label_patterns: (formData.optional_label_patterns || []).filter(p => p !== pattern),
    })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gh-blue"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Teams</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage teams and their runner provisioning policies
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gh-blue hover:bg-gh-blue-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gh-blue"
        >
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Create Team
        </button>
      </div>

      {/* Teams List */}
      <div className="bg-white shadow overflow-hidden border border-gray-200 sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Team
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Required Labels
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Max Runners
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Members
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {data?.teams.map((team) => (
              <tr key={team.id} className="hover:bg-gray-50">
                <td className="px-6 py-4 whitespace-nowrap">
                  <div>
                    <div className="text-sm font-medium text-gray-900">{team.name}</div>
                    {team.description && (
                      <div className="text-sm text-gray-500">{team.description}</div>
                    )}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex flex-wrap gap-1">
                    {team.required_labels.map((label) => (
                      <span
                        key={label}
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800"
                      >
                        {label}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {team.max_runners ?? 'Unlimited'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {team.member_count ?? 0}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span
                    className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      team.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {team.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <div className="flex items-center justify-end gap-3">
                    <button
                      onClick={() => {
                        setSelectedTeamId(team.id)
                        setSelectedTeamName(team.name)
                      }}
                      className="text-gh-blue hover:text-gh-blue-dark"
                    >
                      Manage Members
                    </button>
                    {team.is_active && (
                      <button
                        onClick={() => handleDeactivateTeam(team.id, team.name)}
                        className="text-red-600 hover:text-red-900"
                      >
                        Deactivate
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create Team Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">Create New Team</h2>
            <form onSubmit={handleCreateTeam} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Team Name</label>
                <input
                  type="text"
                  required
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-gh-blue focus:border-gh-blue"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Description</label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={3}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-gh-blue focus:border-gh-blue"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Required Labels
                </label>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={labelInput}
                    onChange={(e) => setLabelInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addLabel())}
                    placeholder="e.g., linux, docker"
                    className="flex-1 border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-gh-blue focus:border-gh-blue"
                  />
                  <button
                    type="button"
                    onClick={addLabel}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
                  >
                    Add
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {formData.required_labels.map((label) => (
                    <span
                      key={label}
                      className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800"
                    >
                      {label}
                      <button
                        type="button"
                        onClick={() => removeLabel(label)}
                        className="ml-2 text-blue-600 hover:text-blue-800"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Optional Label Patterns (regex)
                </label>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={patternInput}
                    onChange={(e) => setPatternInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addPattern())}
                    placeholder="e.g., custom-.*"
                    className="flex-1 border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-gh-blue focus:border-gh-blue"
                  />
                  <button
                    type="button"
                    onClick={addPattern}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
                  >
                    Add
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {(formData.optional_label_patterns || []).map((pattern) => (
                    <span
                      key={pattern}
                      className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-purple-100 text-purple-800"
                    >
                      {pattern}
                      <button
                        type="button"
                        onClick={() => removePattern(pattern)}
                        className="ml-2 text-purple-600 hover:text-purple-800"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Max Runners (optional)
                </label>
                <input
                  type="number"
                  min="0"
                  value={formData.max_runners ?? ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      max_runners: e.target.value ? parseInt(e.target.value) : undefined,
                    })
                  }
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-gh-blue focus:border-gh-blue"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false)
                    resetForm()
                  }}
                  className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createTeam.isPending}
                  className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gh-blue hover:bg-gh-blue-dark disabled:opacity-50"
                >
                  {createTeam.isPending ? 'Creating...' : 'Create Team'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Deactivate Confirmation Dialog */}
      {deactivateDialog && (
        <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" onClick={handleCancelDeactivate}></div>

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
                    Deactivate Team
                  </h3>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500">
                      Are you sure you want to deactivate <strong>{deactivateDialog.teamName}</strong>?
                      Team members will lose access to provision runners. Please provide a reason for this action.
                    </p>
                  </div>
                  <div className="mt-4">
                    <label htmlFor="deactivate-reason" className="block text-sm font-medium text-gray-700 text-left">
                      Reason (required)
                    </label>
                    <textarea
                      id="deactivate-reason"
                      rows={3}
                      value={deactivateReason}
                      onChange={(e) => setDeactivateReason(e.target.value)}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
                      placeholder="e.g., Team restructuring, project completed"
                    />
                  </div>
                </div>
              </div>
              <div className="mt-5 sm:mt-6 sm:grid sm:grid-cols-2 sm:gap-3 sm:grid-flow-row-dense">
                <button
                  type="button"
                  onClick={handleConfirmDeactivate}
                  disabled={!deactivateReason.trim() || deactivateTeam.isPending}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:col-start-2 sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {deactivateTeam.isPending ? 'Deactivating...' : 'Deactivate'}
                </button>
                <button
                  type="button"
                  onClick={handleCancelDeactivate}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gh-blue sm:mt-0 sm:col-start-1 sm:text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Team Members Modal */}
      {selectedTeamId && (
        <TeamMembers
          teamId={selectedTeamId}
          teamName={selectedTeamName}
          onClose={() => {
            setSelectedTeamId(null)
            setSelectedTeamName('')
          }}
        />
      )}
    </div>
  )
}

// Made with Bob
