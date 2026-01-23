import { useQuery } from '@tanstack/react-query'
import { apiClient, DashboardStats } from '@api/client'

export function useDashboardStats() {
  return useQuery<DashboardStats>({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      const response = await apiClient.get('/api/v1/dashboard/stats')
      return response.data
    },
    // Refetch stats every 60 seconds by default
    refetchInterval: 60_000,
  })
}
