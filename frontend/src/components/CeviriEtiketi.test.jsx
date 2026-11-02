import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import CeviriEtiketi, { ceviriEtiketiHtml } from './CeviriEtiketi'

describe('CeviriEtiketi', () => {
  it('LibreTranslate kaydi sari uyari rozeti alir', () => {
    render(<CeviriEtiketi kayit={{ translation_provider: 'libretranslate' }} />)
    expect(screen.getByText('Makine çevirisi: LibreTranslate')).toBeInTheDocument()
  })
  it('LibreTranslate aciklamasi "2 saat" vaadi vermez, gun ici iyilestirmeyi soyler', () => {
    render(<CeviriEtiketi kayit={{ translation_provider: 'libretranslate' }} />)
    const baslik = screen.getByText('Makine çevirisi: LibreTranslate').getAttribute('title')
    expect(baslik).not.toContain('En geç 2 saat içinde')
    expect(baslik).toBe('Yerel LibreTranslate ile çevrildi; anlam hatası olabilir, orijinal metne bakın. Haberler ile kritik ve yüksek zafiyetler gün içinde Gemini ile iyileştirilir.')
    expect(ceviriEtiketiHtml({ translation_provider: 'libretranslate' })).not.toContain('En geç 2 saat içinde')
  })
  it('Gemini kaydi gri bilgi rozeti alir', () => {
    render(<CeviriEtiketi kayit={{ translation_provider: 'gemini' }} />)
    expect(screen.getByText('Çeviri: Gemini')).toBeInTheDocument()
  })
  it('OpenRouter ve DeepL kayitlari Gemini gibi gri bilgi rozeti alir (PR-C)', () => {
    render(<CeviriEtiketi kayit={{ translation_provider: 'openrouter' }} />)
    const openrouter = screen.getByText('Çeviri: OpenRouter')
    expect(openrouter).toHaveClass('bg-secondary')
    expect(openrouter.getAttribute('title')).toBe('OpenRouter ücretsiz modeliyle çevrildi.')
    render(<CeviriEtiketi kayit={{ translation_provider: 'deepl' }} />)
    const deepl = screen.getByText('Çeviri: DeepL')
    expect(deepl).toHaveClass('bg-secondary')
    expect(deepl.getAttribute('title')).toBe('DeepL API Free ile çevrildi.')
    expect(ceviriEtiketiHtml({ translation_provider: 'openrouter' })).toContain('Çeviri: OpenRouter')
    expect(ceviriEtiketiHtml({ translation_provider: 'deepl' })).toContain('background:#6c757d')
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
  it('hic deneme yapilmamis kayit da "Çevrilmedi" rozeti alir (metin Ingilizce gosteriliyor)', () => {
    // Bulgu 6 (2026-10-16): takili kuyrukta 42 Ingilizce baslik rozetsizdi; 10-21'de 16 kayit (deneme 0)
    render(<CeviriEtiketi kayit={{ translation_provider: '', needs_translation: true, translation_attempts: 0 }} />)
    expect(screen.getByText('Çevrilmedi: orijinal metin')).toBeInTheDocument()
  })
  it('html cikti da "Çevrilmedi" rozetini uretir', () => {
    expect(ceviriEtiketiHtml({ translation_provider: '', needs_translation: true, translation_attempts: 1 })).toContain('Çevrilmedi: orijinal metin')
  })
})
