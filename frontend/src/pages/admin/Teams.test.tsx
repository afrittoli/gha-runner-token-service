import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Teams from './Teams'

// Mock the useOAuthClients hook (Teams page imports TeamM2MClient which uses it)
vi.mock('@hooks/useOAuthClients', () => ({
  useTeamOAuthClient: vi.fn(() => ({ data: null, isLoading: false })),
  useRegisterOAuthClient: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false, isError: false })),
  useUpdateOAuthClient: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false, isError: false })),
  useDeleteOAuthClient: vi.fn(() => ({ mutateAsync: vi.fn(), isPending: false, isError: false })),
}))

// Mock the useTeams hook
vi.mock('@hooks/useTeams', () => ({
  useTeams: vi.fn(() => ({
    data: {
      teams: [
        {
          id: 'team-1',
          name: 'Engineering',
          description: 'Engineering team',
          required_labels: ['linux', 'docker'],
          optional_label_patterns: ['custom-.*'],
          max_runners: 10,
          is_active: true,
          member_count: 5,
          runner_count: 3,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
        {
          id: 'team-2',
          name: 'QA',
          description: 'Quality Assurance',
          required_labels: ['test'],
          optional_label_patterns: [],
          max_runners: null,
          is_active: false,
          member_count: 2,
          runner_count: 0,
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ],
      total: 2,
    },
    isLoading: false,
  })),
  useCreateTeam: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
  useDeactivateTeam: vi.fn(() => ({
    mutateAsync: vi.fn(),
  })),
  useReactivateTeam: vi.fn(() => ({
    mutateAsync: vi.fn(),
  })),
  useUpdateTeam: vi.fn(() => ({
    mutateAsync: vi.fn(),
    isPending: false,
  })),
}))

describe('Teams', () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

  const renderTeams = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <Teams />
      </QueryClientProvider>
    )
  }

  it('renders teams list', async () => {
    renderTeams()

    await waitFor(() => {
      expect(screen.getByText('Teams')).toBeInTheDocument()
      expect(screen.getByText('Engineering')).toBeInTheDocument()
      expect(screen.getByText('QA')).toBeInTheDocument()
    })
  })

  it('displays team details correctly', async () => {
    renderTeams()

    await waitFor(() => {
      // Check Engineering team
      expect(screen.getByText('Engineering')).toBeInTheDocument()
      expect(screen.getByText('Engineering team')).toBeInTheDocument()
      expect(screen.getByText('linux')).toBeInTheDocument()
      expect(screen.getByText('docker')).toBeInTheDocument()
      expect(screen.getByText('10')).toBeInTheDocument()
      expect(screen.getByText('5')).toBeInTheDocument()

      // Check QA team
      expect(screen.getByText('QA')).toBeInTheDocument()
      expect(screen.getByText('Quality Assurance')).toBeInTheDocument()
      expect(screen.getByText('test')).toBeInTheDocument()
      expect(screen.getByText('Unlimited')).toBeInTheDocument()
    })
  })

  it('displays team status badges', async () => {
    renderTeams()

    await waitFor(() => {
      const activeBadges = screen.getAllByText('Active')
      const inactiveBadges = screen.getAllByText('Inactive')
      
      expect(activeBadges.length).toBeGreaterThan(0)
      expect(inactiveBadges.length).toBeGreaterThan(0)
    })
  })

  it('shows create team button', async () => {
    renderTeams()

    await waitFor(() => {
      expect(screen.getByText('Create Team')).toBeInTheDocument()
    })
  })

  it('shows deactivate option in actions menu for active teams', async () => {
    const user = userEvent.setup()
    renderTeams()

    await waitFor(() => expect(screen.getByText('Engineering')).toBeInTheDocument())
    // Open the ⋮ menu for the first (active) team row
    const moreButtons = screen.getAllByRole('button', { name: /more actions/i })
    await user.click(moreButtons[0])
    expect(screen.getByRole('menuitem', { name: /deactivate/i })).toBeInTheDocument()
  })

  it('opens create team modal when Create Team button is clicked', async () => {
    const user = userEvent.setup()
    renderTeams()

    await waitFor(() => expect(screen.getByText('Create Team')).toBeInTheDocument())
    await user.click(screen.getByText('Create Team'))

    expect(screen.getByText('Create New Team')).toBeInTheDocument()
    expect(screen.getByText('Team Name')).toBeInTheDocument()
  })

  it('closes create team modal when Cancel is clicked', async () => {
    const user = userEvent.setup()
    renderTeams()

    await waitFor(() => expect(screen.getByText('Create Team')).toBeInTheDocument())
    await user.click(screen.getByText('Create Team'))
    expect(screen.getByText('Create New Team')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(screen.queryByText('Create New Team')).not.toBeInTheDocument()
  })

  it('opens edit modal when Edit icon button is clicked for an active team', async () => {
    const user = userEvent.setup()
    renderTeams()

    await waitFor(() => expect(screen.getByText('Engineering')).toBeInTheDocument())
    const editButtons = screen.getAllByRole('button', { name: /edit team/i })
    await user.click(editButtons[0])

    expect(screen.getByText(/Edit Team:/)).toBeInTheDocument()
    expect(screen.getByDisplayValue('Engineering team')).toBeInTheDocument()
  })

  it('calls updateTeam when edit form is submitted', async () => {
    const user = userEvent.setup()
    const mockUpdate = vi.fn().mockResolvedValue(undefined)
    const { useUpdateTeam } = await import('@hooks/useTeams')
    vi.mocked(useUpdateTeam).mockReturnValue({ mutateAsync: mockUpdate, isPending: false } as any)

    renderTeams()

    await waitFor(() => expect(screen.getByText('Engineering')).toBeInTheDocument())
    const editButtons = screen.getAllByRole('button', { name: /edit team/i })
    await user.click(editButtons[0])

    // Change description
    const descInput = screen.getByDisplayValue('Engineering team')
    await user.clear(descInput)
    await user.type(descInput, 'Updated description')

    await user.click(screen.getByRole('button', { name: /save changes/i }))

    await waitFor(() => expect(mockUpdate).toHaveBeenCalled())
  })

  it('closes edit modal when Cancel is clicked', async () => {
    const user = userEvent.setup()
    renderTeams()

    await waitFor(() => expect(screen.getByText('Engineering')).toBeInTheDocument())
    const editButtons = screen.getAllByRole('button', { name: /edit team/i })
    await user.click(editButtons[0])
    expect(screen.getByText(/Edit Team:/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /cancel/i }))
    expect(screen.queryByText(/Edit Team:/)).not.toBeInTheDocument()
  })

  it('shows M2M Client icon button for each team', async () => {
    renderTeams()

    await waitFor(() => {
      const m2mButtons = screen.getAllByRole('button', { name: /manage m2m client/i })
      expect(m2mButtons.length).toBeGreaterThan(0)
    })
  })

  it('opens M2M Client panel when M2M Client icon button is clicked', async () => {
    const user = userEvent.setup()
    renderTeams()

    await waitFor(() => expect(screen.getByText('Engineering')).toBeInTheDocument())
    const m2mButtons = screen.getAllByRole('button', { name: /manage m2m client/i })
    await user.click(m2mButtons[0])

    // Verify the M2M Client panel opened
    expect(screen.getByText('About M2M clients')).toBeInTheDocument()
  })
})

