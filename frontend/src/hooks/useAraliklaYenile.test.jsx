import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import useAraliklaYenile from './useAraliklaYenile'

const gorunurluk = (gizli) => Object.defineProperty(document, 'hidden', { configurable: true, get: () => gizli })

describe('useAraliklaYenile', () => {
  beforeEach(() => { vi.useFakeTimers(); gorunurluk(false) })
  afterEach(() => { vi.useRealTimers(); gorunurluk(false) })

  it('aralik dolunca callback cagrilir', () => {
    const cb = vi.fn()
    renderHook(() => useAraliklaYenile(cb, 1000))
    vi.advanceTimersByTime(2500)
    expect(cb).toHaveBeenCalledTimes(2)
  })

  it('sekme arka plandayken istek atmaz, one gelince hemen yeniler', () => {
    const cb = vi.fn()
    renderHook(() => useAraliklaYenile(cb, 1000))
    gorunurluk(true)
    vi.advanceTimersByTime(3000)
    expect(cb).not.toHaveBeenCalled()
    gorunurluk(false)
    document.dispatchEvent(new Event('visibilitychange'))
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('unmount sonrasi zamanlayici ve dinleyici durur', () => {
    const cb = vi.fn()
    const { unmount } = renderHook(() => useAraliklaYenile(cb, 1000))
    unmount()
    vi.advanceTimersByTime(3000)
    document.dispatchEvent(new Event('visibilitychange'))
    expect(cb).not.toHaveBeenCalled()
  })

  it('en guncel callback kullanilir', () => {
    const ilk = vi.fn()
    const son = vi.fn()
    const { rerender } = renderHook(({ cb }) => useAraliklaYenile(cb, 1000), { initialProps: { cb: ilk } })
    rerender({ cb: son })
    vi.advanceTimersByTime(1000)
    expect(ilk).not.toHaveBeenCalled()
    expect(son).toHaveBeenCalledTimes(1)
  })
})
