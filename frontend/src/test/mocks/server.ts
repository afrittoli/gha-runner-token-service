import { setupServer } from 'msw/node'
import { beforeAll, afterEach, afterAll } from 'vitest'
import { handlers } from './handlers'

/**
 * Setup MSW server for Node.js environment (tests)
 * This intercepts HTTP requests during tests and returns mocked responses
 */
export const server = setupServer(...handlers)

/**
 * Start server before all tests
 */
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'warn' })
})

/**
 * Reset handlers after each test to ensure test isolation
 */
afterEach(() => {
  server.resetHandlers()
})

/**
 * Clean up after all tests
 */
afterAll(() => {
  server.close()
})

// Made with Bob
