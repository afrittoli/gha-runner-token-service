/**
 * Format a date string into a user-friendly format.
 */
export function formatDate(dateString: string | undefined): string {
  if (!dateString) return 'Never'
  const date = new Date(dateString)
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

/**
 * Get CSS classes for status badges based on runner status.
 */
export function getStatusBadgeClass(status: string | undefined): string {
  switch (status) {
    case 'active':
    case 'online':
      return 'bg-green-100 text-green-800 border-green-200'
    case 'offline':
      return 'bg-gray-100 text-gray-800 border-gray-200'
    case 'pending':
      return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    case 'deleted':
      return 'bg-red-100 text-red-800 border-red-200'
    default:
      return 'bg-blue-100 text-blue-800 border-blue-200'
  }
}
