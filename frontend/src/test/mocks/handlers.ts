import { http, HttpResponse } from 'msw'

const API_BASE = '/api/v1'

/**
 * Mock data for testing
 */
export const mockUser = {
  user_id: 'test-user-123',
  oidc_sub: 'github|12345',
  is_admin: false,
  roles: ['user'],
}

export const mockAdminUser = {
  user_id: 'admin-user-456',
  oidc_sub: 'github|67890',
  is_admin: true,
  roles: ['admin', 'user'],
}

export const mockRunner = {
  id: 'runner-1',
  name: 'test-runner-1',
  status: 'online',
  labels: ['linux', 'x64'],
  ephemeral: false,
  provisioned_by: 'test-user-123',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  registered_at: '2024-01-01T00:00:00Z',
  last_seen: '2024-01-01T00:00:00Z',
  github_id: 123,
}

export const mockDashboardStats = {
  total_runners: 10,
  active_runners: 7,
  offline_runners: 2,
  pending_runners: 1,
  recent_events: [
    {
      id: 'event-1',
      event_type: 'runner_provisioned',
      user_identity: 'test-user-123',
      timestamp: '2024-01-01T00:00:00Z',
      details: { runner_name: 'test-runner-1' },
    },
  ],
}

/**
 * MSW request handlers for API mocking
 */
export const handlers = [
  // Auth endpoints
  http.get(`${API_BASE}/auth/me`, () => {
    return HttpResponse.json(mockUser)
  }),

  // Dashboard stats
  http.get(`${API_BASE}/dashboard/stats`, () => {
    return HttpResponse.json(mockDashboardStats)
  }),

  // Runners endpoints
  http.get(`${API_BASE}/runners`, ({ request }) => {
    const url = new URL(request.url)
    const limit = parseInt(url.searchParams.get('limit') || '10')
    const offset = parseInt(url.searchParams.get('offset') || '0')

    return HttpResponse.json({
      runners: [mockRunner],
      total: 1,
      limit,
      offset,
    })
  }),

  http.get(`${API_BASE}/runners/:id`, ({ params }) => {
    return HttpResponse.json({
      ...mockRunner,
      id: params.id,
    })
  }),

  http.post(`${API_BASE}/runners`, async ({ request }) => {
    const body = await request.json()
    return HttpResponse.json(
      {
        runner: {
          ...mockRunner,
          name: (body as any).name,
          labels: (body as any).labels,
        },
        token: 'mock-registration-token-12345',
        expires_at: '2024-01-01T01:00:00Z',
      },
      { status: 201 }
    )
  }),

  http.delete(`${API_BASE}/runners/:id`, () => {
    return HttpResponse.json({ message: 'Runner deprovisioned' })
  }),

  // Admin endpoints
  http.get(`${API_BASE}/admin/users`, () => {
    return HttpResponse.json({
      users: [mockUser, mockAdminUser],
      total: 2,
    })
  }),

  http.get(`${API_BASE}/admin/label-policies`, () => {
    return HttpResponse.json({
      policies: [
        {
          user_identity: 'test-user-123',
          allowed_labels: ['linux', 'x64'],
          label_patterns: [],
          max_runners: 5,
          require_approval: false,
          description: 'Test policy',
          created_by: 'admin-user-456',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ],
    })
  }),

  http.get(`${API_BASE}/admin/security-events`, () => {
    return HttpResponse.json({
      events: [
        {
          id: 'sec-event-1',
          event_type: 'unauthorized_access',
          user_identity: 'test-user-123',
          severity: 'medium',
          timestamp: '2024-01-01T00:00:00Z',
          details: { reason: 'Invalid token' },
        },
      ],
      total: 1,
    })
  }),

  http.get(`${API_BASE}/admin/audit-log`, () => {
    return HttpResponse.json({
      events: [
        {
          id: 'audit-1',
          event_type: 'runner_provisioned',
          user_identity: 'test-user-123',
          timestamp: '2024-01-01T00:00:00Z',
          details: { runner_name: 'test-runner-1' },
        },
      ],
      total: 1,
    })
  }),
]

/**
 * Error handlers for testing error states
 */
export const errorHandlers = [
  http.get(`${API_BASE}/auth/me`, () => {
    return HttpResponse.json(
      { detail: 'Unauthorized' },
      { status: 401 }
    )
  }),

  http.get(`${API_BASE}/runners`, () => {
    return HttpResponse.json(
      { detail: 'Internal server error' },
      { status: 500 }
    )
  }),
]

// Made with Bob
