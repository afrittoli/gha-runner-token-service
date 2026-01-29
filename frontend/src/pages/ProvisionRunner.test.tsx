import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import ProvisionRunner from './ProvisionRunner'
import * as useRunnersHooks from '@hooks/useRunners'
import * as useTeamsHooks from '@hooks/useTeams'

// Mock the hooks
vi.mock('@hooks/useRunners')
vi.mock('@hooks/useTeams')
vi.mock('@utils/clipboard', () => ({
  copyToClipboard: vi.fn().mockResolvedValue(true),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  )
}

describe('ProvisionRunner', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Team Selection', () => {
    it('should show team selection dropdown when teams exist', () => {
      const mockTeams = {
        teams: [
          {
            id: 'team-1',
            name: 'Backend Team',
            description: 'Backend services',
            is_active: true,
            required_labels: ['linux'],
            optional_label_patterns: [],
            max_runners: 10,
            member_count: 5,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
          {
            id: 'team-2',
            name: 'Frontend Team',
            description: 'Frontend apps',
            is_active: true,
            required_labels: ['node'],
            optional_label_patterns: [],
            max_runners: 5,
            member_count: 3,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
        ],
      }

      vi.mocked(useTeamsHooks.useTeams).mockReturnValue({
        data: mockTeams,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useProvisionRunnerJit).mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
        isSuccess: false,
        isError: false,
        error: null,
        data: undefined,
        reset: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useMyLabelPolicy).mockReturnValue({
        data: null,
        isLoading: false,
      } as any)

      render(<ProvisionRunner />, { wrapper: createWrapper() })

      expect(screen.getByLabelText(/team/i)).toBeInTheDocument()
      expect(screen.getByText('Backend Team - Backend services')).toBeInTheDocument()
      expect(screen.getByText('Frontend Team - Frontend apps')).toBeInTheDocument()
    })

    it('should not show team selection when no teams exist', () => {
      vi.mocked(useTeamsHooks.useTeams).mockReturnValue({
        data: { teams: [] },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useProvisionRunnerJit).mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
        isSuccess: false,
        isError: false,
        error: null,
        data: undefined,
        reset: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useMyLabelPolicy).mockReturnValue({
        data: null,
        isLoading: false,
      } as any)

      render(<ProvisionRunner />, { wrapper: createWrapper() })

      expect(screen.queryByLabelText(/team/i)).not.toBeInTheDocument()
    })

    it('should filter out inactive teams from dropdown', () => {
      const mockTeams = {
        teams: [
          {
            id: 'team-1',
            name: 'Active Team',
            description: '',
            is_active: true,
            required_labels: [],
            optional_label_patterns: [],
            max_runners: null,
            member_count: 0,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
          {
            id: 'team-2',
            name: 'Inactive Team',
            description: '',
            is_active: false,
            required_labels: [],
            optional_label_patterns: [],
            max_runners: null,
            member_count: 0,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
        ],
      }

      vi.mocked(useTeamsHooks.useTeams).mockReturnValue({
        data: mockTeams,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useProvisionRunnerJit).mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
        isSuccess: false,
        isError: false,
        error: null,
        data: undefined,
        reset: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useMyLabelPolicy).mockReturnValue({
        data: null,
        isLoading: false,
      } as any)

      render(<ProvisionRunner />, { wrapper: createWrapper() })

      expect(screen.getByText('Active Team')).toBeInTheDocument()
      expect(screen.queryByText('Inactive Team')).not.toBeInTheDocument()
    })
  })

  describe('Form Submission with Teams', () => {
    it('should include team_id when provisioning with team selected', async () => {
      const user = userEvent.setup()
      const mockMutate = vi.fn()

      const mockTeams = {
        teams: [
          {
            id: 'team-1',
            name: 'Test Team',
            description: '',
            is_active: true,
            required_labels: [],
            optional_label_patterns: [],
            max_runners: null,
            member_count: 0,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
        ],
      }

      vi.mocked(useTeamsHooks.useTeams).mockReturnValue({
        data: mockTeams,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useProvisionRunnerJit).mockReturnValue({
        mutate: mockMutate,
        isPending: false,
        isSuccess: false,
        isError: false,
        error: null,
        data: undefined,
        reset: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useMyLabelPolicy).mockReturnValue({
        data: null,
        isLoading: false,
      } as any)

      render(<ProvisionRunner />, { wrapper: createWrapper() })

      // Select team
      const teamSelect = screen.getByLabelText(/team/i)
      await user.selectOptions(teamSelect, 'team-1')

      // Fill in labels
      const labelsInput = screen.getByLabelText(/custom labels/i)
      await user.type(labelsInput, 'gpu, high-mem')

      // Submit form
      const submitButton = screen.getByRole('button', { name: /provision jit runner/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockMutate).toHaveBeenCalledWith({
          runner_name_prefix: undefined,
          labels: ['gpu', 'high-mem'],
          team_id: 'team-1',
        })
      })
    })

    it('should require team selection when teams exist', async () => {
      const user = userEvent.setup()
      const mockMutate = vi.fn()

      const mockTeams = {
        teams: [
          {
            id: 'team-1',
            name: 'Test Team',
            description: '',
            is_active: true,
            required_labels: [],
            optional_label_patterns: [],
            max_runners: null,
            member_count: 0,
            created_at: '2024-01-01T00:00:00Z',
            updated_at: '2024-01-01T00:00:00Z',
          },
        ],
      }

      vi.mocked(useTeamsHooks.useTeams).mockReturnValue({
        data: mockTeams,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useProvisionRunnerJit).mockReturnValue({
        mutate: mockMutate,
        isPending: false,
        isSuccess: false,
        isError: false,
        error: null,
        data: undefined,
        reset: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useMyLabelPolicy).mockReturnValue({
        data: null,
        isLoading: false,
      } as any)

      render(<ProvisionRunner />, { wrapper: createWrapper() })

      // Try to submit without selecting team
      const submitButton = screen.getByRole('button', { name: /provision jit runner/i })
      await user.click(submitButton)

      // Form should not submit (HTML5 validation)
      expect(mockMutate).not.toHaveBeenCalled()
    })

    it('should not include team_id when no teams exist', async () => {
      const user = userEvent.setup()
      const mockMutate = vi.fn()

      vi.mocked(useTeamsHooks.useTeams).mockReturnValue({
        data: { teams: [] },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useProvisionRunnerJit).mockReturnValue({
        mutate: mockMutate,
        isPending: false,
        isSuccess: false,
        isError: false,
        error: null,
        data: undefined,
        reset: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useMyLabelPolicy).mockReturnValue({
        data: null,
        isLoading: false,
      } as any)

      render(<ProvisionRunner />, { wrapper: createWrapper() })

      // Fill in labels
      const labelsInput = screen.getByLabelText(/custom labels/i)
      await user.type(labelsInput, 'test')

      // Submit form
      const submitButton = screen.getByRole('button', { name: /provision jit runner/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockMutate).toHaveBeenCalledWith({
          runner_name_prefix: undefined,
          labels: ['test'],
          team_id: undefined,
        })
      })
    })
  })

  describe('Success State', () => {
    it('should display success message with runner details', () => {
      const mockSuccessData = {
        runner_name: 'test-runner-abc123',
        encoded_jit_config: 'base64encodedconfig==',
        run_command: './run.sh --jitconfig base64encodedconfig==',
        labels: ['self-hosted', 'linux', 'x64', 'gpu'],
      }

      vi.mocked(useTeamsHooks.useTeams).mockReturnValue({
        data: { teams: [] },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useProvisionRunnerJit).mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
        isSuccess: true,
        isError: false,
        error: null,
        data: mockSuccessData,
        reset: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useMyLabelPolicy).mockReturnValue({
        data: null,
        isLoading: false,
      } as any)

      render(<ProvisionRunner />, { wrapper: createWrapper() })

      expect(screen.getByText(/runner provisioned successfully/i)).toBeInTheDocument()
      expect(screen.getByText('test-runner-abc123')).toBeInTheDocument()
      expect(screen.getByText('base64encodedconfig==')).toBeInTheDocument()
      expect(screen.getByText(/self-hosted/)).toBeInTheDocument()
      expect(screen.getByText(/gpu/)).toBeInTheDocument()
    })
  })

  describe('Error Handling', () => {
    it('should display error message on provision failure', () => {
      const mockError = {
        response: {
          data: {
            detail: 'Team quota exceeded',
          },
        },
        message: 'Request failed',
      }

      vi.mocked(useTeamsHooks.useTeams).mockReturnValue({
        data: { teams: [] },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useProvisionRunnerJit).mockReturnValue({
        mutate: vi.fn(),
        isPending: false,
        isSuccess: false,
        isError: true,
        error: mockError,
        data: undefined,
        reset: vi.fn(),
      } as any)

      vi.mocked(useRunnersHooks.useMyLabelPolicy).mockReturnValue({
        data: null,
        isLoading: false,
      } as any)

      render(<ProvisionRunner />, { wrapper: createWrapper() })

      expect(screen.getByText(/failed to provision runner/i)).toBeInTheDocument()
      expect(screen.getByText(/team quota exceeded/i)).toBeInTheDocument()
    })
  })
})

// Made with Bob
