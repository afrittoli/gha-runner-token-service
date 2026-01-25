import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import SecurityEvents from './SecurityEvents'
import * as useAdminHooks from '@hooks/useAdmin'

// Mock the hooks
vi.mock('@hooks/useAdmin')

const mockSecurityEvents = [
  {
    id: 1,
    event_type: 'label_violation',
    severity: 'high',
    user_identity: 'alice@example.com',
    runner_name: 'runner-1',
    timestamp: '2024-01-15T10:30:00Z',
    action_taken: 'Runner provisioning blocked',
    violation_data: {
      requested_labels: ['linux', 'gpu'],
      allowed_labels: ['linux', 'docker'],
      violated_labels: ['gpu'],
    },
  },
  {
    id: 2,
    event_type: 'quota_exceeded',
    severity: 'medium',
    user_identity: 'bob@example.com',
    runner_name: 'runner-2',
    timestamp: '2024-01-15T11:00:00Z',
    action_taken: 'Request denied',
    violation_data: {
      current_count: 5,
      max_allowed: 5,
    },
  },
  {
    id: 3,
    event_type: 'unauthorized_access',
    severity: 'critical',
    user_identity: 'charlie@example.com',
    runner_name: null,
    timestamp: '2024-01-15T12:00:00Z',
    action_taken: 'Access denied, logged',
    violation_data: {
      attempted_action: 'delete_runner',
      runner_owner: 'alice@example.com',
    },
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

describe('SecurityEvents', () => {
  const mockUseSecurityEvents = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useAdminHooks.useSecurityEvents).mockImplementation(mockUseSecurityEvents)
  })

  it('renders loading state', () => {
    mockUseSecurityEvents.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    })

    const { container } = renderWithProviders(<SecurityEvents />)
    
    const spinner = container.querySelector('.animate-spin')
    expect(spinner).toBeInTheDocument()
  })

  it('renders error state', () => {
    mockUseSecurityEvents.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Failed to load events'),
    })

    renderWithProviders(<SecurityEvents />)
    
    expect(screen.getByText(/error loading security events/i)).toBeInTheDocument()
    expect(screen.getByText(/failed to load events/i)).toBeInTheDocument()
  })

  it('renders empty state when no events exist', () => {
    mockUseSecurityEvents.mockReturnValue({
      data: { events: [], total: 0 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<SecurityEvents />)
    
    expect(screen.getByText(/no security events found/i)).toBeInTheDocument()
  })

  it('renders list of security events', () => {
    mockUseSecurityEvents.mockReturnValue({
      data: { events: mockSecurityEvents, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<SecurityEvents />)
    
    expect(screen.getByText('label_violation')).toBeInTheDocument()
    expect(screen.getByText('quota_exceeded')).toBeInTheDocument()
    expect(screen.getByText('unauthorized_access')).toBeInTheDocument()
    expect(screen.getByText('alice@example.com')).toBeInTheDocument()
    expect(screen.getByText('bob@example.com')).toBeInTheDocument()
    expect(screen.getByText('charlie@example.com')).toBeInTheDocument()
  })

  it('displays severity badges with correct colors', () => {
    mockUseSecurityEvents.mockReturnValue({
      data: { events: mockSecurityEvents, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<SecurityEvents />)
    
    const highBadge = screen.getByText('high')
    const mediumBadge = screen.getByText('medium')
    const criticalBadge = screen.getByText('critical')
    
    expect(highBadge).toHaveClass('bg-red-100', 'text-red-800')
    expect(mediumBadge).toHaveClass('bg-yellow-100', 'text-yellow-800')
    expect(criticalBadge).toHaveClass('bg-red-200', 'text-red-900', 'font-bold')
  })

  it('filters events by event type', async () => {
    const user = userEvent.setup()
    let capturedFilters: any = {}
    
    mockUseSecurityEvents.mockImplementation((filters) => {
      capturedFilters = filters
      return {
        data: { events: mockSecurityEvents, total: 3 },
        isLoading: false,
        error: null,
      }
    })

    renderWithProviders(<SecurityEvents />)
    
    // Get all comboboxes - first one is event type
    const selects = screen.getAllByRole('combobox')
    const eventTypeSelect = selects[0]
    await user.selectOptions(eventTypeSelect, 'label_violation')
    
    await waitFor(() => {
      expect(capturedFilters.event_type).toBe('label_violation')
      expect(capturedFilters.offset).toBe(0)
    })
  })

  it('filters events by severity', async () => {
    const user = userEvent.setup()
    let capturedFilters: any = {}
    
    mockUseSecurityEvents.mockImplementation((filters) => {
      capturedFilters = filters
      return {
        data: { events: mockSecurityEvents, total: 3 },
        isLoading: false,
        error: null,
      }
    })

    renderWithProviders(<SecurityEvents />)
    
    // Get all comboboxes - second one is severity
    const selects = screen.getAllByRole('combobox')
    const severitySelect = selects[1]
    await user.selectOptions(severitySelect, 'high')
    
    await waitFor(() => {
      expect(capturedFilters.severity).toBe('high')
      expect(capturedFilters.offset).toBe(0)
    })
  })

  it('searches by user identity', async () => {
    const user = userEvent.setup()
    let capturedFilters: any = {}
    
    mockUseSecurityEvents.mockImplementation((filters) => {
      capturedFilters = filters
      return {
        data: { events: mockSecurityEvents, total: 3 },
        isLoading: false,
        error: null,
      }
    })

    renderWithProviders(<SecurityEvents />)
    
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
    
    mockUseSecurityEvents.mockImplementation((filters) => {
      capturedFilters = filters
      return {
        data: { events: mockSecurityEvents, total: 3 },
        isLoading: false,
        error: null,
      }
    })

    renderWithProviders(<SecurityEvents />)
    
    const searchInput = screen.getByPlaceholderText(/search by user/i)
    
    await user.type(searchInput, 'bob@example.com{Enter}')
    
    await waitFor(() => {
      expect(capturedFilters.user_identity).toBe('bob@example.com')
    })
  })

  it('clears all filters when Clear Filters is clicked', async () => {
    const user = userEvent.setup()
    let capturedFilters: any = {}
    
    mockUseSecurityEvents.mockImplementation((filters) => {
      capturedFilters = filters
      return {
        data: { events: mockSecurityEvents, total: 3 },
        isLoading: false,
        error: null,
      }
    })

    renderWithProviders(<SecurityEvents />)
    
    // Set some filters
    const selects = screen.getAllByRole('combobox')
    const eventTypeSelect = selects[0]
    await user.selectOptions(eventTypeSelect, 'label_violation')
    
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
    
    mockUseSecurityEvents.mockReturnValue({
      data: { events: mockSecurityEvents, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<SecurityEvents />)
    
    const detailsButtons = screen.getAllByRole('button', { name: /details/i })
    await user.click(detailsButtons[0])
    
    await waitFor(() => {
      expect(screen.getByText('Security Event Details')).toBeInTheDocument()
      expect(screen.getByText('Runner provisioning blocked')).toBeInTheDocument()
      expect(screen.getByText(/"requested_labels"/i)).toBeInTheDocument()
    })
  })

  it('closes detail modal when close button is clicked', async () => {
    const user = userEvent.setup()
    
    mockUseSecurityEvents.mockReturnValue({
      data: { events: mockSecurityEvents, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<SecurityEvents />)
    
    // Open modal
    const detailsButtons = screen.getAllByRole('button', { name: /details/i })
    await user.click(detailsButtons[0])
    
    // Close modal
    const closeButtons = screen.getAllByRole('button', { name: /close/i })
    await user.click(closeButtons[0])
    
    await waitFor(() => {
      expect(screen.queryByText('Security Event Details')).not.toBeInTheDocument()
    })
  })

  it('displays violation data in modal', async () => {
    const user = userEvent.setup()
    
    mockUseSecurityEvents.mockReturnValue({
      data: { events: mockSecurityEvents, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<SecurityEvents />)
    
    const detailsButtons = screen.getAllByRole('button', { name: /details/i })
    await user.click(detailsButtons[0])
    
    await waitFor(() => {
      const modal = screen.getByRole('dialog')
      expect(within(modal).getByText(/"requested_labels"/i)).toBeInTheDocument()
      expect(within(modal).getByText(/"allowed_labels"/i)).toBeInTheDocument()
      expect(within(modal).getByText(/"violated_labels"/i)).toBeInTheDocument()
    })
  })

  it('displays runner name or dash when null', () => {
    mockUseSecurityEvents.mockReturnValue({
      data: { events: mockSecurityEvents, total: 3 },
      isLoading: false,
      error: null,
    })

    renderWithProviders(<SecurityEvents />)
    
    expect(screen.getByText('runner-1')).toBeInTheDocument()
    expect(screen.getByText('runner-2')).toBeInTheDocument()
    
    // Find the row with charlie@example.com and check for dash
    const rows = screen.getAllByRole('row')
    const charlieRow = rows.find(row => row.textContent?.includes('charlie@example.com'))
    expect(charlieRow?.textContent).toContain('-')
  })
})

// Made with Bob
