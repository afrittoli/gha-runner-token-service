import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { AxiosError } from 'axios'
import { useProvisionRunnerJit } from '@hooks/useRunners'
import { copyToClipboard } from '@utils/clipboard'

export default function ProvisionRunner() {
  const navigate = useNavigate()
  const provisionMutation = useProvisionRunnerJit()
  
  const [namePrefix, setNamePrefix] = useState('')
  const [labels, setLabels] = useState('')
  const [copySuccess, setCopySuccess] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    const labelList = labels
      .split(',')
      .map(l => l.trim())
      .filter(l => l !== '')

    provisionMutation.mutate({
      runner_name_prefix: namePrefix || undefined,
      labels: labelList,
    })
  }

  const handleCopy = async (text: string, type: string) => {
    const success = await copyToClipboard(text)
    if (success) {
      setCopySuccess(type)
      setTimeout(() => setCopySuccess(null), 2000)
    }
  }

  if (provisionMutation.isSuccess) {
    const data = provisionMutation.data
    return (
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="card p-8 text-center space-y-4">
          <div className="mx-auto flex items-center justify-center h-12 w-12 rounded-full bg-green-100">
            <svg className="h-6 w-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Runner Provisioned Successfully!</h1>
          <p className="text-gray-600">
            Your runner <strong>{data.runner_name}</strong> has been pre-registered using JIT configuration. 
            Use the command below to start it on your machine.
          </p>
        </div>

        <div className="card divide-y divide-gray-200">
          <div className="p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">JIT Configuration</h2>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                Always Ephemeral
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <code className="flex-1 block p-3 bg-gray-100 rounded border border-gray-200 text-sm font-mono break-all line-clamp-3">
                {data.encoded_jit_config}
              </code>
              <button
                onClick={() => handleCopy(data.encoded_jit_config, 'token')}
                className="btn btn-secondary py-3 h-fit"
              >
                {copySuccess === 'token' ? 'Copied!' : 'Copy'}
              </button>
            </div>
            <p className="text-xs text-yellow-600 font-medium">
              Warning: This configuration is valid for 1 hour and will only be shown once.
            </p>
          </div>

          <div className="p-6 space-y-4">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">Run Command</h2>
            <div className="flex items-center space-x-2">
              <code className="flex-1 block p-3 bg-gray-900 text-gray-100 rounded text-sm font-mono break-all">
                {data.run_command}
              </code>
              <button
                onClick={() => handleCopy(data.run_command, 'command')}
                className="btn btn-secondary py-3 h-fit"
              >
                {copySuccess === 'command' ? 'Copied!' : 'Copy'}
              </button>
            </div>
          </div>

          <div className="p-6 space-y-4">
            <h2 className="text-sm font-semibold text-gray-900 uppercase tracking-wider">Assigned Labels</h2>
            <div className="flex flex-wrap gap-2">
              {data.labels.map((label: string) => (
                <span key={label} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800 border border-gray-200">
                  {label}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="flex justify-center space-x-4">
          <Link to="/runners" className="btn btn-secondary">
            Back to Runners
          </Link>
          <button 
            onClick={() => provisionMutation.reset()} 
            className="btn btn-primary"
          >
            Provision Another
          </button>
        </div>
      </div>
    )
  }

  const error = provisionMutation.error as AxiosError<{ detail?: string }>

  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Provision JIT Runner</h1>
        <p className="text-gray-600">Enter the details below to generate a Just-In-Time configuration.</p>
      </div>

      <form onSubmit={handleSubmit} className="card p-6 space-y-6">
        {provisionMutation.isError && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-md text-red-600 text-sm">
            Failed to provision runner: {error?.response?.data?.detail || provisionMutation.error.message}
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="namePrefix" className="block text-sm font-medium text-gray-700">
            Runner Name Prefix
          </label>
          <input
            id="namePrefix"
            type="text"
            placeholder="e.g. dev-runner"
            value={namePrefix}
            onChange={(e) => setNamePrefix(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-gh-blue focus:border-transparent outline-none"
          />
          <p className="text-xs text-gray-500">
            A unique suffix will be added automatically.
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="labels" className="block text-sm font-medium text-gray-700">
            Custom Labels (comma separated)
          </label>
          <input
            id="labels"
            type="text"
            placeholder="e.g. gpu, high-mem"
            value={labels}
            onChange={(e) => setLabels(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-gh-blue focus:border-transparent outline-none"
          />
          <p className="text-xs text-gray-500">
            System labels (self-hosted, OS, architecture) are added automatically.
          </p>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">Security Note</h3>
              <div className="mt-2 text-sm text-blue-700">
                <p>
                  With JIT provisioning, labels are enforced server-side, runners are always ephemeral and no long-lived tokens are issued.
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="pt-4 flex items-center justify-end space-x-4">
          <button
            type="button"
            onClick={() => navigate('/runners')}
            className="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={provisionMutation.isPending}
            className="btn btn-primary"
          >
            {provisionMutation.isPending ? 'Provisioning...' : 'Provision JIT Runner'}
          </button>
        </div>
      </form>
    </div>
  )
}
