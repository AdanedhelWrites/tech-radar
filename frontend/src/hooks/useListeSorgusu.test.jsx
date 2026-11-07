import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import useListeSorgusu from './useListeSorgusu'

// Sunucu zarfi (Task 1): {success, data, cached, count, toplam, sayfa, sayfa_sayisi, boyut}
const zarf = (params, ek = {}) => ({
  data: {
    success: true,
    data: [{ id: (params.sayfa || 1) * 100, ad: 'kayit' }],
    cached: false,
    count: 1,
    toplam: 60,
    sayfa: params.sayfa || 1,
    sayfa_sayisi: 3,
    boyut: 25,
    ...ek,
  },
})

const sahteGetir = () => vi.fn(async (params) => zarf(params))

// Kanca ile birlikte adres de okunur: sorgu durumu yalniz adreste tutulur
// durumlar: her render'daki yukleniyor degeri (sessiz yenilemenin onu hic degistirmedigini gormek icin)
const kur = (giris, getir = sahteGetir(), ekAnahtarlar, kaynaklar, ekDegerler) => {
  const durumlar = []
  const sonuc = renderHook(
    () => {
      const r = { ...useListeSorgusu({ getir, ekAnahtarlar, kaynaklar, ekDegerler }), konum: useLocation() }
      durumlar.push(r.yukleniyor)
      return r
    },
    { wrapper: ({ children }) => <MemoryRouter initialEntries={[giris]}>{children}</MemoryRouter> },
  )
  return { ...sonuc, getir, durumlar }
}

const yuklendi = (result) => waitFor(() => expect(result.current.yukleniyor).toBe(false))

