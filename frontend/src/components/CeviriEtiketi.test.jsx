import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import CeviriEtiketi, { ceviriEtiketiHtml } from './CeviriEtiketi'

describe('CeviriEtiketi', () => {
  it('LibreTranslate kaydi sari uyari rozeti alir', () => {
    render(<CeviriEtiketi kayit={{ translation_provider: 'libretranslate' }} />)
    expect(screen.getByText('Makine çevirisi: LibreTranslate')).toBeInTheDocument()
  })
  it('Gemini kaydi gri bilgi rozeti alir', () => {
    render(<CeviriEtiketi kayit={{ translation_provider: 'gemini' }} />)
    expect(screen.getByText('Çeviri: Gemini')).toBeInTheDocument()
  })
  it('saglayicisiz ve ceviri beklemeyen kayit rozet almaz; kayit yoksa cokmez', () => {
    const { container } = render(<CeviriEtiketi kayit={{ translation_provider: '', needs_translation: false }} />)
    expect(container).toBeEmptyDOMElement()
    expect(render(<CeviriEtiketi />).container).toBeEmptyDOMElement()
  })
  it('html cikti saglayiciya gore rozet uretir, bilinmeyen icin bos', () => {
    expect(ceviriEtiketiHtml({ translation_provider: 'gemini' })).toContain('Çeviri: Gemini')
    expect(ceviriEtiketiHtml({ translation_provider: 'x' })).toBe('')
    expect(ceviriEtiketiHtml(undefined)).toBe('')
  })
  it('saglayicisiz ama ceviri bekleyen kayit "Çevrilmedi" rozeti alir', () => {
    render(<CeviriEtiketi kayit={{ translation_provider: '', needs_translation: true, translation_attempts: 1 }} />)
    expect(screen.getByText('Çevrilmedi: orijinal metin')).toBeInTheDocument()
  })
  it('hic deneme yapilmamis taze kayit "Çevrilmedi" rozeti almaz', () => {
    const kayit = { translation_provider: '', needs_translation: true, translation_attempts: 0 }
    expect(render(<CeviriEtiketi kayit={kayit} />).container).toBeEmptyDOMElement()
    expect(ceviriEtiketiHtml(kayit)).toBe('')
  })
  it('html cikti da "Çevrilmedi" rozetini uretir', () => {
    expect(ceviriEtiketiHtml({ translation_provider: '', needs_translation: true, translation_attempts: 1 })).toContain('Çevrilmedi: orijinal metin')
  })
})
