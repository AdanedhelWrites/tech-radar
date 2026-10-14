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
})
