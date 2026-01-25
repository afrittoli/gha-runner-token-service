import { describe, it, expect } from 'vitest'
import { formatDate, getStatusBadgeClass } from './formatters'

describe('formatters', () => {
  describe('formatDate', () => {
    it('formats ISO date string correctly', () => {
      const date = '2024-01-15T10:30:00Z'
      const result = formatDate(date)
      // Should contain date and time
      expect(result).toContain('Jan')
      expect(result).toContain('2024')
    })

    it('handles undefined date', () => {
      const result = formatDate(undefined)
      expect(result).toBe('Never')
    })

    it('formats valid date object', () => {
      const date = new Date('2024-01-15T10:30:00Z').toISOString()
      const result = formatDate(date)
      expect(result).toBeTruthy()
      expect(result).not.toBe('Never')
    })
  })

  describe('getStatusBadgeClass', () => {
    it('returns correct class for active status', () => {
      const result = getStatusBadgeClass('active')
      expect(result).toContain('bg-green-100')
      expect(result).toContain('text-green-800')
    })

    it('returns correct class for online status', () => {
      const result = getStatusBadgeClass('online')
      expect(result).toContain('bg-green-100')
      expect(result).toContain('text-green-800')
    })

    it('returns correct class for offline status', () => {
      const result = getStatusBadgeClass('offline')
      expect(result).toContain('bg-gray-100')
      expect(result).toContain('text-gray-800')
    })

    it('returns correct class for pending status', () => {
      const result = getStatusBadgeClass('pending')
      expect(result).toContain('bg-yellow-100')
      expect(result).toContain('text-yellow-800')
    })

    it('returns correct class for deleted status', () => {
      const result = getStatusBadgeClass('deleted')
      expect(result).toContain('bg-red-100')
      expect(result).toContain('text-red-800')
    })

    it('returns default class for unknown status', () => {
      const result = getStatusBadgeClass('unknown')
      expect(result).toContain('bg-blue-100')
      expect(result).toContain('text-blue-800')
    })

    it('returns default class for undefined status', () => {
      const result = getStatusBadgeClass(undefined)
      expect(result).toContain('bg-blue-100')
      expect(result).toContain('text-blue-800')
    })
  })
})

// Made with Bob