describe('useListeSorgusu', () => {
  afterEach(() => { vi.useRealTimers() })

  it('adres_parametrelerini_okur', async () => {
    const { result } = kur('/cve?gun=1&sirala=cvss&sayfa=2&kaynak=NVD,CISA%20KEV&onem=kritik',
      undefined, ['onem'])
    expect(result.current.sorgu).toEqual({
      gun: 1, sirala: 'cvss', kaynak: ['NVD', 'CISA KEV'], ara: '', onem: 'kritik',
    })
    expect(result.current.sayfa).toBe(2)
    await yuklendi(result)
    expect(result.current.kayitlar).toEqual([{ id: 200, ad: 'kayit' }])
    expect(result.current.toplam).toBe(60)
    expect(result.current.sayfaSayisi).toBe(3)
    expect(result.current.boyut).toBe(25)
    expect(result.current.hata).toBeNull()
  })

  it('varsayilanlar_adrese_yazilmaz', async () => {
    const { result } = kur('/k8s?gun=1&sirala=eski&kaynak=A&kategori=guvenlik', undefined, ['kategori'])
    await yuklendi(result)
    // Varsayilan sorgu: Son 7 gun, en yeni, bos kaynak/ek filtre
    expect(kur('/k8s').result.current.sorgu).toEqual({ gun: 7, sirala: 'yeni', kaynak: [], ara: '' })
    act(() => result.current.degistir({ gun: 7, sirala: 'yeni', kaynak: [], kategori: '' }))
    expect(result.current.konum.search).toBe('')
    // Tumu (null) varsayilan degil: adreste acikca tutulur
    act(() => result.current.degistir({ gun: null }))
    expect(result.current.sorgu.gun).toBeNull()
    expect(result.current.konum.search).toBe('?gun=tumu')
    act(() => result.current.sayfayaGit(1))
    expect(result.current.konum.search).toBe('?gun=tumu')
  })

  it('filtre_degisince_sayfa_sifirlanir', async () => {
    const { result, getir } = kur('/news?sayfa=5&kayit=9')
    await yuklendi(result)
    act(() => result.current.degistir({ kaynak: ['The Register', 'SANS ISC'] }))
    // Acik panel (kayit) korunur; sayfa silinir
    expect(result.current.konum.search).toBe('?kayit=9&kaynak=The+Register%2CSANS+ISC')
    expect(result.current.sayfa).toBe(1)
    await waitFor(() => expect(getir).toHaveBeenLastCalledWith(
      { gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25, kaynak: 'The Register,SANS ISC' }))
    act(() => result.current.sayfayaGit(3))
    act(() => result.current.degistir({ sirala: 'eski' }))
    expect(result.current.konum.search).toBe('?kayit=9&kaynak=The+Register%2CSANS+ISC&sirala=eski')
  })

  it('sayfayaGit_yalniz_sayfayi_yazar', async () => {
    const { result, getir } = kur('/cve?gun=3&onem=orta&kayit=4', undefined, ['onem'])
    await yuklendi(result)
    act(() => result.current.sayfayaGit(2))
    expect(result.current.konum.search).toBe('?gun=3&onem=orta&kayit=4&sayfa=2')
    expect(result.current.sorgu).toEqual({ gun: 3, sirala: 'yeni', kaynak: [], ara: '', onem: 'orta' })
    await waitFor(() => expect(result.current.sayfa).toBe(2))
    expect(getir).toHaveBeenLastCalledWith({ gun: 3, sirala: 'yeni', sayfa: 2, boyut: 25, onem: 'orta' })
  })

  it('gecersiz_adres_parametreleri_varsayilana_duser', async () => {
    const { result, getir } = kur('/news?gun=abc&sayfa=-3&sirala=x')
    expect(result.current.sorgu).toEqual({ gun: 7, sirala: 'yeni', kaynak: [], ara: '' })
    expect(result.current.sayfa).toBe(1)
    await yuklendi(result)
    expect(getir).toHaveBeenCalledWith({ gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25 })
    // Listede olmayan gun ve kesirli sayfa da varsayilana duser
    const ikinci = kur('/news?gun=5&sayfa=2.5')
    expect(ikinci.result.current.sorgu.gun).toBe(7)
    expect(ikinci.result.current.sayfa).toBe(1)
  })

  it('yenileme_sayfayi_degistirmez', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { result, getir, durumlar } = kur('/sre?kayit=7')
    await yuklendi(result)
    const ilkRenderSayisi = durumlar.length
    expect(getir).toHaveBeenCalledTimes(1)
    // Yenilemede sunucu yeni kayit dondurur; sayfa, adres ve yukleniyor durumu degismez.
    // Yanit bekletilir: istek suresince de yukleniyor false kalmali (liste yerine yukleniyor gorunmez)
    let coz
    getir.mockImplementation((params) => new Promise(r => {
      coz = () => r(zarf(params, { data: [{ id: 999 }], toplam: 61 }))
    }))
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(getir).toHaveBeenCalledTimes(2)
    expect(result.current.yukleniyor).toBe(false)
    expect(result.current.kayitlar).toEqual([{ id: 100, ad: 'kayit' }])
    // Yanit gelmeden bir sonraki tur istek yigmaz
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(getir).toHaveBeenCalledTimes(2)
    await act(async () => { coz() })
    expect(getir).toHaveBeenLastCalledWith({ gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25 })
    expect(result.current.kayitlar).toEqual([{ id: 999 }])
    expect(result.current.toplam).toBe(61)
    expect(result.current.sayfa).toBe(1)
    expect(result.current.konum.search).toBe('?kayit=7')
    expect(durumlar.length).toBeGreaterThan(ilkRenderSayisi)
    expect(durumlar.slice(ilkRenderSayisi).every(d => d === false)).toBe(true)
    // Sessiz yenileme hatasi ekrandaki listeyi ve hatayi bozmaz
    getir.mockRejectedValueOnce(new Error('ag'))
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(result.current.hata).toBeNull()
    expect(result.current.kayitlar).toEqual([{ id: 999 }])
  })

  it('sonraki_sayfalarda_sessiz_yenileme_yok', async () => {
    // Yeni kayit gelince sayfa 2+ kayardi; okuyan kullanicinin listesi ve tiklayacagi satir oynamasin
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { result, getir } = kur('/sre?sayfa=2')
    await yuklendi(result)
    expect(getir).toHaveBeenCalledTimes(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(15000) })
    expect(getir).toHaveBeenCalledTimes(1)
    // Elle yenileme o sayfayi yine ister
    await act(async () => { result.current.yenile() })
    expect(getir).toHaveBeenCalledTimes(2)
    expect(getir).toHaveBeenLastCalledWith({ gun: 7, sirala: 'yeni', sayfa: 2, boyut: 25 })
  })

  it('arama_adrese_ve_istege_yazilir', async () => {
    const { result, getir } = kur('/cve?sayfa=3')
    await yuklendi(result)
    act(() => result.current.degistir({ ara: 'log4j' }))
    expect(result.current.konum.search).toBe('?ara=log4j')
    expect(result.current.sorgu.ara).toBe('log4j')
    await waitFor(() => expect(getir).toHaveBeenLastCalledWith(
      { gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25, ara: 'log4j' }))
    // Tek karakterlik arama istege gitmez (sunucu da suzmez); bos arama adresten silinir
    act(() => result.current.degistir({ ara: 'x' }))
    await waitFor(() => expect(getir).toHaveBeenLastCalledWith({ gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25 }))
    act(() => result.current.degistir({ ara: '' }))
    expect(result.current.konum.search).toBe('')
  })

  it('getire_dogru_parametreler_gider', async () => {
    const { result, getir } = kur('/cve?kaynak=NVD,GitHub&gun=tumu&sirala=cvss&onem=', undefined, ['onem'])
    await yuklendi(result)
    // Tumu: gun gonderilmez (sunucuda gun yok = hepsi); bos ek filtre gonderilmez
    expect(getir).toHaveBeenLastCalledWith({ sirala: 'cvss', sayfa: 1, boyut: 25, kaynak: 'NVD,GitHub' })
    act(() => result.current.degistir({ gun: 7, onem: 'kritik' }))
    // Varsayilan gun=7 adrese yazilmaz ama istekte her zaman gider
    expect(result.current.konum.search).toBe('?kaynak=NVD%2CGitHub&sirala=cvss&onem=kritik')
    await waitFor(() => expect(getir).toHaveBeenLastCalledWith(
      { gun: 7, sirala: 'cvss', sayfa: 1, boyut: 25, kaynak: 'NVD,GitHub', onem: 'kritik' }))
    // Elle yenile ayni sorguyu yeniden ister
    const onceki = getir.mock.calls.length
    await act(async () => { await result.current.yenile() })
    expect(getir).toHaveBeenCalledTimes(onceki + 1)
    expect(getir).toHaveBeenLastCalledWith(
      { gun: 7, sirala: 'cvss', sayfa: 1, boyut: 25, kaynak: 'NVD,GitHub', onem: 'kritik' })
  })

  it('hata_durumunda_hata_doner_ve_eski_yanit_yeni_sorguyu_ezmez', async () => {
    let coz
    const getir = vi.fn()
      .mockImplementationOnce(() => new Promise(r => { coz = r }))
      .mockImplementation(async (params) => zarf(params))
    const { result } = kur('/ai', getir)
    // Ilk istek bitmeden sayfa degisir: gec gelen eski yanit yeni sayfanin listesini ezmemeli
    act(() => result.current.sayfayaGit(3))
    await waitFor(() => expect(result.current.kayitlar).toEqual([{ id: 300, ad: 'kayit' }]))
    await act(async () => { coz(zarf({ sayfa: 1 })) })
    expect(result.current.kayitlar).toEqual([{ id: 300, ad: 'kayit' }])
    expect(result.current.yukleniyor).toBe(false)

    const hatali = vi.fn().mockRejectedValue(new Error('500'))
    const ikinci = kur('/ai', hatali)
    await yuklendi(ikinci.result)
    expect(ikinci.result.current.hata).toBeInstanceOf(Error)
    expect(ikinci.result.current.kayitlar).toEqual([])
  })

  it('yeni_istek_eski_hatayi_temizler', async () => {
    let coz
    const getir = vi.fn()
      .mockRejectedValueOnce(new Error('500'))
      .mockImplementation((params) => new Promise(r => { coz = () => r(zarf(params)) }))
    const { result } = kur('/sre', getir)
    await yuklendi(result)
    expect(result.current.hata).toBeInstanceOf(Error)
    // Yeni sorgu baslar baslamaz eski hata kalkar (yanit beklenirken eski uyari asili kalmaz)
    act(() => result.current.degistir({ gun: 1 }))
    await waitFor(() => expect(getir).toHaveBeenCalledTimes(2))
    expect(result.current.yukleniyor).toBe(true)
    expect(result.current.hata).toBeNull()
    await act(async () => { coz() })
    expect(result.current.hata).toBeNull()
  })

  it('basarisiz_yanit_hata_sayilir', async () => {
    const getir = vi.fn(async () => ({ data: { success: false, message: 'bozuk' } }))
    const { result } = kur('/devtools', getir)
    await yuklendi(result)
    expect(result.current.hata).toBeInstanceOf(Error)
    expect(result.current.hata.message).toBe('bozuk')
    expect(result.current.kayitlar).toEqual([])
  })

  it('bilinmeyen_kaynak_istege_gitmez', async () => {
    // Bolumun kaynak listesinde olmayan adres degerleri istege (ve Cek'e) gitmez
    const { result, getir } = kur('/cve?kaynak=Uydurma,NVD,%3Cx%3E', undefined, [], ['NVD', 'GitHub Advisory'])
    expect(result.current.sorgu.kaynak).toEqual(['NVD'])
    await yuklendi(result)
    expect(getir).toHaveBeenLastCalledWith({ gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25, kaynak: 'NVD' })
    // Yalniz bilinmeyen adlar: bos secim = hepsi, kaynak gonderilmez
    const ikinci = kur('/cve?kaynak=Uydurma', undefined, [], ['NVD', 'GitHub Advisory'])
    expect(ikinci.result.current.sorgu.kaynak).toEqual([])
    await yuklendi(ikinci.result)
    expect(ikinci.getir).toHaveBeenLastCalledWith({ gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25 })
  })

  it('gecersiz_ek_filtre_istege_gitmez', async () => {
    // ekDegerler verilen ek anahtarda listede olmayan adres degeri bos (= Tumu) sayilir
    const izinli = { onem: ['kritik', 'yuksek', 'orta', 'dusuk'] }
    const { result, getir } = kur('/cve?onem=uydurma', undefined, ['onem'], undefined, izinli)
    expect(result.current.sorgu.onem).toBe('')
    await yuklendi(result)
    expect(getir).toHaveBeenLastCalledWith({ gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25 })
    const ikinci = kur('/cve?onem=orta', undefined, ['onem'], undefined, izinli)
    await yuklendi(ikinci.result)
    expect(ikinci.getir).toHaveBeenLastCalledWith({ gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25, onem: 'orta' })
  })

  it('guncel_yalniz_gecerli_sorgunun_yanitinda', async () => {
    const getir = vi.fn(async (params) => {
      if (params.sayfa === 2) throw new Error('500')
      return zarf(params)
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const { result } = kur('/news', getir)
    expect(result.current.guncel).toBe(false)
    await yuklendi(result)
    expect(result.current.guncel).toBe(true)
    // Yeni sayfanin istegi basarisiz: eldeki toplam/kayitlar eski sorgunun, guncel degil
    act(() => result.current.sayfayaGit(2))
    await waitFor(() => expect(result.current.hata).toBeInstanceOf(Error))
    expect(result.current.yukleniyor).toBe(false)
    expect(result.current.guncel).toBe(false)
    act(() => result.current.sayfayaGit(1))
    await waitFor(() => expect(result.current.guncel).toBe(true))
    vi.restoreAllMocks()
  })

  it('istek_gecerli_parametreleri_dondurur', async () => {
    // Rapor ayni filtreyle sayfa sayfa ister: gecerli istek parametreleri disari verilir
    const { result } = kur('/k8s?gun=tumu&kaynak=A&kategori=security&sayfa=2', undefined, ['kategori'])
    await yuklendi(result)
    expect(result.current.istek).toEqual({ sirala: 'yeni', sayfa: 2, boyut: 25, kaynak: 'A', kategori: 'security' })
  })
})
