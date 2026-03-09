import { useState } from 'react'
import type { AxiosError } from 'axios'
import {
  useTeamOAuthClient,
  useRegisterOAuthClient,
  useUpdateOAuthClient,
  useDeleteOAuthClient,
  type OAuthClientCreate,
} from '@hooks/useOAuthClients'

interface TeamM2MClientProps {
  teamId: string
  teamName: string
  onClose: () => void
}

function formatDate(iso: string | null): string {
  if (!iso) return 'Never'
  return new Date(iso).toLocaleString()
}

function apiErrorMessage(error: unknown): string {
  const axiosErr = error as AxiosError<{ detail?: string }>
  return axiosErr?.response?.data?.detail ?? 'An unexpected error occurred.'
}

export default function TeamM2MClient({
  teamId,
  teamName,
  onClose,
}: TeamM2MClientProps) {
  const { data: oauthClient, isLoading } = useTeamOAuthClient(teamId)
  const registerClient = useRegisterOAuthClient()
  const updateClient = useUpdateOAuthClient(teamId)
  const deleteClient = useDeleteOAuthClient(teamId)

  // Register form state
  const [showRegisterForm, setShowRegisterForm] = useState(false)
  const [clientIdInput, setClientIdInput] = useState('')
  const [descriptionInput, setDescriptionInput] = useState('')

  // Delete confirmation state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    const payload: OAuthClientCreate = {
      client_id: clientIdInput.trim(),
      team_id: teamId,
      description: descriptionInput.trim() || undefined,
    }
    try {
      await registerClient.mutateAsync(payload)
      setShowRegisterForm(false)
      setClientIdInput('')
      setDescriptionInput('')
    } catch {
      // error displayed inline
    }
  }

  const handleToggleActive = async () => {
    if (!oauthClient) return
    try {
      await updateClient.mutateAsync({
        clientRecordId: oauthClient.id,
        data: { is_active: !oauthClient.is_active },
      })
    } catch {
      // error displayed inline
    }
  }

  const handleDelete = async () => {
    if (!oauthClient) return
    try {
      await deleteClient.mutateAsync(oauthClient.id)
      setShowDeleteConfirm(false)
    } catch {
      // error displayed inline
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">M2M Client</h2>
            <p className="text-sm text-gray-500 mt-1">{teamName}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-500">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Explainer */}
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-md text-sm text-blue-800">
          <p className="font-medium mb-1">About M2M clients</p>
          <p>
            Each team has exactly one machine member — the Auth0 M2M application
            provisioned by terraform for this team. Registering its{' '}
            <code className="font-mono bg-blue-100 px-1 rounded">client_id</code>{' '}
            here is required before the team can use M2M provisioning. Without a
            registered client, all M2M tokens for this team are rejected.
          </p>
          <p className="mt-2">
            The{' '}
            <code className="font-mono bg-blue-100 px-1 rounded">client_id</code>{' '}
            must match the <strong>Client ID</strong> of the Auth0 M2M application
            whose <code className="font-mono bg-blue-100 px-1 rounded">client_metadata.team</code>{' '}
            equals <strong>{teamName}</strong>.
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gh-blue" />
          </div>
        ) : oauthClient ? (
          /* ---- Registered client view ---- */
          <div className="space-y-4">
            <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <tbody className="divide-y divide-gray-100">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase w-36">
                      Client ID
                    </th>
                    <td className="px-4 py-3 font-mono text-sm text-gray-900 break-all">
                      {oauthClient.client_id}
                    </td>
                  </tr>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Status
                    </th>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          oauthClient.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                        }`}
                      >
                        {oauthClient.is_active ? 'Active' : 'Disabled'}
                      </span>
                      {!oauthClient.is_active && (
                        <span className="ml-2 text-xs text-red-600">
                          M2M provisioning is blocked for this team.
                        </span>
                      )}
                    </td>
                  </tr>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Description
                    </th>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {oauthClient.description ?? <span className="text-gray-400 italic">None</span>}
                    </td>
                  </tr>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Registered by
                    </th>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {oauthClient.created_by ?? <span className="text-gray-400 italic">Unknown</span>}
                    </td>
                  </tr>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Registered at
                    </th>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {formatDate(oauthClient.created_at)}
                    </td>
                  </tr>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Last used
                    </th>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      {formatDate(oauthClient.last_used_at)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Mutation errors */}
            {updateClient.isError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
                {apiErrorMessage(updateClient.error)}
              </div>
            )}
            {deleteClient.isError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
                {apiErrorMessage(deleteClient.error)}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-3 pt-2">
              <button
                onClick={handleToggleActive}
                disabled={updateClient.isPending}
                className={`inline-flex items-center px-4 py-2 border rounded-md text-sm font-medium focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 ${
                  oauthClient.is_active
                    ? 'border-yellow-300 text-yellow-700 bg-yellow-50 hover:bg-yellow-100 focus:ring-yellow-500'
                    : 'border-green-300 text-green-700 bg-green-50 hover:bg-green-100 focus:ring-green-500'
                }`}
              >
                {updateClient.isPending
                  ? 'Saving…'
                  : oauthClient.is_active
                  ? 'Disable client'
                  : 'Enable client'}
              </button>
              <button
                onClick={() => setShowDeleteConfirm(true)}
                disabled={deleteClient.isPending}
                className="inline-flex items-center px-4 py-2 border border-red-300 rounded-md text-sm font-medium text-red-700 bg-white hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
              >
                Delete registration
              </button>
            </div>

            {/* Delete confirm dialog */}
            {showDeleteConfirm && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-800 font-medium mb-1">
                  Delete M2M client registration?
                </p>
                <p className="text-sm text-red-700 mb-4">
                  This removes the registration record. The Auth0 M2M application
                  in terraform is <strong>not</strong> affected. After deletion,
                  all M2M tokens for team <strong>{teamName}</strong> will be
                  rejected until a new client is registered.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={handleDelete}
                    disabled={deleteClient.isPending}
                    className="px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 disabled:opacity-50"
                  >
                    {deleteClient.isPending ? 'Deleting…' : 'Confirm delete'}
                  </button>
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          /* ---- No client registered ---- */
          <div>
            <div className="p-4 bg-yellow-50 border border-yellow-300 rounded-md flex gap-3 mb-6">
              <svg className="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <div className="text-sm text-yellow-800">
                <p className="font-medium">No M2M client registered</p>
                <p className="mt-1">
                  This team has no registered machine member. All M2M tokens
                  for team <strong>{teamName}</strong> are currently rejected.
                  Register the Auth0 client ID below to enable M2M provisioning.
                </p>
              </div>
            </div>

            {!showRegisterForm ? (
              <button
                onClick={() => setShowRegisterForm(true)}
                className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gh-blue hover:bg-gh-blue-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gh-blue"
              >
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                Register M2M client
              </button>
            ) : (
              <form onSubmit={handleRegister} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Auth0 Client ID <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={clientIdInput}
                    onChange={(e) => setClientIdInput(e.target.value)}
                    placeholder="e.g. aBcDeFgHiJkLmNoPqRsT1234"
                    className="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 font-mono text-sm focus:outline-none focus:ring-gh-blue focus:border-gh-blue"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Found in the Auth0 dashboard under the M2M application for this team.
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description (optional)
                  </label>
                  <input
                    type="text"
                    value={descriptionInput}
                    onChange={(e) => setDescriptionInput(e.target.value)}
                    placeholder="e.g. CI/CD pipeline for platform-team"
                    className="block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 text-sm focus:outline-none focus:ring-gh-blue focus:border-gh-blue"
                  />
                </div>

                {registerClient.isError && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
                    {apiErrorMessage(registerClient.error)}
                  </div>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    type="submit"
                    disabled={registerClient.isPending || !clientIdInput.trim()}
                    className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gh-blue hover:bg-gh-blue-dark disabled:opacity-50"
                  >
                    {registerClient.isPending ? 'Registering…' : 'Register'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowRegisterForm(false)
                      setClientIdInput('')
                      setDescriptionInput('')
                    }}
                    className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
