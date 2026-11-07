import { describe, it, expect, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation, useNavigate } from 'react-router-dom'
import useSeciliKayit from './useSeciliKayit'

const kayitlar = () => [{ id: 3, ad: 'uc' }, { id: 7, ad: 'yedi' }]

// Kanca ile birlikte adres ve gezinme de okunur: secim yalniz ?kayit= parametresinde tutulur
const kur = (giris, ilk = kayitlar()) => renderHook(
  ({ liste }) => ({ ...useSeciliKayit(liste), konum: useLocation(), git: useNavigate() }),
  {
    initialProps: { liste: ilk },
    wrapper: ({ children }) => <MemoryRouter initialEntries={[giris]}>{children}</MemoryRouter>,
  },
)

describe('useSeciliKayit', () => {
  it('parametredeki id ile cozer', () => {
    const { result } = kur('/cve?kayit=7')
    expect(result.current.secili.id).toBe(7)
    expect(result.current.secili.ad).toBe('yedi')
  })

  it('bilinmeyen id null', () => {
    expect(kur('/cve?kayit=999').result.current.secili).toBeNull()
    expect(kur('/cve?kayit=').result.current.secili).toBeNull()
    expect(kur('/cve?kayit=abc').result.current.secili).toBeNull()
    expect(kur('/cve').result.current.secili).toBeNull()
  })

  it('liste yenilenince secim korunur', () => {
    const { result, rerender } = kur('/cve?kayit=7')
    // Periyodik yenileme ayni kayitlari yeni nesnelerle getirir
    const yeni = [{ id: 7, ad: 'yedi (guncel)' }, { id: 3, ad: 'uc' }]
    rerender({ liste: yeni })
    expect(result.current.secili).toBe(yeni[0])
  })

  it('liste yuklenmeden panel kapali, yuklenince acilir', () => {
    const { result, rerender } = kur('/cve?kayit=7', [])
    expect(result.current.secili).toBeNull()
    rerender({ liste: kayitlar() })
    expect(result.current.secili.id).toBe(7)
  })

  it('secili_kayit_listeden_dusunce_panel_acik_kalir', () => {
    // Sayfa degisimi, filtre ya da 5 sn yenilemesi secili kaydi gorunen sayfadan dusurebilir
    const { result, rerender } = kur('/cve?kayit=7')
    const ilk = result.current.secili
    rerender({ liste: [{ id: 3, ad: 'uc' }] })
    expect(result.current.secili).toBe(ilk)
    rerender({ liste: [] })
    expect(result.current.secili).toBe(ilk)
    // Kayit listeye guncel haliyle donerse guncel nesne kullanilir
    const guncel = { id: 7, ad: 'yedi (guncel)' }
    rerender({ liste: [guncel] })
    expect(result.current.secili).toBe(guncel)
    // Baska kayit secilince eskisi tutulmaz; kapat ile panel kapanir
    act(() => result.current.sec(3))
    rerender({ liste: [{ id: 3, ad: 'uc' }] })
    expect(result.current.secili.id).toBe(3)
    act(() => result.current.kapat())
    expect(result.current.konum.search).toBe('')
    expect(result.current.secili).toBeNull()
  })

  it('sec adrese ekler, geri tusu paneli kapatir', () => {
    const { result } = kur('/cve?gun=3')
    act(() => result.current.sec(3))
    expect(result.current.konum.search).toBe('?gun=3&kayit=3')
    expect(result.current.secili.id).toBe(3)
    act(() => result.current.git(-1))
    expect(result.current.konum.search).toBe('?gun=3')
    expect(result.current.secili).toBeNull()
  })

  it('kapat parametreyi siler ve geri tusu paneli yeniden acmaz', () => {
    const { result } = kur('/cve')
    act(() => result.current.sec(7))
    act(() => result.current.kapat())
    expect(result.current.konum.search).toBe('')
    expect(result.current.secili).toBeNull()
    // Panel acilmadan onceki giris yerinde: geri tusu /cve'nin oncesine gider, ?kayit=7'ye donmez
    expect(result.current.konum.key).toBe('default')
  })

  it('art arda iki kapat cagrisi bir kez geri gider', () => {
    // Offcanvas onHide, popstate islenmeden iki kez gelebilir (Esc + kapat dugmesi)
    const { result } = kur('/onceki')
    act(() => result.current.git('/cve'))
    act(() => result.current.sec(7))
    act(() => {
      result.current.kapat()
      result.current.kapat()
    })
    expect(result.current.konum.pathname).toBe('/cve')
    expect(result.current.konum.search).toBe('')
    // Ayni kayit yeniden acilip kapatilabilir
    act(() => result.current.sec(7))
    act(() => result.current.kapat())
    expect(result.current.konum.pathname).toBe('/cve')
    expect(result.current.konum.search).toBe('')
  })

  it('panel kapaliyken kapat bir sey yapmaz', () => {
    const { result } = kur('/onceki')
    act(() => result.current.git('/cve'))
    act(() => result.current.kapat())
    expect(result.current.konum.pathname).toBe('/cve')
  })

  it('paylasilan adreste kapat parametreyi yerinde siler', () => {
    const { result } = kur('/cve?kayit=7')
    act(() => result.current.kapat())
    expect(result.current.konum.pathname).toBe('/cve')
    expect(result.current.konum.search).toBe('')
    expect(result.current.secili).toBeNull()
  })

  describe('listede olmayan paylasilan kayit', () => {
    const kurUzak = (giris, tekilGetir, liste = kayitlar(), hazir = true) => renderHook(
      ({ l, h }) => ({ ...useSeciliKayit(l, tekilGetir, h), konum: useLocation() }),
      {
        initialProps: { l: liste, h: hazir },
        wrapper: ({ children }) => <MemoryRouter initialEntries={[giris]}>{children}</MemoryRouter>,
      },
    )

    it('sunucudan_istenir_ve_panel_acilir', async () => {
      const tekilGetir = vi.fn().mockResolvedValue({ id: 999, ad: 'eski kayit' })
      const { result } = kurUzak('/cve?kayit=999', tekilGetir)
      await waitFor(() => expect(result.current.secili?.ad).toBe('eski kayit'))
      expect(tekilGetir).toHaveBeenCalledTimes(1)
      expect(tekilGetir).toHaveBeenCalledWith(999)
    })

    it('liste_yuklenirken_istenmez_listede_varsa_hic_istenmez', async () => {
      const tekilGetir = vi.fn().mockResolvedValue(null)
      const { result, rerender } = kurUzak('/cve?kayit=7', tekilGetir, [], false)
      expect(tekilGetir).not.toHaveBeenCalled()
      rerender({ l: kayitlar(), h: true })
      expect(result.current.secili.id).toBe(7)
      expect(tekilGetir).not.toHaveBeenCalled()
    })

    it('bulunamazsa_parametre_silinir', async () => {
      const tekilGetir = vi.fn().mockResolvedValue(null)
      const { result } = kurUzak('/cve?kayit=999&gun=1', tekilGetir)
      await waitFor(() => expect(result.current.konum.search).toBe('?gun=1'))
      expect(result.current.secili).toBeNull()
    })

    it('ag_hatasinda_parametre_kalir', async () => {
      const tekilGetir = vi.fn().mockRejectedValue(new Error('ag'))
      const { result } = kurUzak('/cve?kayit=999', tekilGetir)
      await waitFor(() => expect(tekilGetir).toHaveBeenCalled())
      await act(async () => {})
      expect(result.current.konum.search).toBe('?kayit=999')
      expect(tekilGetir).toHaveBeenCalledTimes(1)
    })
  })
})
