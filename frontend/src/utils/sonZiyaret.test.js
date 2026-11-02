import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { sonZiyaretOku, sonZiyaretYaz, ziyaretTabani, TABAN_OMRU_MS } from './sonZiyaret'

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
  it('taban omru dolunca son ziyarete ilerler, dolmadan ilerlemez', () => {
    const t0 = Date.parse('2026-11-01T08:00:00Z')
    sonZiyaretYaz('2026-10-30T08:00:00Z')
    expect(ziyaretTabani(t0)).toBe('2026-10-30T08:00:00Z')
    sonZiyaretYaz('2026-11-01T09:00:00Z')
    expect(ziyaretTabani(t0 + TABAN_OMRU_MS - 1)).toBe('2026-10-30T08:00:00Z')
    expect(ziyaretTabani(t0 + TABAN_OMRU_MS)).toBe('2026-11-01T09:00:00Z')
    // Yeni taban yeni omurle sabitlenir
    sonZiyaretYaz('2026-11-01T15:00:00Z')
    expect(ziyaretTabani(t0 + TABAN_OMRU_MS + 1)).toBe('2026-11-01T09:00:00Z')
  })
  it('kurulma zamani olmayan eski taban bir kez yenilenir', () => {
    sessionStorage.setItem('tr.sonZiyaretTaban', '2026-10-01T08:00:00Z')
    sonZiyaretYaz('2026-10-31T08:00:00Z')
    expect(ziyaretTabani()).toBe('2026-10-31T08:00:00Z')
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
