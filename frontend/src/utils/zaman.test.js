import { describe, it, expect } from 'vitest'
import { goreliZaman, tarihBicimle } from './zaman'

const T = Date.parse('2026-10-14T12:00:00Z')

describe('goreliZaman', () => {
  it('saniye, dakika, saat, gun esikleri', () => {
    expect(goreliZaman('2026-10-14T11:59:30Z', T)).toBe('az önce')
    expect(goreliZaman('2026-10-14T11:45:00Z', T)).toBe('15 dk önce')
    expect(goreliZaman('2026-10-14T06:00:00Z', T)).toBe('6 sa önce')
    expect(goreliZaman('2026-10-11T12:00:00Z', T)).toBe('3 gün önce')
  })
  it('24-48 saat dun, sonrasi gun', () => {
    expect(goreliZaman('2026-10-13T12:00:00Z', T)).toBe('dün')
    expect(goreliZaman('2026-10-13T00:00:01Z', T)).toBe('dün')
    expect(goreliZaman('2026-10-12T12:00:00Z', T)).toBe('2 gün önce')
  })
  it('bos, bozuk ve gelecek deger tire olur', () => {
    expect(goreliZaman(null, T)).toBe('-')
    expect(goreliZaman(undefined, T)).toBe('-')
    expect(goreliZaman('bozuk', T)).toBe('-')
    expect(goreliZaman('2026-10-14T13:00:00Z', T)).toBe('-')
  })
})

describe('tarihBicimle', () => {
  it('iso_gunu_turkce_yazar', () => {
    expect(tarihBicimle('2026-11-05')).toBe('5 Kasım 2026')
    expect(tarihBicimle('2026-01-31T23:30:00Z')).toBe('31 Ocak 2026')
  })

  it('iso_olmayan_ve_bozuk_deger_aynen_doner', () => {
    expect(tarihBicimle('Nov 05, 2026')).toBe('Nov 05, 2026')
    expect(tarihBicimle('2026-02-31')).toBe('2026-02-31')
    expect(tarihBicimle('')).toBe('')
    expect(tarihBicimle(null)).toBe('')
  })
})
