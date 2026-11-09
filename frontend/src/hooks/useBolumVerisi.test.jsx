import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import useBolumVerisi from './useBolumVerisi'

vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }))

const sahteApi = () => ({
  liste: vi.fn().mockResolvedValue({ data: { success: true, data: [], toplam: 0 } }),
  istatistik: vi.fn().mockResolvedValue({ data: { success: true, total: 1, by_source: {}, last_update: null } }),
  cek: vi.fn(),
  temizle: vi.fn(),
})

const kur = (api) => renderHook(
  () => useBolumVerisi({ kaynaklar: [], api, metinler: { temizleOnayi: 'Emin misiniz?' }, rapor: {} }),
  { wrapper: ({ children }) => <MemoryRouter initialEntries={['/sre']}>{children}</MemoryRouter> },
)

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('useBolumVerisi', () => {
  it('istatistik_dakikada_bir_tazelenir', async () => {
    // Baslik ozeti yalniz acilista yukleniyordu; liste 5 sn'de tazelenirken baslik eskide kaliyordu
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const api = sahteApi()
    kur(api)
    await waitFor(() => expect(api.istatistik).toHaveBeenCalledTimes(1))
    await act(async () => { await vi.advanceTimersByTimeAsync(60000) })
    expect(api.istatistik).toHaveBeenCalledTimes(2)
  })

  it('sifirlama_surerken_ikinci_istek_atilmaz', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const api = sahteApi()
    let bitir
    api.temizle.mockImplementation(() => new Promise(r => { bitir = r }))
    const { result } = kur(api)
    await waitFor(() => expect(api.istatistik).toHaveBeenCalled())
    const kapat = vi.fn()
    act(() => { result.current.cubukOzellikleri(kapat).onTemizle() })
    await waitFor(() => expect(result.current.cubukOzellikleri(kapat).sifirlaniyor).toBe(true))
    act(() => { result.current.cubukOzellikleri(kapat).onTemizle() })
    expect(api.temizle).toHaveBeenCalledTimes(1)
    await act(async () => { bitir({ data: { success: true } }) })
    expect(result.current.cubukOzellikleri(kapat).sifirlaniyor).toBe(false)
    expect(kapat).toHaveBeenCalledTimes(1)
  })
})
