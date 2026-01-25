import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import LabelPolicies from './LabelPolicies'
import * as useAdminHooks from '@hooks/useAdmin'

// Mock the hooks
vi.mock('@hooks/useAdmin')

const mockPolicies = [
  {
    user_identity: 'alice@example.com',
    allowed_labels: ['linux', 'docker', 'x64'],
    label_patterns: null,
    max_runners: 5,
    require_approval: false,
    description: 'Team A development runners',
    created_by: 'admin@example.com',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-15T00:00:00Z',
  },
  {
    user_identity: 'bob@example.com',
    allowed_labels: ['linux', 'arm64'],
    label_patterns: null,
    max_runners: 3,
    require_approval: false,
    description: 'Team B runners',
    created_by: 'admin@example.com',
    created_at: '2024-01-02T00:00:00Z',
    updated_at: '2024-01-16T00:00:00Z',
  },
]

function renderWithProviders(component: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {component}
      </BrowserRouter>
    </QueryClientProvider>
  )
}

describe('LabelPolicies', () => {
  const mockUseLabelPolicies = vi.fn()
  const mockUseDeleteLabelPolicy = vi.fn()
  const mockUseCreateLabelPolicy = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    
    // Setup default mocks with proper return values
    vi.mocked(useAdminHooks.useLabelPolicies).mockImplementation(mockUseLabelPolicies)
    vi.mocked(useAdminHooks.useDeleteLabelPolicy).mockImplementation(mockUseDeleteLabelPolicy)
    vi.mocked(useAdminHooks.useCreateLabelPolicy).mockImplementation(mockUseCreateLabelPolicy)
    
    // Default mock implementations
    mockUseDeleteLabelPolicy.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as never)
    
    mockUseCreateLabelPolicy.mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    } as never)
  })

  it('renders loading state', () => {
    mockUseLabelPolicies.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    })

    const { container } = renderWithProviders(<LabelPolicies />)
    
    // Check for the loading spinner by its class
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
    expect(spinner).toHaveClass('rounded-full', 'h-8', 'w-8', 'border-b-2', 'border-gh-blue')
  })

  it('renders error state', () => {
    mockUseLabelPolicies.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Failed to load policies'),
    })

    renderWithProviders(<LabelPolicies />)
    
    expect(screen.getByText(/error loading label policies/i)).toBeInTheDocument()
    expect(screen.getByText(/failed to load policies/i)).toBeInTheDocument()
  })

  it('renders empty state when no policies exist', () => {
    mockUseLabelPolicies.mockReturnValue({
      data: { policies: [], total: 0 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<LabelPolicies />)
    
    expect(screen.getByText(/no label policies configured/i)).toBeInTheDocument()
  })

  it('renders list of policies', () => {
    mockUseLabelPolicies.mockReturnValue({
      data: { policies: mockPolicies, total: 2 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<LabelPolicies />)
    
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText('bob@example.com')).toBeInTheDocument()
    expect(screen.getByText('Team A development runners')).toBeInTheDocument()
    expect(screen.getByText('Team B runners')).toBeInTheDocument()
  })

  it('displays policy labels as pills', () => {
    mockUseLabelPolicies.mockReturnValue({
      data: { policies: mockPolicies, total: 2 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<LabelPolicies />)
    
    // Check for multiple instances of 'linux' (appears in both policies)
    const linuxLabels = screen.getAllByText('linux')
    expect(linuxLabels.length).toBeGreaterThan(0)
    expect(screen.getByText('docker')).toBeInTheDocument()
    expect(screen.getByText('x64')).toBeInTheDocument()
    expect(screen.getByText('arm64')).toBeInTheDocument()
  })

  it('shows add policy form when Add Policy button is clicked', async () => {
    const user = userEvent.setup()
    mockUseLabelPolicies.mockReturnValue({
      data: { policies: mockPolicies, total: 2 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<LabelPolicies />)
    
    const addButton = screen.getByRole('button', { name: /add policy/i })
    await user.click(addButton)
    
    expect(screen.getByText(/create new policy/i)).toBeInTheDocument()
    expect(screen.getByPlaceholderText('user@example.com')).toBeInTheDocument()
    expect(screen.getByDisplayValue('5')).toBeInTheDocument() // max runners default value
    expect(screen.getByPlaceholderText('linux, docker, x64')).toBeInTheDocument()
  })

  it('creates a new policy when form is submitted', async () => {
    const user = userEvent.setup()
    const mockMutateAsync = vi.fn().mockResolvedValue({})
    
    mockUseLabelPolicies.mockReturnValue({
      data: { policies: [], total: 0 },
      isLoading: false,
      error: null,
    })
    
    mockUseCreateLabelPolicy.mockReturnValue({
      mutateAsync: mockMutateAsync,
      isPending: false,
    })

    renderWithProviders(<LabelPolicies />)
    
    // Open form
    await user.click(screen.getByRole('button', { name: /add policy/i }))
    
    // Fill form using placeholders
    await user.type(screen.getByPlaceholderText('user@example.com'), 'charlie@example.com')
    const maxRunnersInput = screen.getByDisplayValue('5')
    await user.clear(maxRunnersInput)
    await user.type(maxRunnersInput, '10')
    await user.type(screen.getByPlaceholderText('linux, docker, x64'), 'linux, docker')
    await user.type(screen.getByPlaceholderText('Team A runners'), 'Test policy')
    
    // Submit
    await user.click(screen.getByRole('button', { name: /create policy/i }))
    
    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        user_identity: 'charlie@example.com',
        allowed_labels: ['linux', 'docker'],
        description: 'Test policy',
        max_runners: 10,
      })
    })
  })

  it('opens edit form with policy data when Edit is clicked', async () => {
    const user = userEvent.setup()
    mockUseLabelPolicies.mockReturnValue({
      data: { policies: mockPolicies, total: 2 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<LabelPolicies />)
    
    const editButtons = screen.getAllByRole('button', { name: /edit/i })
    await user.click(editButtons[0])
    
    expect(screen.getByText(/edit policy/i)).toBeInTheDocument()
    expect(screen.getByDisplayValue('alice@example.com')).toBeInTheDocument()
    expect(screen.getByDisplayValue('linux, docker, x64')).toBeInTheDocument()
    expect(screen.getByDisplayValue('5')).toBeInTheDocument()
  })

  it('disables user identity field when editing', async () => {
    const user = userEvent.setup()
    mockUseLabelPolicies.mockReturnValue({
      data: { policies: mockPolicies, total: 2 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<LabelPolicies />)
    
    const editButtons = screen.getAllByRole('button', { name: /edit/i })
    await user.click(editButtons[0])
    
    const userIdentityInput = screen.getByDisplayValue('alice@example.com')
    expect(userIdentityInput).toBeDisabled()
  })

  it('shows confirmation dialog when Delete is clicked', async () => {
    const user = userEvent.setup()
    const mockConfirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const mockMutateAsync = vi.fn().mockResolvedValue(undefined)
    
    mockUseLabelPolicies.mockReturnValue({
      data: { policies: mockPolicies, total: 2 },
      isLoading: false,
      error: null,
    })
    
    mockUseDeleteLabelPolicy.mockReturnValue({
      mutateAsync: mockMutateAsync,
    })

    renderWithProviders(<LabelPolicies />)
    
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteButtons[0])
    
    expect(mockConfirm).toHaveBeenCalledWith(
      expect.stringContaining('alice@example.com')
    )
    
    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith('alice@example.com')
    })
  })

  it('does not delete policy if confirmation is cancelled', async () => {
    const user = userEvent.setup()
    const mockConfirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const mockMutateAsync = vi.fn()
    
    mockUseLabelPolicies.mockReturnValue({
      data: { policies: mockPolicies, total: 2 },
      isLoading: false,
      error: null,
    })
    
    mockUseDeleteLabelPolicy.mockReturnValue({
      mutateAsync: mockMutateAsync,
    })

    renderWithProviders(<LabelPolicies />)
    
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i })
    await user.click(deleteButtons[0])
    
    expect(mockConfirm).toHaveBeenCalled()
    expect(mockMutateAsync).not.toHaveBeenCalled()
  })

  it('cancels form and resets state when Cancel is clicked', async () => {
    const user = userEvent.setup()
    mockUseLabelPolicies.mockReturnValue({
      data: { policies: mockPolicies, total: 2 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<LabelPolicies />)
    
    // Open form
    await user.click(screen.getByRole('button', { name: /add policy/i }))
    
    // Fill some data
    await user.type(screen.getByPlaceholderText('user@example.com'), 'test@example.com')
    
    // Cancel
    const cancelButtons = screen.getAllByRole('button', { name: /cancel/i })
    await user.click(cancelButtons[cancelButtons.length - 1]) // Click the form cancel button
    
    // Form should be hidden
    expect(screen.queryByText(/create new policy/i)).not.toBeInTheDocument()
    
    // Open again to verify reset
    await user.click(screen.getByRole('button', { name: /add policy/i }))
    expect(screen.getByPlaceholderText('user@example.com')).toHaveValue('')
  })
})

// Made with Bob
