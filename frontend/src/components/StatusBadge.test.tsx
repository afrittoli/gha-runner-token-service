import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatusBadge from './StatusBadge'

describe('StatusBadge', () => {
  it('renders with online status', () => {
    render(<StatusBadge status="online" />)
    const badge = screen.getByText('online')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-green-100', 'text-green-800')
  })

  it('renders with offline status', () => {
    render(<StatusBadge status="offline" />)
    const badge = screen.getByText('offline')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-gray-100', 'text-gray-800')
  })

  it('renders with pending status', () => {
    render(<StatusBadge status="pending" />)
    const badge = screen.getByText('pending')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-yellow-100', 'text-yellow-800')
  })

  it('renders with active status', () => {
    render(<StatusBadge status="active" />)
    const badge = screen.getByText('active')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-green-100', 'text-green-800')
  })

  it('renders with deleted status', () => {
    render(<StatusBadge status="deleted" />)
    const badge = screen.getByText('deleted')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-red-100', 'text-red-800')
  })

  it('renders "unknown" when status is undefined', () => {
    render(<StatusBadge status={undefined} />)
    const badge = screen.getByText('unknown')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-blue-100', 'text-blue-800')
  })

  it('applies correct CSS classes', () => {
    render(<StatusBadge status="online" />)
    const badge = screen.getByText('online')
    expect(badge).toHaveClass('px-2', 'py-0.5', 'text-xs', 'font-semibold', 'rounded-full', 'border')
  })

  it('renders custom status text', () => {
    render(<StatusBadge status="custom-status" />)
    const badge = screen.getByText('custom-status')
    expect(badge).toBeInTheDocument()
  })
})

// Made with Bob
