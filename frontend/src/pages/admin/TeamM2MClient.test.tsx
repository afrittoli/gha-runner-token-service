import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import TeamM2MClient from './TeamM2MClient'
import * as useOAuthClientsHooks from '@hooks/useOAuthClients'

vi.mock('@hooks/useOAuthClients')

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

const mockActiveClient = {
  id: 'rec-uuid-1',
  client_id: 'pipeline@clients',
  team_id: 'team-1',
  description: 'CI/CD pipeline',
  is_active: true,
  created_at: '2024-01-15T10:00:00Z',
  created_by: 'admin@example.com',
  last_used_at: '2024-02-01T08:30:00Z',
}

const mockDisabledClient = {
  ...mockActiveClient,
  is_active: false,
  last_used_at: null,
}

const defaultProps = {
  teamId: 'team-1',
  teamName: 'Engineering',
  onClose: vi.fn(),
}

describe('TeamM2MClient', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Default: no client registered
    vi.mocked(useOAuthClientsHooks.useTeamOAuthClient).mockReturnValue({
      data: null,
      isLoading: false,
    } as any)
    vi.mocked(useOAuthClientsHooks.useRegisterOAuthClient).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
    } as any)
    vi.mocked(useOAuthClientsHooks.useUpdateOAuthClient).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
    } as any)
    vi.mocked(useOAuthClientsHooks.useDeleteOAuthClient).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
    } as any)
  })

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  describe('Loading state', () => {
    it('shows a loading spinner while fetching', () => {
      vi.mocked(useOAuthClientsHooks.useTeamOAuthClient).mockReturnValue({
        data: undefined,
        isLoading: true,
      } as any)

      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })

      const spinner = document.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })

  // -------------------------------------------------------------------------
  // No client registered
  // -------------------------------------------------------------------------

  describe('No client registered', () => {
    it('shows the team name in the header', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      // teamName appears multiple times in the component; verify at least one instance
      const matches = screen.getAllByText('Engineering')
      expect(matches.length).toBeGreaterThan(0)
    })

    it('shows a warning that no M2M client is registered', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByText('No M2M client registered')).toBeInTheDocument()
    })

    it('shows the Register M2M client button', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByText('Register M2M client')).toBeInTheDocument()
    })

    it('shows the registration form when Register M2M client is clicked', async () => {
      const user = userEvent.setup()
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })

      await user.click(screen.getByText('Register M2M client'))

      expect(screen.getByText('Auth0 Client ID')).toBeInTheDocument()
      expect(screen.getByPlaceholderText(/aBcDeFgHiJkLmNoPqRsT1234/)).toBeInTheDocument()
    })

    it('cancels registration form when Cancel is clicked', async () => {
      const user = userEvent.setup()
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })

      await user.click(screen.getByText('Register M2M client'))
      expect(screen.getByText('Auth0 Client ID')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: /cancel/i }))
      expect(screen.queryByText('Auth0 Client ID')).not.toBeInTheDocument()
    })

    it('calls registerClient.mutateAsync on form submit', async () => {
      const user = userEvent.setup()
      const mockRegister = vi.fn().mockResolvedValue(mockActiveClient)
      vi.mocked(useOAuthClientsHooks.useRegisterOAuthClient).mockReturnValue({
        mutateAsync: mockRegister,
        isPending: false,
        isError: false,
        error: null,
      } as any)

      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })

      await user.click(screen.getByText('Register M2M client'))

      const clientIdInput = screen.getByPlaceholderText(/aBcDeFgHiJkLmNoPqRsT1234/)
      await user.type(clientIdInput, 'my-client@clients')

      await user.click(screen.getByRole('button', { name: /^Register$/i }))

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith({
          client_id: 'my-client@clients',
          team_id: 'team-1',
          description: undefined,
        })
      })
    })

    it('keeps Register button disabled when client_id is empty', async () => {
      const user = userEvent.setup()
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })

      await user.click(screen.getByText('Register M2M client'))

      const registerBtn = screen.getByRole('button', { name: /^Register$/i })
      expect(registerBtn).toBeDisabled()
    })

    it('calls onClose when the close button is clicked', async () => {
      const user = userEvent.setup()
      const onClose = vi.fn()
      render(<TeamM2MClient {...defaultProps} onClose={onClose} />, {
        wrapper: createWrapper(),
      })

      // The close button contains an SVG, no accessible name — select by position
      const closeBtn = document.querySelector('button.text-gray-400')
      await user.click(closeBtn!)

      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  // -------------------------------------------------------------------------
  // Active client registered
  // -------------------------------------------------------------------------

  describe('Active client registered', () => {
    beforeEach(() => {
      vi.mocked(useOAuthClientsHooks.useTeamOAuthClient).mockReturnValue({
        data: mockActiveClient,
        isLoading: false,
      } as any)
    })

    it('shows the client_id', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByText('pipeline@clients')).toBeInTheDocument()
    })

    it('shows Active status badge', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByText('Active')).toBeInTheDocument()
    })

    it('shows the description', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByText('CI/CD pipeline')).toBeInTheDocument()
    })

    it('shows the registered_by field', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByText('admin@example.com')).toBeInTheDocument()
    })

    it('shows Disable client button for an active client', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByRole('button', { name: /disable client/i })).toBeInTheDocument()
    })

    it('calls updateClient when Disable client is clicked', async () => {
      const user = userEvent.setup()
      const mockUpdate = vi.fn().mockResolvedValue({ ...mockActiveClient, is_active: false })
      vi.mocked(useOAuthClientsHooks.useUpdateOAuthClient).mockReturnValue({
        mutateAsync: mockUpdate,
        isPending: false,
        isError: false,
        error: null,
      } as any)

      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })

      await user.click(screen.getByRole('button', { name: /disable client/i }))

      await waitFor(() => {
        expect(mockUpdate).toHaveBeenCalledWith({
          clientRecordId: 'rec-uuid-1',
          data: { is_active: false },
        })
      })
    })

    it('shows Delete registration button', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByRole('button', { name: /delete registration/i })).toBeInTheDocument()
    })

    it('shows delete confirmation dialog when Delete registration is clicked', async () => {
      const user = userEvent.setup()
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })

      await user.click(screen.getByRole('button', { name: /delete registration/i }))

      expect(screen.getByText('Delete M2M client registration?')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /confirm delete/i })).toBeInTheDocument()
    })

    it('cancels delete when Cancel is clicked in confirmation dialog', async () => {
      const user = userEvent.setup()
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })

      await user.click(screen.getByRole('button', { name: /delete registration/i }))
      expect(screen.getByText('Delete M2M client registration?')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: /^cancel$/i }))
      expect(screen.queryByText('Delete M2M client registration?')).not.toBeInTheDocument()
    })

    it('calls deleteClient when Confirm delete is clicked', async () => {
      const user = userEvent.setup()
      const mockDelete = vi.fn().mockResolvedValue(undefined)
      vi.mocked(useOAuthClientsHooks.useDeleteOAuthClient).mockReturnValue({
        mutateAsync: mockDelete,
        isPending: false,
        isError: false,
        error: null,
      } as any)

      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })

      await user.click(screen.getByRole('button', { name: /delete registration/i }))
      await user.click(screen.getByRole('button', { name: /confirm delete/i }))

      await waitFor(() => {
        expect(mockDelete).toHaveBeenCalledWith('rec-uuid-1')
      })
    })
  })

  // -------------------------------------------------------------------------
  // Disabled client registered
  // -------------------------------------------------------------------------

  describe('Disabled client registered', () => {
    beforeEach(() => {
      vi.mocked(useOAuthClientsHooks.useTeamOAuthClient).mockReturnValue({
        data: mockDisabledClient,
        isLoading: false,
      } as any)
    })

    it('shows Disabled status badge', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByText('Disabled')).toBeInTheDocument()
    })

    it('shows M2M provisioning blocked warning', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByText(/M2M provisioning is blocked/)).toBeInTheDocument()
    })

    it('shows Enable client button for a disabled client', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByRole('button', { name: /enable client/i })).toBeInTheDocument()
    })

    it('shows Never for last_used_at when null', () => {
      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })
      expect(screen.getByText('Never')).toBeInTheDocument()
    })

    it('calls updateClient with is_active=true when Enable client is clicked', async () => {
      const user = userEvent.setup()
      const mockUpdate = vi.fn().mockResolvedValue(mockActiveClient)
      vi.mocked(useOAuthClientsHooks.useUpdateOAuthClient).mockReturnValue({
        mutateAsync: mockUpdate,
        isPending: false,
        isError: false,
        error: null,
      } as any)

      render(<TeamM2MClient {...defaultProps} />, { wrapper: createWrapper() })

      await user.click(screen.getByRole('button', { name: /enable client/i }))

      await waitFor(() => {
        expect(mockUpdate).toHaveBeenCalledWith({
          clientRecordId: 'rec-uuid-1',
          data: { is_active: true },
        })
      })
    })
  })
})
