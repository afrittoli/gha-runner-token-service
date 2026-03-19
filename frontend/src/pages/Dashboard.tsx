import { Link } from 'react-router-dom'
import { useRunners } from '@hooks/useRunners'

export default function Dashboard() {
  const { data: runnersData, isLoading, error } = useRunners({ limit: 1000 })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card p-6 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-20 mb-2"></div>
              <div className="h-8 bg-gray-200 rounded w-12"></div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="card p-6 text-red-600">
          Failed to load runners. Please try again.
        </div>
      </div>
    )
  }

  const runners = runnersData?.runners || []
  const statCards = [
    {
      name: 'Total Runners',
      value: runnersData?.total || 0,
      color: 'bg-blue-500',
    },
    {
      name: 'Active',
      value: runners.filter((r) => r.status === 'active').length,
      color: 'bg-green-500',
    },
    {
      name: 'Offline',
      value: runners.filter((r) => r.status === 'offline').length,
      color: 'bg-gray-500',
    },
    {
      name: 'Pending',
      value: runners.filter((r) => r.status === 'pending').length,
      color: 'bg-yellow-500',
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <div className="flex space-x-3">
          <Link to="/runners/provision" className="btn btn-primary">
            Provision Runner
          </Link>
          <Link to="/runners" className="btn btn-secondary">
            View All Runners
          </Link>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <div key={stat.name} className="card p-6">
            <div className="flex items-center">
              <div className={`w-3 h-3 rounded-full ${stat.color} mr-3`}></div>
              <span className="text-sm font-medium text-gray-500">
                {stat.name}
              </span>
            </div>
            <p className="mt-2 text-3xl font-semibold text-gray-900">
              {stat.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
