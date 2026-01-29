import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Teams from './Teams'

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

  it('shows deactivate button for active teams', async () => {
    renderTeams()

    await waitFor(() => {
      const deactivateButtons = screen.getAllByText('Deactivate')
      expect(deactivateButtons.length).toBeGreaterThan(0)
    })
  })
})

// Made with Bob
