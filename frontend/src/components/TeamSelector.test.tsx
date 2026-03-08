import { describe, it, expect, vi } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import { renderWithProviders } from '../test/utils'
import TeamSelector from './TeamSelector'
import { TeamSummary } from '@api/client'

const TEAMS: TeamSummary[] = [
  { id: 'id-1', name: 'platform-team' },
  { id: 'id-2', name: 'infra' },
]

describe('TeamSelector', () => {
  it('renders "All My Teams" as first option', () => {
    const onChange = vi.fn()
    renderWithProviders(
      <TeamSelector teams={TEAMS} selectedTeam={undefined} onChange={onChange} />
    )
    const select = screen.getByRole('combobox', { name: /filter by team/i })
    const options = Array.from(select.querySelectorAll('option'))
    expect(options[0].textContent).toBe('All My Teams')
    expect(options[0].value).toBe('')
  })

  it('renders one option per team', () => {
    renderWithProviders(
      <TeamSelector teams={TEAMS} selectedTeam={undefined} onChange={vi.fn()} />
    )
    expect(screen.getByRole('option', { name: 'platform-team' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'infra' })).toBeInTheDocument()
  })

  it('reflects the selectedTeam prop', () => {
    renderWithProviders(
      <TeamSelector teams={TEAMS} selectedTeam="infra" onChange={vi.fn()} />
    )
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe('infra')
  })

  it('calls onChange with team name when a team is selected', () => {
    const onChange = vi.fn()
    renderWithProviders(
      <TeamSelector teams={TEAMS} selectedTeam={undefined} onChange={onChange} />
    )
    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: 'platform-team' },
    })
    expect(onChange).toHaveBeenCalledWith('platform-team')
  })

  it('calls onChange with undefined when "All My Teams" is selected', () => {
    const onChange = vi.fn()
    renderWithProviders(
      <TeamSelector teams={TEAMS} selectedTeam="platform-team" onChange={onChange} />
    )
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '' } })
    expect(onChange).toHaveBeenCalledWith(undefined)
  })

  it('renders with an empty teams array', () => {
    renderWithProviders(
      <TeamSelector teams={[]} selectedTeam={undefined} onChange={vi.fn()} />
    )
    const select = screen.getByRole('combobox')
    const options = Array.from(select.querySelectorAll('option'))
    // Only the "All My Teams" option
    expect(options).toHaveLength(1)
  })
})
