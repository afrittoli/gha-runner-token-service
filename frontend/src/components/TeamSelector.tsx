import { TeamSummary } from '@api/client'

interface TeamSelectorProps {
  /** Teams the current user belongs to. */
  teams: TeamSummary[]
  /** Currently selected team name, or undefined for "all teams". */
  selectedTeam: string | undefined
  /** Called when the user selects a team or "All Teams". */
  onChange: (teamName: string | undefined) => void
}

/**
 * TeamSelector — a drop-down that lets the user filter the runner list to a
 * specific team. Renders as a simple `<select>` consistent with the existing
 * status filter in `RunnersList`.
 *
 * Shows "All My Teams" as the default option, then one option per team.
 * When the user has only one team, the selector is still shown (for
 * discoverability) but pre-selects that team automatically.
 */
export default function TeamSelector({
  teams,
  selectedTeam,
  onChange,
}: TeamSelectorProps) {
  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value
    onChange(value === '' ? undefined : value)
  }

  return (
    <select
      value={selectedTeam ?? ''}
      onChange={handleChange}
      className="px-4 py-2 border border-gray-300 rounded-md
                 focus:outline-none focus:ring-2 focus:ring-gh-blue"
      aria-label="Filter by team"
    >
      <option value="">All My Teams</option>
      {teams.map((team) => (
        <option key={team.id} value={team.name}>
          {team.name}
        </option>
      ))}
    </select>
  )
}
