import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import TeamMembers from './TeamMembers'
import * as useTeamsHooks from '@hooks/useTeams'

// Mock the hooks
vi.mock('@hooks/useTeams')
vi.mock('@hooks/useAdmin', () => ({
  useUsers: vi.fn(() => ({
    data: {
      users: [
        { id: 'user-3', email: 'charlie@example.com', display_name: 'Charlie', is_active: true },
      ],
    },
    isLoading: false,
  })),
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

const mockMembers = {
  members: [
    {
      user_id: 'user-1',
      email: 'alice@example.com',
      display_name: 'Alice Smith',      joined_at: '2024-01-01T00:00:00Z',
    },
    {
      user_id: 'user-2',
      email: 'bob@example.com',
      display_name: null,      joined_at: '2024-01-02T00:00:00Z',
    },
  ],
  total: 2,
}

describe('TeamMembers', () => {
  const mockOnClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Loading State', () => {
    it('should show loading spinner while fetching members', () => {
      vi.mocked(useTeamsHooks.useTeamMembers).mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
        refetch: vi.fn(),
      } as any)

      render(
        <TeamMembers teamId="team-1" teamName="Test Team" onClose={mockOnClose} />,
        { wrapper: createWrapper() }
      )

      // Check for loading spinner by class name
      const spinner = document.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })

  describe('Members List', () => {
    beforeEach(() => {
      vi.mocked(useTeamsHooks.useTeamMembers).mockReturnValue({
        data: mockMembers,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useTeamsHooks.useAddTeamMember).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: false,
        isError: false,
      } as any)

      vi.mocked(useTeamsHooks.useRemoveTeamMember).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: false,
      } as any)    })

    it('should display team name in header', () => {
      render(
        <TeamMembers teamId="team-1" teamName="Test Team" onClose={mockOnClose} />,
        { wrapper: createWrapper() }
      )

      expect(screen.getByText('Test Team')).toBeInTheDocument()
    })

    it('should display all team members', () => {
      render(
        <TeamMembers teamId="team-1" teamName="Test Team" onClose={mockOnClose} />,
        { wrapper: createWrapper() }
      )

      expect(screen.getByText('Alice Smith')).toBeInTheDocument()
      expect(screen.getByText('alice@example.com')).toBeInTheDocument()
      expect(screen.getByText('bob@example.com')).toBeInTheDocument()
    })

    it('should call onClose when close button is clicked', async () => {
      const user = userEvent.setup()

      render(
        <TeamMembers teamId="team-1" teamName="Test Team" onClose={mockOnClose} />,
        { wrapper: createWrapper() }
      )

      const closeButton = screen.getByRole('button', { name: '' })
      await user.click(closeButton)

      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })
  })

  describe('Empty State', () => {
    it('should show empty state when no members', () => {
      vi.mocked(useTeamsHooks.useTeamMembers).mockReturnValue({
        data: { members: [], total: 0 },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useTeamsHooks.useAddTeamMember).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: false,
        isError: false,
      } as any)

      vi.mocked(useTeamsHooks.useRemoveTeamMember).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: false,
      } as any)
      render(
        <TeamMembers teamId="team-1" teamName="Test Team" onClose={mockOnClose} />,
        { wrapper: createWrapper() }
      )

      expect(screen.getByText('No members')).toBeInTheDocument()
      expect(screen.getByText(/get started by adding a member/i)).toBeInTheDocument()
    })
  })

  describe('Add Member', () => {
    it('should open add member modal when button is clicked', async () => {
      const user = userEvent.setup()

      vi.mocked(useTeamsHooks.useTeamMembers).mockReturnValue({
        data: mockMembers,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useTeamsHooks.useAddTeamMember).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: false,
        isError: false,
      } as any)

      vi.mocked(useTeamsHooks.useRemoveTeamMember).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: false,
      } as any)
      render(
        <TeamMembers teamId="team-1" teamName="Test Team" onClose={mockOnClose} />,
        { wrapper: createWrapper() }
      )

      const addButton = screen.getByRole('button', { name: /add member/i })
      await user.click(addButton)

      expect(screen.getByText('Add Team Member')).toBeInTheDocument()
      expect(screen.getByRole('combobox', { name: /user/i })).toBeInTheDocument()
    })

    it('should add member when form is submitted', async () => {
      const user = userEvent.setup()
      const mockAddMember = vi.fn().mockResolvedValue(undefined)

      vi.mocked(useTeamsHooks.useTeamMembers).mockReturnValue({
        data: mockMembers,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useTeamsHooks.useAddTeamMember).mockReturnValue({
        mutateAsync: mockAddMember,
        isPending: false,
        isError: false,
      } as any)

      vi.mocked(useTeamsHooks.useRemoveTeamMember).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: false,
      } as any)
      render(
        <TeamMembers teamId="team-1" teamName="Test Team" onClose={mockOnClose} />,
        { wrapper: createWrapper() }
      )

      // Open modal
      const addButton = screen.getByRole('button', { name: /add member/i })
      await user.click(addButton)

      // Select user from dropdown
      const userSelect = screen.getByRole('combobox', { name: /user/i })
      await user.selectOptions(userSelect, 'user-3')

      // Submit - get the second "Add Member" button (the one in the modal form)
      const addMemberButtons = screen.getAllByRole('button', { name: /add member/i })
      await user.click(addMemberButtons[1])

      await waitFor(() => {
        expect(mockAddMember).toHaveBeenCalledWith({
          user_id: 'user-3',
        })
      })
    })
  })

  describe('Remove Member', () => {
    it('should remove member when confirmed', async () => {
      const user = userEvent.setup()
      const mockRemoveMember = vi.fn().mockResolvedValue(undefined)

      // Mock window.confirm
      vi.stubGlobal('confirm', vi.fn(() => true))

      vi.mocked(useTeamsHooks.useTeamMembers).mockReturnValue({
        data: mockMembers,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useTeamsHooks.useAddTeamMember).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: false,
        isError: false,
      } as any)

      vi.mocked(useTeamsHooks.useRemoveTeamMember).mockReturnValue({
        mutateAsync: mockRemoveMember,
        isPending: false,
      } as any)
      render(
        <TeamMembers teamId="team-1" teamName="Test Team" onClose={mockOnClose} />,
        { wrapper: createWrapper() }
      )

      // Open the ⋮ menu for the first row, then click Remove
      const moreButtons = screen.getAllByRole('button', { name: /more actions/i })
      await user.click(moreButtons[0])
      const removeItem = screen.getByRole('menuitem', { name: /remove/i })
      await user.click(removeItem)

      await waitFor(() => {
        expect(mockRemoveMember).toHaveBeenCalledWith('user-1')
      })

      vi.unstubAllGlobals()
    })

    it('should not remove member when cancelled', async () => {
      const user = userEvent.setup()
      const mockRemoveMember = vi.fn()

      // Mock window.confirm to return false
      vi.stubGlobal('confirm', vi.fn(() => false))

      vi.mocked(useTeamsHooks.useTeamMembers).mockReturnValue({
        data: mockMembers,
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      } as any)

      vi.mocked(useTeamsHooks.useAddTeamMember).mockReturnValue({
        mutateAsync: vi.fn(),
        isPending: false,
        isError: false,
      } as any)

      vi.mocked(useTeamsHooks.useRemoveTeamMember).mockReturnValue({
        mutateAsync: mockRemoveMember,
        isPending: false,
      } as any)
      render(
        <TeamMembers teamId="team-1" teamName="Test Team" onClose={mockOnClose} />,
        { wrapper: createWrapper() }
      )

      // Open the ⋮ menu for the first row, then click Remove
      const moreButtons = screen.getAllByRole('button', { name: /more actions/i })
      await user.click(moreButtons[0])
      const removeItem = screen.getByRole('menuitem', { name: /remove/i })
      await user.click(removeItem)

      expect(mockRemoveMember).not.toHaveBeenCalled()

      vi.unstubAllGlobals()
    })
  })

})
