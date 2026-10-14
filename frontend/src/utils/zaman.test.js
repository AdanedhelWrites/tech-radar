import { describe, it, expect } from 'vitest'
import { goreliZaman } from './zaman'

const T = Date.parse('2026-10-14T12:00:00Z')

describe('goreliZaman', () => {
  it('saniye, dakika, saat, gun esikleri', () => {
    expect(goreliZaman('2026-10-14T11:59:30Z', T)).toBe('az önce')
    expect(goreliZaman('2026-10-14T11:45:00Z', T)).toBe('15 dk önce')
    expect(goreliZaman('2026-10-14T06:00:00Z', T)).toBe('6 sa önce')
    expect(goreliZaman('2026-10-11T12:00:00Z', T)).toBe('3 gün önce')
  })
  it('bos, bozuk ve gelecek deger tire olur', () => {
    expect(goreliZaman(null, T)).toBe('-')
    expect(goreliZaman(undefined, T)).toBe('-')
    expect(goreliZaman('bozuk', T)).toBe('-')
    expect(goreliZaman('2026-10-14T13:00:00Z', T)).toBe('-')
  })
})
