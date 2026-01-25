import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import LabelPill from './LabelPill'

describe('LabelPill', () => {
  it('renders label text', () => {
    render(<LabelPill label="linux" />)
    expect(screen.getByText('linux')).toBeInTheDocument()
  })

  it('applies correct CSS classes', () => {
    render(<LabelPill label="x64" />)
    const pill = screen.getByText('x64')
    expect(pill).toHaveClass(
      'inline-flex',
      'items-center',
      'px-2',
      'py-0.5',
      'rounded',
      'text-xs',
      'font-medium',
      'bg-gh-gray-100',
      'text-gh-gray-700',
      'border',
      'border-gh-gray-200'
    )
  })

  it('renders with special characters', () => {
    render(<LabelPill label="self-hosted" />)
    expect(screen.getByText('self-hosted')).toBeInTheDocument()
  })

  it('renders with numbers', () => {
    render(<LabelPill label="ubuntu-22.04" />)
    expect(screen.getByText('ubuntu-22.04')).toBeInTheDocument()
  })

  it('renders empty label', () => {
    const { container } = render(<LabelPill label="" />)
    const pill = container.querySelector('span')
    expect(pill).toBeInTheDocument()
    expect(pill).toHaveClass('inline-flex')
  })

  it('renders long label text', () => {
    const longLabel = 'very-long-label-name-that-might-wrap'
    render(<LabelPill label={longLabel} />)
    expect(screen.getByText(longLabel)).toBeInTheDocument()
  })
})

// Made with Bob
