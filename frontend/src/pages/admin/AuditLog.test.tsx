import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import AuditLogPage from './AuditLog'
import * as useAdminHooks from '@hooks/useAdmin'

// Mock the hooks
vi.mock('@hooks/useAdmin')

const mockAuditLogs = [
  {
    id: 1,
    event_type: 'provision_runner',
    runner_id: 'runner-123',
    runner_name: 'test-runner-1',
    user_identity: 'alice@example.com',
    oidc_sub: 'sub-alice',
    request_ip: '192.168.1.1',
    user_agent: 'Mozilla/5.0',
    event_data: {
      labels: ['linux', 'docker'],
      ephemeral: true,
    },
    success: true,
    error_message: null,
    timestamp: '2024-01-15T10:30:00Z',
  },
  {
    id: 2,
    event_type: 'deprovision_runner',
    runner_id: 'runner-456',
    runner_name: 'test-runner-2',
    user_identity: 'bob@example.com',
    oidc_sub: 'sub-bob',
    request_ip: '192.168.1.2',
    user_agent: 'Mozilla/5.0',
    event_data: {
      reason: 'No longer needed',
    },
    success: true,
    error_message: null,
    timestamp: '2024-01-15T11:00:00Z',
  },
  {
    id: 3,
    event_type: 'create_label_policy',
    runner_id: null,
    runner_name: null,
    user_identity: 'admin@example.com',
    oidc_sub: 'sub-admin',
    request_ip: '192.168.1.3',
    user_agent: 'Mozilla/5.0',
    event_data: {
      user_identity: 'charlie@example.com',
      allowed_labels: ['linux', 'arm64'],
      max_runners: 3,
    },
    success: false,
    error_message: 'Validation failed: max_runners must be positive',
    timestamp: '2024-01-15T12:00:00Z',
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

describe('AuditLog', () => {
  const mockUseAuditLogs = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAdminHooks.useAuditLogs).mockImplementation(mockUseAuditLogs)
  })

  it('renders loading state', () => {
    mockUseAuditLogs.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    })

    const { container } = renderWithProviders(<AuditLogPage />)
    
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
  })

  it('renders error state', () => {
    mockUseAuditLogs.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Failed to load logs'),
    })

    renderWithProviders(<AuditLogPage />)
    
    expect(screen.getByText(/error loading audit logs/i)).toBeInTheDocument()
    expect(screen.getByText(/failed to load logs/i)).toBeInTheDocument()
  })

  it('renders empty state when no logs exist', () => {
    mockUseAuditLogs.mockReturnValue({
      data: { logs: [], total: 0 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<AuditLogPage />)
    
    expect(screen.getByText(/no audit logs found/i)).toBeInTheDocument()
  })

  it('renders list of audit logs', () => {
    mockUseAuditLogs.mockReturnValue({
      data: { logs: mockAuditLogs, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<AuditLogPage />)
    
    expect(screen.getByText('provision_runner')).toBeInTheDocument()
    expect(screen.getByText('deprovision_runner')).toBeInTheDocument()
    expect(screen.getByText('create_label_policy')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText('bob@example.com')).toBeInTheDocument()
    expect(screen.getByText('admin@example.com')).toBeInTheDocument()
  })

  it('displays success and failed status badges', () => {
    mockUseAuditLogs.mockReturnValue({
      data: { logs: mockAuditLogs, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<AuditLogPage />)
    
    const successBadges = screen.getAllByText('Success')
    const failedBadges = screen.getAllByText('Failed')
    
    expect(successBadges).toHaveLength(2)
    expect(failedBadges).toHaveLength(1)
    
    // Check colors
    expect(successBadges[0]).toHaveClass('bg-green-100', 'text-green-800')
    expect(failedBadges[0]).toHaveClass('bg-red-100', 'text-red-800')
  })

  it('filters logs by event type', async () => {
    const user = userEvent.setup()
    let capturedFilters: any = {}
    
    mockUseAuditLogs.mockImplementation((filters) => {
      capturedFilters = filters
      return {
        data: { logs: mockAuditLogs, total: 3 },
        isLoading: false,
        error: null,
      }
    })

    renderWithProviders(<AuditLogPage />)
    
    const selects = screen.getAllByRole('combobox')
    const eventTypeSelect = selects[0]
    await user.selectOptions(eventTypeSelect, 'provision_runner')
    
    await waitFor(() => {
      expect(capturedFilters.event_type).toBe('provision_runner')
      expect(capturedFilters.offset).toBe(0)
    })
  })

  it('searches by user identity', async () => {
    const user = userEvent.setup()
    let capturedFilters: any = {}
    
    mockUseAuditLogs.mockImplementation((filters) => {
      capturedFilters = filters
      return {
        data: { logs: mockAuditLogs, total: 3 },
        isLoading: false,
        error: null,
      }
    })

    renderWithProviders(<AuditLogPage />)
    
    const searchInput = screen.getByPlaceholderText(/search by user/i)
    const searchButton = screen.getByRole('button', { name: /search/i })
    
    await user.type(searchInput, 'alice@example.com')
    await user.click(searchButton)
    
    await waitFor(() => {
      expect(capturedFilters.user_identity).toBe('alice@example.com')
      expect(capturedFilters.offset).toBe(0)
    })
  })

  it('searches by user identity on Enter key', async () => {
    const user = userEvent.setup()
    let capturedFilters: any = {}
    
    mockUseAuditLogs.mockImplementation((filters) => {
      capturedFilters = filters
      return {
        data: { logs: mockAuditLogs, total: 3 },
        isLoading: false,
        error: null,
      }
    })

    renderWithProviders(<AuditLogPage />)
    
    const searchInput = screen.getByPlaceholderText(/search by user/i)
    
    await user.type(searchInput, 'bob@example.com{Enter}')
    
    await waitFor(() => {
      expect(capturedFilters.user_identity).toBe('bob@example.com')
    })
  })

  it('clears all filters when Clear Filters is clicked', async () => {
    const user = userEvent.setup()
    let capturedFilters: any = {}
    
    mockUseAuditLogs.mockImplementation((filters) => {
      capturedFilters = filters
      return {
        data: { logs: mockAuditLogs, total: 3 },
        isLoading: false,
        error: null,
      }
    })

    renderWithProviders(<AuditLogPage />)
    
    // Set some filters
    const selects = screen.getAllByRole('combobox')
    const eventTypeSelect = selects[0]
    await user.selectOptions(eventTypeSelect, 'provision_runner')
    
    const searchInput = screen.getByPlaceholderText(/search by user/i)
    await user.type(searchInput, 'alice@example.com')
    
    // Clear filters
    const clearButton = screen.getByRole('button', { name: /clear filters/i })
    await user.click(clearButton)
    
    await waitFor(() => {
      expect(capturedFilters.event_type).toBeUndefined()
      expect(capturedFilters.user_identity).toBeUndefined()
      expect(capturedFilters.limit).toBe(50)
      expect(capturedFilters.offset).toBe(0)
    })
    
    expect(searchInput).toHaveValue('')
  })

  it('opens detail modal when Details button is clicked', async () => {
    const user = userEvent.setup()
    
    mockUseAuditLogs.mockReturnValue({
      data: { logs: mockAuditLogs, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<AuditLogPage />)
    
    const detailsButtons = screen.getAllByRole('button', { name: /details/i })
    await user.click(detailsButtons[0])
    
    await waitFor(() => {
      expect(screen.getByText(/event details: provision_runner/i)).toBeInTheDocument()
      expect(screen.getByText('192.168.1.1')).toBeInTheDocument()
    })
  })

  it('closes detail modal when close button is clicked', async () => {
    const user = userEvent.setup()
    
    mockUseAuditLogs.mockReturnValue({
      data: { logs: mockAuditLogs, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<AuditLogPage />)
    
    // Open modal
    const detailsButtons = screen.getAllByRole('button', { name: /details/i })
    await user.click(detailsButtons[0])
    
    // Close modal
    const closeButtons = screen.getAllByRole('button', { name: /close/i })
    await user.click(closeButtons[0])
    
    await waitFor(() => {
      expect(screen.queryByText(/event details:/i)).not.toBeInTheDocument()
    })
  })

  it('displays event data in modal', async () => {
    const user = userEvent.setup()
    
    mockUseAuditLogs.mockReturnValue({
      data: { logs: mockAuditLogs, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<AuditLogPage />)
    
    const detailsButtons = screen.getAllByRole('button', { name: /details/i })
    await user.click(detailsButtons[0])
    
    await waitFor(() => {
      const modal = screen.getByRole('dialog')
      expect(within(modal).getByText(/"labels"/i)).toBeInTheDocument()
      expect(within(modal).getByText(/"ephemeral"/i)).toBeInTheDocument()
    })
  })

  it('displays error message in modal for failed events', async () => {
    const user = userEvent.setup()
    
    mockUseAuditLogs.mockReturnValue({
      data: { logs: mockAuditLogs, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<AuditLogPage />)
    
    // Click on the failed event (third one)
    const detailsButtons = screen.getAllByRole('button', { name: /details/i })
    await user.click(detailsButtons[2])
    
    await waitFor(() => {
      expect(screen.getByText(/validation failed: max_runners must be positive/i)).toBeInTheDocument()
    })
  })

  it('displays runner name or dash when null', () => {
    mockUseAuditLogs.mockReturnValue({
      data: { logs: mockAuditLogs, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<AuditLogPage />)
    
    expect(screen.getByText('test-runner-1')).toBeInTheDocument()
    expect(screen.getByText('test-runner-2')).toBeInTheDocument()
    
    // Find the row with admin@example.com and check for dash
    const rows = screen.getAllByRole('row')
    const adminRow = rows.find(row => row.textContent?.includes('admin@example.com'))
    expect(adminRow?.textContent).toContain('-')
  })

  it('formats event data to hide empty arrays', async () => {
    const user = userEvent.setup()
    
    const logWithEmptyArrays = {
      ...mockAuditLogs[0],
      event_data: {
        labels: ['linux'],
        empty_field: [],
        another_empty: [],
      },
    }
    
    mockUseAuditLogs.mockReturnValue({
      data: { logs: [logWithEmptyArrays], total: 1 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<AuditLogPage />)
    
    const detailsButtons = screen.getAllByRole('button', { name: /details/i })
    await user.click(detailsButtons[0])
    
    await waitFor(() => {
      const modal = screen.getByRole('dialog')
      const eventDataText = within(modal).getByText(/"labels"/i).textContent || ''
      
      // Should include labels
      expect(eventDataText).toContain('labels')
      // Should NOT include empty_field or another_empty
      expect(eventDataText).not.toContain('empty_field')
      expect(eventDataText).not.toContain('another_empty')
    })
  })
})

// Made with Bob
