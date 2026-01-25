# Frontend Testing Guide

## Overview

The frontend uses a modern testing stack with Vitest, React Testing Library, and MSW for comprehensive test coverage.

## Testing Stack

- **Vitest 4.0.18** - Fast test runner with native Vite integration
- **React Testing Library 16.3.2** - Component testing focused on user behavior
- **MSW 2.12.7** - API mocking at the network level
- **jsdom 27.4.0** - DOM environment for tests
- **@testing-library/jest-dom** - Custom matchers for DOM assertions

## Running Tests

```bash
# Run tests in watch mode (development)
npm test

# Run tests once (CI)
npm run test:run

# Run tests with coverage
npm run test:coverage

# Run tests with UI
npm run test:ui

# Type checking
npm run typecheck

# Linting
npm run lint
```

## Test Structure

```
frontend/
├── src/
│   ├── test/
│   │   ├── setup.ts              # Global test setup
│   │   ├── utils.tsx             # Test utilities (custom render)
│   │   └── mocks/
│   │       ├── handlers.ts       # MSW request handlers
│   │       └── server.ts         # MSW server setup
│   ├── components/
│   │   ├── StatusBadge.tsx
│   │   └── StatusBadge.test.tsx  # Component tests
│   ├── utils/
│   │   ├── formatters.ts
│   │   └── formatters.test.ts    # Utility tests
│   └── ...
└── vitest.config.ts              # Vitest configuration
```

## Writing Tests

### Component Tests

```typescript
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MyComponent from './MyComponent'

describe('MyComponent', () => {
  it('renders correctly', () => {
    render(<MyComponent />)
    expect(screen.getByText('Hello')).toBeInTheDocument()
  })
})
```

### Using Custom Render with Providers

```typescript
import { renderWithProviders } from '@/test/utils'

it('renders with React Query', () => {
  renderWithProviders(<MyComponent />)
  // Component has access to QueryClient and Router
})
```

### Testing with MSW

```typescript
import { server } from '@/test/mocks/server'
import { http, HttpResponse } from 'msw'

it('handles API errors', async () => {
  // Override default handler for this test
  server.use(
    http.get('/api/v1/runners', () => {
      return HttpResponse.json(
        { detail: 'Server error' },
        { status: 500 }
      )
    })
  )
  
  renderWithProviders(<RunnersList />)
  expect(await screen.findByText('Error loading runners')).toBeInTheDocument()
})
```

### User Interactions

```typescript
import { userEvent } from '@/test/utils'

it('handles button click', async () => {
  const user = userEvent.setup()
  render(<MyButton />)
  
  await user.click(screen.getByRole('button'))
  expect(screen.getByText('Clicked!')).toBeInTheDocument()
})
```

## Coverage Requirements

- **Overall**: 40% minimum (enforced in CI)
- **Target**: 60%+ for production readiness
- **Critical paths**: 90%+ recommended

### Checking Coverage

```bash
npm run test:coverage
```

Coverage reports are generated in `coverage/` directory:
- `coverage/index.html` - HTML report (open in browser)
- `coverage/lcov.info` - LCOV format for CI tools

## CI/CD Integration

### Pre-commit Hooks

Frontend tests run automatically on commit for changed files:
- ESLint
- TypeScript type checking
- Vitest tests

### GitHub Actions

The `.github/workflows/frontend.yml` workflow runs on:
- Push to main
- Pull requests
- Changes to `frontend/**` files

Jobs:
1. **Lint and Type Check** - ESLint + TypeScript
2. **Unit Tests** - Vitest with coverage threshold check
3. **Build** - Production bundle with size check

## Best Practices

### 1. Test User Behavior, Not Implementation

```typescript
// ❌ Bad - testing implementation details
expect(component.state.count).toBe(1)

// ✅ Good - testing user-visible behavior
expect(screen.getByText('Count: 1')).toBeInTheDocument()
```

### 2. Use Accessible Queries

```typescript
// ✅ Preferred order
screen.getByRole('button', { name: 'Submit' })
screen.getByLabelText('Email')
screen.getByPlaceholderText('Enter email')
screen.getByText('Welcome')

// ❌ Avoid
screen.getByTestId('submit-button')
```

### 3. Wait for Async Updates

```typescript
// ✅ Use findBy for async elements
expect(await screen.findByText('Loaded')).toBeInTheDocument()

// ✅ Use waitFor for complex conditions
await waitFor(() => {
  expect(screen.getByText('Success')).toBeInTheDocument()
})
```

### 4. Clean Up Between Tests

Tests are automatically cleaned up by `@testing-library/react`'s cleanup function in `setup.ts`.

### 5. Mock External Dependencies

- **API calls**: Use MSW handlers in `src/test/mocks/handlers.ts`
- **Browser APIs**: Mock in `src/test/setup.ts`
- **Third-party libraries**: Mock with `vi.mock()`

## Debugging Tests

### Run Single Test File

```bash
npm test -- StatusBadge.test.tsx
```

### Run Tests Matching Pattern

```bash
npm test -- --grep "renders correctly"
```

### Debug in VS Code

Add to `.vscode/launch.json`:

```json
{
  "type": "node",
  "request": "launch",
  "name": "Debug Vitest Tests",
  "runtimeExecutable": "npm",
  "runtimeArgs": ["run", "test"],
  "console": "integratedTerminal",
  "internalConsoleOptions": "neverOpen"
}
```

### View Test UI

```bash
npm run test:ui
```

Opens interactive UI at `http://localhost:51204/__vitest__/`

## Common Issues

### TypeScript Errors in Test Files

The jest-dom matchers (like `toBeInTheDocument`) may show TypeScript errors in the editor, but tests will run correctly. This is expected and resolved at runtime by the setup file.

### MSW Warnings

If you see "unhandled request" warnings, add handlers to `src/test/mocks/handlers.ts` for those endpoints.

### Coverage Not Meeting Threshold

Run `npm run test:coverage` and open `coverage/index.html` to see which files need more tests.

## Resources

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [MSW Documentation](https://mswjs.io/)
- [Testing Library Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)