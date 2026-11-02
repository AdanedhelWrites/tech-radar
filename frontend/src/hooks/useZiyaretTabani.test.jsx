import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import useZiyaretTabani from './useZiyaretTabani'
import { sonZiyaretYaz, TABAN_OMRU_MS } from '../utils/sonZiyaret'

const gorunurlukDegistir = (durum) => {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => durum })
  try {
    document.dispatchEvent(new Event('visibilitychange'))
  } finally {
    delete document.visibilityState
  }
}

describe('useZiyaretTabani', () => {
  beforeEach(() => { localStorage.clear(); sessionStorage.clear() })
  afterEach(() => vi.restoreAllMocks())

  it('ilk degeri tabandan okur', () => {
    sonZiyaretYaz('2026-10-30T08:00:00Z')
    const { result } = renderHook(() => useZiyaretTabani())
    expect(result.current).toBe('2026-10-30T08:00:00Z')
  })

  it('sekmeye omur dolduktan sonra donulunce taban ilerler, once donulunce ilerlemez', () => {
    const t0 = Date.parse('2026-11-01T08:00:00Z')
    const simdi = vi.spyOn(Date, 'now').mockReturnValue(t0)
    sonZiyaretYaz('2026-10-30T08:00:00Z')
    const { result } = renderHook(() => useZiyaretTabani())
    sonZiyaretYaz('2026-11-01T09:00:00Z') // sekme gizlenince Genel Bakis yazar

    simdi.mockReturnValue(t0 + 60 * 1000)
    act(() => gorunurlukDegistir('visible'))
    expect(result.current).toBe('2026-10-30T08:00:00Z')

    simdi.mockReturnValue(t0 + TABAN_OMRU_MS)
    act(() => gorunurlukDegistir('hidden'))
    expect(result.current).toBe('2026-10-30T08:00:00Z')
    act(() => gorunurlukDegistir('visible'))
    expect(result.current).toBe('2026-11-01T09:00:00Z')
  })

  it('ayrilinca dinleyiciyi kaldirir', () => {
    const kaldir = vi.spyOn(document, 'removeEventListener')
    const { unmount } = renderHook(() => useZiyaretTabani())
    unmount()
    expect(kaldir).toHaveBeenCalledWith('visibilitychange', expect.any(Function))
  })
})
