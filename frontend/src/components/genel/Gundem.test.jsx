import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Gundem from './Gundem'
import { haberOkumaKaydi } from '../../utils/okumaKaydi'

const saatOnce = (sa) => new Date(Date.now() - sa * 3600 * 1000).toISOString()

const olay = (ek = {}, kayitEk = {}) => ({
  bolum: 'news',
  kayit: {
    id: 7, turkish_title: 'Büyük veri sızıntısı', original_title: 'Big data leak', source: 'BleepingComputer',
    link: 'https://ornek.test/7', created_at: saatOnce(30), translation_provider: 'gemini', needs_translation: false,
    ...kayitEk,
  },
  kaynak_sayisi: 1,
  kaynaklar: ['BleepingComputer'],
  makale_sayisi: 1,
  bolumler: ['news'],
  puan: 1,
  ilk: saatOnce(30),
  son: saatOnce(30),
  ...ek,
})

describe('Gundem', () => {
  it('cok_kaynakli_olayda_rozet', () => {
    const kaynaklar = ['A', 'B', 'C', 'D', 'E', 'F']
    render(<Gundem olaylar={[olay({ kaynak_sayisi: 6, kaynaklar, makale_sayisi: 7 })]} hata={false} onSec={() => {}} />)
    const rozet = screen.getByText('6 kaynak')
    expect(rozet).toHaveAttribute('title', 'A, B, C, D, E, F')
  })

  it('tek_kaynakta_rozet_yok', () => {
    render(<Gundem olaylar={[olay()]} hata={false} onSec={() => {}} />)
    expect(screen.queryByText(/ kaynak$/)).toBeNull()
  })

  it('alt_satir_bolum_kaynak_zaman', () => {
    // Zaman olayin son'u: temsilci 30 saat once, olayin en yeni makalesi 2 saat once
    render(<Gundem olaylar={[olay({ son: saatOnce(2) })]} hata={false} onSec={() => {}} />)
    const alt = screen.getByText(/Siber Güvenlik/)
    expect(alt).toHaveTextContent('Siber Güvenlik · BleepingComputer · 2 sa önce')
  })

  it('tiklama_temsilciyi_okuma_panelinde_acar', () => {
    const o = olay({ bolum: 'kubernetes' })
    const onSec = vi.fn()
    render(<Gundem olaylar={[o]} hata={false} onSec={onSec} />)
    fireEvent.click(screen.getByText('Büyük veri sızıntısı').closest('button'))
    expect(onSec).toHaveBeenCalledWith(haberOkumaKaydi(o.kayit, 'kubernetes'))
  })

  it('gundem_hatasi_karta_yansir', () => {
    render(<Gundem olaylar={null} hata onSec={() => {}} />)
    expect(screen.getByText('Gündem bilgisi alınamadı.')).toBeInTheDocument()
  })
})
