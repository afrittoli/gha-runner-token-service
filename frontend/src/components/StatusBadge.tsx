import { getStatusBadgeClass } from '@utils/formatters'

interface StatusBadgeProps {
  status: string | undefined
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`px-2 py-0.5 text-xs font-semibold rounded-full border ${getStatusBadgeClass(status)}`}>
      {status || 'unknown'}
    </span>
  )
}
