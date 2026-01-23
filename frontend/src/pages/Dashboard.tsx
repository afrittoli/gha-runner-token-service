import { Link } from 'react-router-dom'
import { useDashboardStats } from '@hooks/useDashboardStats'

export default function Dashboard() {
  const { data: stats, isLoading, error } = useDashboardStats()

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
          Failed to load dashboard stats. Please try again.
        </div>
      </div>
    )
  }

  const statCards = [
    {
      name: 'Total Runners',
      value: stats?.total_runners || 0,
      color: 'bg-blue-500',
    },
    {
      name: 'Active',
      value: stats?.active_runners || 0,
      color: 'bg-green-500',
    },
    {
      name: 'Offline',
      value: stats?.offline_runners || 0,
      color: 'bg-gray-500',
    },
    {
      name: 'Pending',
      value: stats?.pending_runners || 0,
      color: 'bg-yellow-500',
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <Link to="/runners" className="btn btn-primary">
          View All Runners
        </Link>
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

      {/* Recent activity */}
      <div className="card">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium text-gray-900">Recent Activity</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {stats?.recent_events && stats.recent_events.length > 0 ? (
            stats.recent_events.slice(0, 10).map((event) => (
              <div key={event.id} className="px-6 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <span
                      className={`status-badge ${
                        event.severity === 'high'
                          ? 'bg-red-100 text-red-800'
                          : event.severity === 'medium'
                          ? 'bg-yellow-100 text-yellow-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}
                    >
                      {event.event_type}
                    </span>
                    <span className="ml-2 text-sm text-gray-500">
                      by {event.user_identity}
                    </span>
                  </div>
                  <span className="text-sm text-gray-400">
                    {new Date(event.timestamp).toLocaleString()}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="px-6 py-8 text-center text-gray-500">
              No recent activity
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
