import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { sonZiyaretOku, sonZiyaretYaz, ziyaretTabani } from './sonZiyaret'

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

describe('ziyaretTabani (sekme basina, karar R9)', () => {
  beforeEach(() => { localStorage.clear(); sessionStorage.clear() })
  afterEach(() => vi.restoreAllMocks())

  it('ilk ziyarette null doner ve taban yazmaz', () => {
    expect(ziyaretTabani()).toBeNull()
    expect(sessionStorage.length).toBe(0)
  })
  it('localStorage degerini sekmenin tabani yapar; sonraki yazma tabani degistirmez', () => {
    sonZiyaretYaz('2026-10-30T08:00:00Z')
    expect(ziyaretTabani()).toBe('2026-10-30T08:00:00Z')
    sonZiyaretYaz('2026-10-31T08:00:00Z') // sayfa gizlendi / F5 (pagehide)
    expect(ziyaretTabani()).toBe('2026-10-30T08:00:00Z')
  })
  it('sessionStorage hata firlatirsa localStorage degerine duser', () => {
    sonZiyaretYaz('2026-10-30T08:00:00Z')
    // Yalniz sessionStorage bozuk: Storage metotlari prototipte, ornek uzerinde spy kurulamaz
    const { getItem, setItem } = Storage.prototype
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (k) {
      if (this === window.sessionStorage) throw new Error('x')
      return getItem.call(this, k)
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (k, v) {
      if (this === window.sessionStorage) throw new Error('x')
      return setItem.call(this, k, v)
    })
    expect(ziyaretTabani()).toBe('2026-10-30T08:00:00Z')
  })
  it('iki depolama da hata firlatirsa null doner', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('x') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('x') })
    expect(ziyaretTabani()).toBeNull()
  })
})
