import { useState } from 'react'
import { useUsers, useUpdateUser, useActivateUser, useDeleteUser, useCreateUser, useBatchDisableUsers, useBatchRestoreUsers } from '@hooks/useAdmin'
import { useTeams } from '@hooks/useTeams'
import StatusBadge from '@components/StatusBadge'
import { formatDate } from '@utils/formatters'

export default function UserManagement() {
  const [showAddForm, setShowAddForm] = useState(false)
  const [newUser, setNewUser] = useState({
    email: '',
    display_name: '',
    is_admin: false,
    team_ids: [] as string[],
  })
  const [deactivateDialog, setDeactivateDialog] = useState<{
    userId: string
    userName: string
  } | null>(null)
  const [deactivateComment, setDeactivateComment] = useState('')
  const [showAdmins, setShowAdmins] = useState(false) // Hide admins by default
  const [showInactive, setShowInactive] = useState(true) // Show inactive users
  const [selectedUserIds, setSelectedUserIds] = useState<Set<string>>(new Set())
  const [batchDialog, setBatchDialog] = useState<{
    action: 'disable' | 'restore'
    count: number
  } | null>(null)
  const [batchComment, setBatchComment] = useState('')

  const { data, isLoading, error } = useUsers(true) // Include inactive
  const { data: teamsData } = useTeams(false) // Only active teams
  
  // Filter out admin team from selection
  const availableTeams = teamsData?.teams.filter(t => t.name.toLowerCase() !== 'admin') || []
  
  // Filter users based on admin status and active status
  const filteredUsers = data?.users.filter(user => {
    if (!showAdmins && user.is_admin) return false
    if (!showInactive && !user.is_active) return false
    return true
  })
  const updateUser = useUpdateUser()
  const activateUser = useActivateUser()
  const deleteUser = useDeleteUser()
  const createUser = useCreateUser()
  const batchDisableUsers = useBatchDisableUsers()
  const batchRestoreUsers = useBatchRestoreUsers()

  const handleToggleAdmin = async (userId: string, currentIsAdmin: boolean) => {
    try {
      await updateUser.mutateAsync({
        userId,
        data: { is_admin: !currentIsAdmin }
      })
    } catch (err) {
      console.error('Failed to update user:', err)
    }
  }

  const handleToggleStatus = async (userId: string, userName: string, isActive: boolean) => {
    if (isActive) {
      // Show confirmation dialog for deactivation
      setDeactivateDialog({ userId, userName })
    } else {
      // Activate without confirmation
      try {
        await activateUser.mutateAsync(userId)
      } catch (err) {
        console.error('Failed to activate user:', err)
      }
    }
  }

  const handleConfirmDeactivate = async () => {
    if (!deactivateDialog || !deactivateComment.trim()) {
      return
    }

    try {
      await deleteUser.mutateAsync({
        userId: deactivateDialog.userId,
        comment: deactivateComment.trim()
      })
      setDeactivateDialog(null)
      setDeactivateComment('')
    } catch (err) {
      console.error('Failed to deactivate user:', err)
    }
  }

  const handleCancelDeactivate = () => {
    setDeactivateDialog(null)
    setDeactivateComment('')
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await createUser.mutateAsync(newUser)
      setShowAddForm(false)
      setNewUser({
        email: '',
        display_name: '',
        is_admin: false,
        team_ids: [],
      })
    } catch (err) {
      console.error('Failed to create user:', err)
    }
  }

  const handleToggleTeam = (teamId: string) => {
    const currentTeams = newUser.team_ids
    if (currentTeams.includes(teamId)) {
      setNewUser({ ...newUser, team_ids: currentTeams.filter(id => id !== teamId) })
    } else {
      setNewUser({ ...newUser, team_ids: [...currentTeams, teamId] })
    }
  }

  const handleToggleSelectAll = () => {
    if (selectedUserIds.size === filteredUsers?.length) {
      setSelectedUserIds(new Set())
    } else {
      setSelectedUserIds(new Set(filteredUsers?.map(u => u.id) || []))
    }
  }

  const handleToggleSelect = (userId: string) => {
    const newSelection = new Set(selectedUserIds)
    if (newSelection.has(userId)) {
      newSelection.delete(userId)
    } else {
      newSelection.add(userId)
    }
    setSelectedUserIds(newSelection)
  }

  const handleBatchDisable = () => {
    const activeSelected = filteredUsers?.filter(u =>
      selectedUserIds.has(u.id) && u.is_active
    ) || []
    if (activeSelected.length > 0) {
      setBatchDialog({ action: 'disable', count: activeSelected.length })
    }
  }

  const handleBatchRestore = () => {
    const inactiveSelected = filteredUsers?.filter(u =>
      selectedUserIds.has(u.id) && !u.is_active
    ) || []
    if (inactiveSelected.length > 0) {
      setBatchDialog({ action: 'restore', count: inactiveSelected.length })
    }
  }

  const handleConfirmBatch = async () => {
    if (!batchDialog || !batchComment.trim()) {
      return
    }

    try {
      const userIds = Array.from(selectedUserIds)
      if (batchDialog.action === 'disable') {
        await batchDisableUsers.mutateAsync({
          comment: batchComment.trim(),
          user_ids: userIds,
          exclude_admins: true,
        })
      } else {
        await batchRestoreUsers.mutateAsync({
          comment: batchComment.trim(),
          user_ids: userIds,
        })
      }
      setBatchDialog(null)
      setBatchComment('')
      setSelectedUserIds(new Set())
    } catch (err) {
      console.error('Failed to perform batch action:', err)
    }
  }

  const handleCancelBatch = () => {
    setBatchDialog(null)
    setBatchComment('')
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
        <p className="text-red-700">Error loading users: {(error as Error).message}</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
        <button
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gh-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          onClick={() => setShowAddForm(!showAddForm)}
        >
          {showAddForm ? 'Cancel' : 'Add User'}
        </button>
      </div>

      {showAddForm && (
        <div className="bg-white shadow sm:rounded-lg border border-gray-200 p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Add New User</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Email</label>
                <input
                  type="email"
                  required
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
                  placeholder="user@example.com"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Display Name</label>
                <input
                  type="text"
                  required
                  value={newUser.display_name}
                  onChange={(e) => setNewUser({ ...newUser, display_name: e.target.value })}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
                  placeholder="John Doe"
                />
              </div>
            </div>
            <div className="flex items-center">
              <input
                type="checkbox"
                id="is_admin"
                checked={newUser.is_admin}
                onChange={(e) => setNewUser({ ...newUser, is_admin: e.target.checked, team_ids: e.target.checked ? [] : newUser.team_ids })}
                className="h-4 w-4 text-gh-blue focus:ring-gh-blue border-gray-300 rounded"
              />
              <label htmlFor="is_admin" className="ml-2 block text-sm text-gray-900">
                Admin User
              </label>
            </div>
            
            {!newUser.is_admin && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Team Membership <span className="text-red-600">*</span>
                </label>
                <p className="text-xs text-gray-500 mb-2">Select at least one team for this user</p>
                <div className="border border-gray-300 rounded-md p-3 max-h-48 overflow-y-auto">
                  {availableTeams.length === 0 ? (
                    <p className="text-sm text-gray-500">No teams available. Create a team first.</p>
                  ) : (
                    <div className="space-y-2">
                      {availableTeams.map((team) => (
                        <label key={team.id} className="flex items-center cursor-pointer hover:bg-gray-50 p-2 rounded">
                          <input
                            type="checkbox"
                            checked={newUser.team_ids.includes(team.id)}
                            onChange={() => handleToggleTeam(team.id)}
                            className="h-4 w-4 text-gh-blue focus:ring-gh-blue border-gray-300 rounded"
                          />
                          <span className="ml-2 text-sm text-gray-900">{team.name}</span>
                          {team.description && (
                            <span className="ml-2 text-xs text-gray-500">- {team.description}</span>
                          )}
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {newUser.is_admin && (
              <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                <p className="text-sm text-blue-800">
                  <strong>Admin users</strong> are automatically added to the admin team and have full system access.
                </p>
              </div>
            )}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={!newUser.is_admin && newUser.team_ids.length === 0}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gh-blue hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Create User
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filter Controls */}
      <div className="bg-white shadow border border-gray-200 sm:rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-6">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={showAdmins}
                onChange={(e) => setShowAdmins(e.target.checked)}
                className="h-4 w-4 text-gh-blue focus:ring-gh-blue border-gray-300 rounded"
              />
              <span className="ml-2 text-sm text-gray-700">Show Admin Users</span>
            </label>
            
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={showInactive}
                onChange={(e) => setShowInactive(e.target.checked)}
                className="h-4 w-4 text-gh-blue focus:ring-gh-blue border-gray-300 rounded"
              />
              <span className="ml-2 text-gray-700">Show Inactive Users</span>
            </label>
          </div>
          
          <div className="text-sm text-gray-500">
            Showing {filteredUsers?.length || 0} of {data?.users.length || 0} users
          </div>
        </div>

        {/* Bulk Actions */}
        {selectedUserIds.size > 0 && (
          <div className="flex items-center justify-between pt-4 border-t border-gray-200">
            <div className="text-sm text-gray-700">
              <span className="font-medium">{selectedUserIds.size}</span> user{selectedUserIds.size !== 1 ? 's' : ''} selected
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={handleBatchDisable}
                disabled={!filteredUsers?.some(u => selectedUserIds.has(u.id) && u.is_active)}
                className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Deactivate Selected
              </button>
              <button
                onClick={handleBatchRestore}
                disabled={!filteredUsers?.some(u => selectedUserIds.has(u.id) && !u.is_active)}
                className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Restore Selected
              </button>
              <button
                onClick={() => setSelectedUserIds(new Set())}
                className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gh-blue"
              >
                Clear Selection
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="bg-white shadow overflow-hidden border border-gray-200 sm:rounded-lg">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th scope="col" className="px-6 py-3 text-left">
                <input
                  type="checkbox"
                  checked={selectedUserIds.size > 0 && selectedUserIds.size === filteredUsers?.length}
                  onChange={handleToggleSelectAll}
                  className="h-4 w-4 text-gh-blue focus:ring-gh-blue border-gray-300 rounded"
                />
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                User
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Admin
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Last Login
              </th>
              <th scope="col" className="relative px-6 py-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredUsers?.map((user) => (
              <tr key={user.id} className={selectedUserIds.has(user.id) ? 'bg-blue-50' : ''}>
                <td className="px-6 py-4 whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={selectedUserIds.has(user.id)}
                    onChange={() => handleToggleSelect(user.id)}
                    className="h-4 w-4 text-gh-blue focus:ring-gh-blue border-gray-300 rounded"
                  />
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex flex-col">
                    <div className="text-sm font-medium text-gray-900">{user.display_name || 'N/A'}</div>
                    <div className="text-sm text-gray-500">{user.email || user.oidc_sub}</div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <StatusBadge status={user.is_active ? 'active' : 'offline'} />
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <input
                    type="checkbox"
                    checked={user.is_admin}
                    onChange={() => handleToggleAdmin(user.id, user.is_admin)}
                    className="h-4 w-4 text-gh-blue focus:ring-gh-blue border-gray-300 rounded"
                  />
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {user.last_login_at ? formatDate(user.last_login_at) : 'Never'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => handleToggleStatus(user.id, user.display_name || user.email || user.oidc_sub || 'Unknown', user.is_active)}
                    className={`${user.is_active ? 'text-red-600 hover:text-red-900' : 'text-green-600 hover:text-green-900'}`}
                  >
                    {user.is_active ? 'Deactivate' : 'Activate'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredUsers?.length === 0 && (
          <div className="px-6 py-8 text-center text-gray-500">
            {data?.users.length === 0 ? 'No users found.' : 'No users match the current filters.'}
          </div>
        )}
      </div>

      {/* Batch Action Confirmation Dialog */}
      {batchDialog && (
        <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" aria-hidden="true" onClick={handleCancelBatch}></div>

            <span className="hidden sm:inline-block sm:align-middle sm:h-screen" aria-hidden="true">&#8203;</span>

            <div className="inline-block align-bottom bg-white rounded-lg px-4 pt-5 pb-4 text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full sm:p-6">
              <div>
                <div className={`mx-auto flex items-center justify-center h-12 w-12 rounded-full ${batchDialog.action === 'disable' ? 'bg-red-100' : 'bg-green-100'}`}>
                  <svg className={`h-6 w-6 ${batchDialog.action === 'disable' ? 'text-red-600' : 'text-green-600'}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div className="mt-3 text-center sm:mt-5">
                  <h3 className="text-lg leading-6 font-medium text-gray-900" id="modal-title">
                    {batchDialog.action === 'disable' ? 'Deactivate Users' : 'Restore Users'}
                  </h3>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500">
                      Are you sure you want to {batchDialog.action === 'disable' ? 'deactivate' : 'restore'} <strong>{batchDialog.count}</strong> user{batchDialog.count !== 1 ? 's' : ''}?
                      Please provide a reason for this action.
                    </p>
                  </div>
                  <div className="mt-4">
                    <label htmlFor="batch-comment" className="block text-sm font-medium text-gray-700 text-left">
                      Reason (required, 10-500 characters)
                    </label>
                    <textarea
                      id="batch-comment"
                      rows={3}
                      value={batchComment}
                      onChange={(e) => setBatchComment(e.target.value)}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
                      placeholder={batchDialog.action === 'disable' ? 'e.g., Security incident requiring immediate action' : 'e.g., Restoring access after review'}
                      minLength={10}
                      maxLength={500}
                    />
                    <p className="mt-1 text-xs text-gray-500 text-left">
                      {batchComment.length}/500 characters
                    </p>
                  </div>
                </div>
              </div>
              <div className="mt-5 sm:mt-6 sm:grid sm:grid-cols-2 sm:gap-3 sm:grid-flow-row-dense">
                <button
                  type="button"
                  onClick={handleConfirmBatch}
                  disabled={batchComment.trim().length < 10}
                  className={`w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 text-base font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2 sm:col-start-2 sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed ${
                    batchDialog.action === 'disable'
                      ? 'bg-red-600 hover:bg-red-700 focus:ring-red-500'
                      : 'bg-green-600 hover:bg-green-700 focus:ring-green-500'
                  }`}
                >
                  {batchDialog.action === 'disable' ? 'Deactivate' : 'Restore'}
                </button>
                <button
                  type="button"
                  onClick={handleCancelBatch}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gh-blue sm:mt-0 sm:col-start-1 sm:text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
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
                    Deactivate User
                  </h3>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500">
                      Are you sure you want to deactivate <strong>{deactivateDialog.userName}</strong>?
                      Please provide a reason for this action.
                    </p>
                  </div>
                  <div className="mt-4">
                    <label htmlFor="deactivate-comment" className="block text-sm font-medium text-gray-700 text-left">
                      Reason (required, 10-500 characters)
                    </label>
                    <textarea
                      id="deactivate-comment"
                      rows={3}
                      value={deactivateComment}
                      onChange={(e) => setDeactivateComment(e.target.value)}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2 focus:ring-gh-blue focus:border-gh-blue"
                      placeholder="e.g., User left the organization"
                      minLength={10}
                      maxLength={500}
                    />
                    <p className="mt-1 text-xs text-gray-500 text-left">
                      {deactivateComment.length}/500 characters
                    </p>
                  </div>
                </div>
              </div>
              <div className="mt-5 sm:mt-6 sm:grid sm:grid-cols-2 sm:gap-3 sm:grid-flow-row-dense">
                <button
                  type="button"
                  onClick={handleConfirmDeactivate}
                  disabled={deactivateComment.trim().length < 10}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:col-start-2 sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Deactivate
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
    </div>
  )
}
