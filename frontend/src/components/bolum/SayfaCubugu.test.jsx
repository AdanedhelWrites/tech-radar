import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import SayfaCubugu from './SayfaCubugu'

const dugmeMetinleri = () => within(screen.getByRole('navigation', { name: 'Sayfalar' }))
  .getAllByRole('listitem').map(li => li.textContent)

describe('SayfaCubugu', () => {
  it('tek_sayfada_gizlenir', () => {
    const { container } = render(<SayfaCubugu sayfa={1} sayfaSayisi={1} onSayfa={() => {}} />)
    expect(container).toBeEmptyDOMElement()
    const ikinci = render(<SayfaCubugu sayfa={1} sayfaSayisi={0} onSayfa={() => {}} />)
    expect(ikinci.container).toBeEmptyDOMElement()
  })

  it('uzun_listede_uc_nokta', () => {
    render(<SayfaCubugu sayfa={6} sayfaSayisi={20} onSayfa={() => {}} />)
    expect(dugmeMetinleri()).toEqual(
      ['‹ Önceki', '1', '…', '4', '5', '6', '7', '8', '…', '20', 'Sonraki ›'])
    expect(screen.getByRole('button', { name: '6' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: '5' })).not.toHaveAttribute('aria-current')
  })

  it('kisa_listede_ve_uclarda_bosluk_yok', () => {
    const { unmount } = render(<SayfaCubugu sayfa={1} sayfaSayisi={5} onSayfa={() => {}} />)
    expect(dugmeMetinleri()).toEqual(['‹ Önceki', '1', '2', '3', '4', '5', 'Sonraki ›'])
    unmount()
    // Tek sayfalik bosluk "…" yerine sayfanin kendisiyle doldurulur
    const ikinci = render(<SayfaCubugu sayfa={4} sayfaSayisi={10} onSayfa={() => {}} />)
    expect(dugmeMetinleri()).toEqual(
      ['‹ Önceki', '1', '2', '3', '4', '5', '6', '…', '10', 'Sonraki ›'])
    ikinci.unmount()
    render(<SayfaCubugu sayfa={20} sayfaSayisi={20} onSayfa={() => {}} />)
    expect(dugmeMetinleri()).toEqual(['‹ Önceki', '1', '…', '18', '19', '20', 'Sonraki ›'])
    expect(screen.getByRole('button', { name: 'Sonraki ›' })).toBeDisabled()
  })

  it('onceki_ilk_sayfada_pasif', () => {
    render(<SayfaCubugu sayfa={1} sayfaSayisi={3} onSayfa={() => {}} />)
    expect(screen.getByRole('button', { name: '‹ Önceki' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Sonraki ›' })).toBeEnabled()
  })

  it('tiklama_onSayfa_cagirir', () => {
    const onSayfa = vi.fn()
    render(<SayfaCubugu sayfa={6} sayfaSayisi={20} onSayfa={onSayfa} />)
    fireEvent.click(screen.getByRole('button', { name: '8' }))
    expect(onSayfa).toHaveBeenLastCalledWith(8)
    fireEvent.click(screen.getByRole('button', { name: '‹ Önceki' }))
    expect(onSayfa).toHaveBeenLastCalledWith(5)
    fireEvent.click(screen.getByRole('button', { name: 'Sonraki ›' }))
    expect(onSayfa).toHaveBeenLastCalledWith(7)
    fireEvent.click(screen.getByRole('button', { name: '20' }))
    expect(onSayfa).toHaveBeenLastCalledWith(20)
    // Gecerli sayfaya tiklamak istek uretmez
    onSayfa.mockClear()
    fireEvent.click(screen.getByRole('button', { name: '6' }))
    expect(onSayfa).not.toHaveBeenCalled()
  })
})
