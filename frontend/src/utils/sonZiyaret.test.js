import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { sonZiyaretOku, sonZiyaretYaz } from './sonZiyaret'

describe('sonZiyaret', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.restoreAllMocks())

  it('yazilani okur', () => { sonZiyaretYaz('2026-10-31T08:00:00Z'); expect(sonZiyaretOku()).toBe('2026-10-31T08:00:00Z') })
  it('yazilmamissa null doner', () => expect(sonZiyaretOku()).toBeNull())
  it('localStorage hata firlatirsa null doner', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('x') })
    expect(sonZiyaretOku()).toBeNull()
  })
  it('yazma hata firlatirsa sessiz gecer', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('x') })
    expect(() => sonZiyaretYaz('2026-10-31T08:00:00Z')).not.toThrow()
  })
})
