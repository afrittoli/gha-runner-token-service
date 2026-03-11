import { useState } from 'react'
import {
  useTeamMembers,
  useAddTeamMember,
  useRemoveTeamMember,
} from '@hooks/useTeams'
import { useUsers } from '@hooks/useAdmin'
import ActionMenu from '@components/ActionMenu'

interface TeamMembersProps {
  teamId: string
  teamName: string
  onClose: () => void
}

export default function TeamMembers({ teamId, teamName, onClose }: TeamMembersProps) {
  const { data: membersData, isLoading } = useTeamMembers(teamId)
  const addMember = useAddTeamMember(teamId)
  const removeMember = useRemoveTeamMember(teamId)
  const { data: usersData } = useUsers()

  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedUserId, setSelectedUserId] = useState('')

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await addMember.mutateAsync({ user_id: selectedUserId })
      setShowAddModal(false)
      setSelectedUserId('')
    } catch (error) {
      console.error('Failed to add member:', error)
    }
  }

  const handleRemoveMember = async (userId: string, email: string) => {
    if (!confirm(`Remove ${email} from ${teamName}?`)) {
      return
    }
    try {
      await removeMember.mutateAsync(userId)
    } catch (error) {
      console.error('Failed to remove member:', error)
    }
  }

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg p-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gh-blue mx-auto"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Team Members</h2>
            <p className="text-sm text-gray-500 mt-1">{teamName}</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowAddModal(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gh-blue hover:bg-gh-blue-dark"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Member
            </button>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Members List */}
        {membersData && membersData.members.length > 0 ? (
          <div className="bg-white shadow overflow-hidden border border-gray-200 sm:rounded-lg">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    User
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Joined
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {membersData.members.map((member) => (
                  <tr key={member.user_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">
                          {member.display_name || member.email}
                        </div>
                        {member.display_name && (
                          <div className="text-sm text-gray-500">{member.email}</div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(member.joined_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <ActionMenu
                        menuItems={[
                          {
                            label: 'Remove',
                            onClick: () => handleRemoveMember(member.user_id, member.email),
                            disabled: removeMember.isPending,
                            variant: 'danger',
                          },
                        ]}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
              />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No members</h3>
            <p className="mt-1 text-sm text-gray-500">Get started by adding a member to this team.</p>
            <div className="mt-6">
              <button
                onClick={() => setShowAddModal(true)}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gh-blue hover:bg-gh-blue-dark"
              >
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Add First Member
              </button>
            </div>
          </div>
        )}

        {/* Add Member Modal */}
        {showAddModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-md w-full">
              <h3 className="text-lg font-bold mb-4">Add Team Member</h3>
              <form onSubmit={handleAddMember} className="space-y-4">
                <div>
                  <label htmlFor="user-select" className="block text-sm font-medium text-gray-700">
                    User
                  </label>
                  <select
                    id="user-select"
                    required
                    value={selectedUserId}
                    onChange={(e) => setSelectedUserId(e.target.value)}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-gh-blue focus:border-gh-blue"
                  >
                    <option value="">Select a user...</option>
                    {usersData?.users
                      .filter(u => u.is_active && !membersData?.members.some(m => m.user_id === u.id))
                      .map(u => (
                        <option key={u.id} value={u.id}>
                          {u.email}{u.display_name ? ` (${u.display_name})` : ''}
                        </option>
                      ))
                    }
                  </select>
                </div>

                {addMember.isError && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-600 text-sm">
                    Failed to add member. Please check the user ID and try again.
                  </div>
                )}

                <div className="flex justify-end gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setShowAddModal(false)
                      setSelectedUserId('')
                    }}
                    className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={addMember.isPending}
                    className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gh-blue hover:bg-gh-blue-dark disabled:opacity-50"
                  >
                    {addMember.isPending ? 'Adding...' : 'Add Member'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
