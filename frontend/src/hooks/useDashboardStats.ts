import { useQuery } from '@tanstack/react-query'
import { apiClient, DashboardStats } from '@api/client'

export function useDashboardStats() {
  return useQuery<DashboardStats>({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/dashboard/stats')
      return response.data
    },
    // Aggressive polling for demo: refetch every 5 seconds
    refetchInterval: 5000,
    refetchIntervalInBackground: false, // Only when tab is active
  })
}
