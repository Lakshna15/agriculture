import { afterEach, describe, expect, it, vi } from 'vitest'

import { LATITUDE_LIMIT, LONGITUDE_LIMIT, parseCoordinate } from './coordinates.ts'
import {
  formatDate,
  formatDistance,
  formatPrice,
  formatPriceOrFree,
  formatTime,
  todayAsIsoDate,
} from './format.ts'
import { formatFarmAddress, reservationActionsFor } from './reservations.ts'
import { readSearchLocation, storeSearchLocation } from './searchLocation.ts'

describe('parseCoordinate', () => {
  it.each([
    ['35.2271', LATITUDE_LIMIT, 35.2271],
    ['-80.8431', LONGITUDE_LIMIT, -80.8431],
    [' 90 ', LATITUDE_LIMIT, 90],
    ['-180', LONGITUDE_LIMIT, -180],
    ['0', LATITUDE_LIMIT, 0],
  ])('reads %j as a coordinate', (text, limit, expected) => {
    expect(parseCoordinate(text, limit)).toBe(expected)
  })

  it.each([
    ['', LATITUDE_LIMIT],
    ['   ', LATITUDE_LIMIT],
    ['north', LATITUDE_LIMIT],
    ['90.0001', LATITUDE_LIMIT],
    ['-180.5', LONGITUDE_LIMIT],
    ['Infinity', LONGITUDE_LIMIT],
    ['NaN', LATITUDE_LIMIT],
  ])('refuses %j', (text, limit) => {
    expect(parseCoordinate(text, limit)).toBeNull()
  })
})

describe('formatting', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('formats prices as dollars with cents', () => {
    expect(formatPrice('4.5')).toBe('$4.50')
    expect(formatPrice('1250.00')).toBe('$1,250.00')
  })

  it('shows a zero price as free', () => {
    expect(formatPriceOrFree('0.00')).toBe('Free')
    expect(formatPriceOrFree('12.00')).toBe('$12.00')
  })

  it('formats a calendar date without shifting it to the previous day', () => {
    expect(formatDate('2026-06-01')).toBe('Jun 1, 2026')
    expect(formatDate('2026-12-31')).toBe('Dec 31, 2026')
  })

  it('formats 24-hour times as 12-hour times', () => {
    expect(formatTime('14:30:00')).toBe('2:30 PM')
    expect(formatTime('00:05:00')).toBe('12:05 AM')
  })

  it('formats distances to one decimal place', () => {
    expect(formatDistance(3)).toBe('3.0 mi')
    expect(formatDistance(12.345)).toBe('12.3 mi')
  })

  it('gives today as a padded ISO date', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 2, 7, 23, 59))

    expect(todayAsIsoDate()).toBe('2026-03-07')
  })
})

describe('reservation actions', () => {
  it('lets the farm confirm or cancel a pending reservation', () => {
    expect(reservationActionsFor('farmer', 'PENDING').map((action) => action.newStatus)).toEqual([
      'CONFIRMED',
      'CANCELLED',
    ])
  })

  it('lets the farm complete or cancel a confirmed reservation', () => {
    expect(reservationActionsFor('farmer', 'CONFIRMED').map((action) => action.newStatus)).toEqual([
      'COMPLETED',
      'CANCELLED',
    ])
  })

  it('lets the customer only cancel, while the reservation is still open', () => {
    expect(reservationActionsFor('customer', 'PENDING').map((action) => action.newStatus)).toEqual([
      'CANCELLED',
    ])
    expect(reservationActionsFor('customer', 'CONFIRMED').map((action) => action.newStatus)).toEqual([
      'CANCELLED',
    ])
  })

  it.each(['COMPLETED', 'CANCELLED'] as const)('offers nothing once a reservation is %s', (status) => {
    expect(reservationActionsFor('farmer', status)).toEqual([])
    expect(reservationActionsFor('customer', status)).toEqual([])
  })

  it('formats a farm address on one line', () => {
    expect(
      formatFarmAddress({
        id: 1,
        farm_name: 'Green Acres',
        address: '12 Field Rd',
        city: 'Concord',
        state: 'NC',
        zip_code: '28025',
        phone: null,
      }),
    ).toBe('12 Field Rd, Concord, NC 28025')
  })
})

describe('remembered search location', () => {
  it('is empty until a location is stored', () => {
    expect(readSearchLocation()).toEqual({ latitude: '', longitude: '' })
  })

  it('returns the stored location', () => {
    storeSearchLocation({ latitude: '35.2', longitude: '-80.8' })

    expect(readSearchLocation()).toEqual({ latitude: '35.2', longitude: '-80.8' })
  })

  it('stays in session storage, not local storage', () => {
    storeSearchLocation({ latitude: '35.2', longitude: '-80.8' })

    expect(window.localStorage.length).toBe(0)
  })

  it.each([
    ['not JSON', '{oops'],
    ['the wrong shape', JSON.stringify({ lat: 1, lng: 2 })],
    ['numbers instead of text', JSON.stringify({ latitude: 35.2, longitude: -80.8 })],
  ])('ignores a stored value that is %s', (_case, stored) => {
    window.sessionStorage.setItem('farm2local.searchLocation', stored)

    expect(readSearchLocation()).toEqual({ latitude: '', longitude: '' })
  })
})
