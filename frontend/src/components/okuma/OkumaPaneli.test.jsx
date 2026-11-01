import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import OkumaPaneli from './OkumaPaneli'

const EN_PARAGRAF = 'The vulnerability allows an attacker to execute arbitrary code on the server.'

const kayit = (ek = {}) => ({
  id: 1,
  ustBaslik: null,
  baslik: 'Örnek başlık',
  skor: null,
  rozetler: [],
  govdeTr: '',
  govdeOrijinal: '',
  kevMeta: null,
  tarih: '2026-10-30',
  kaynak: 'Örnek Kaynak',
  link: 'https://ornek.test/kayit',
  ekAlanlar: [],
  referanslar: [],
  ham: {},
  ...ek,
})

describe('OkumaPaneli', () => {
  it('varsayilan turkce, orijinal dugmeyle acilir ve kapanir', () => {
    render(<OkumaPaneli kayit={kayit({ govdeTr: 'Türkçe gövde metni.', govdeOrijinal: 'English body.' })} onKapat={vi.fn()} />)
    expect(screen.getByText('Türkçe gövde metni.')).toBeInTheDocument()
    expect(screen.queryByText('English body.')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Orijinali göster' }))
    expect(screen.getByText('English body.')).toBeInTheDocument()
    expect(screen.getByText('Türkçe gövde metni.')).toBeInTheDocument()
    const gizle = screen.getByRole('button', { name: 'Orijinali gizle' })
    expect(gizle).toHaveAttribute('aria-expanded', 'true')
    fireEvent.click(gizle)
    expect(screen.queryByText('English body.')).toBeNull()
  })

  it('PR adresi varsa gunluk PR etiketleri baglanti olur, orijinalde de', () => {
    const govde = (a) => `Feature (1)\n\n• ${a} (#143343 · @palnabarun · SIG Release)`
    render(<OkumaPaneli kayit={kayit({
      govdeTr: govde('Go 1.26 ile derleniyor.'),
      govdeOrijinal: govde('Built with Go 1.26.'),
      prAdresi: 'https://github.com/kubernetes/kubernetes/pull/',
    })} onKapat={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Orijinali göster' }))
    const baglantilar = screen.getAllByRole('link', { name: '#143343' })
    expect(baglantilar).toHaveLength(2)
    baglantilar.forEach(b => {
      expect(b).toHaveAttribute('href', 'https://github.com/kubernetes/kubernetes/pull/143343')
      expect(b).toHaveAttribute('rel', 'noopener noreferrer')
    })
    expect(baglantilar[0].closest('p')).toHaveTextContent('• Go 1.26 ile derleniyor. (#143343 · @palnabarun · SIG Release)')
  })

  it('PR adresi yoksa ayni etiket duz metin kalir', () => {
    render(<OkumaPaneli kayit={kayit({ govdeTr: '• Düzeltme yapıldı. (#5 · @ali · SIG Node)' })} onKapat={vi.fn()} />)
    expect(screen.queryByRole('link', { name: '#5' })).toBeNull()
    expect(screen.getByText('• Düzeltme yapıldı. (#5 · @ali · SIG Node)')).toBeInTheDocument()
  })

  it('ceviri yoksa orijinal ve uyari gosterilir', () => {
    render(<OkumaPaneli kayit={kayit({ govdeTr: '', govdeOrijinal: 'English body.' })} onKapat={vi.fn()} />)
    expect(screen.getByText('Çevrilmedi: orijinal metin')).toBeInTheDocument()
    expect(screen.getByText('English body.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Orijinali göster' })).toBeNull()
  })

  it('ingilizce kalan paragraf isaretlenir', () => {
    render(<OkumaPaneli kayit={kayit({ govdeTr: `Türkçe ilk paragraf.\n\n${EN_PARAGRAF}`, govdeOrijinal: `First paragraph.\n\n${EN_PARAGRAF}` })} onKapat={vi.fn()} />)
    const not = screen.getByText('Bu paragraf çevrilemedi')
    const paragraf = not.closest('.cevrilmedi')
    expect(paragraf).toHaveTextContent(EN_PARAGRAF)
    expect(paragraf).toHaveAttribute('lang', 'en')
    expect(screen.getByText('Türkçe ilk paragraf.')).not.toHaveClass('cevrilmedi')
    expect(screen.getAllByText('Bu paragraf çevrilemedi')).toHaveLength(1)
  })

  it('kev meta satiri', () => {
    render(<OkumaPaneli kayit={kayit({ govdeTr: 'Gövde.', kevMeta: { kevEklenme: '2026-10-20', sonTarih: '2026-11-10' } })} onKapat={vi.fn()} />)
    expect(screen.getByText("KEV'e eklenme: 2026-10-20")).toBeInTheDocument()
    expect(screen.getByText('Son işlem tarihi: 2026-11-10')).toBeInTheDocument()
  })

  it('kev meta son tarihsiz', () => {
    render(<OkumaPaneli kayit={kayit({ govdeTr: 'Gövde.', kevMeta: { kevEklenme: '2026-10-20', sonTarih: null } })} onKapat={vi.fn()} />)
    expect(screen.getByText("KEV'e eklenme: 2026-10-20")).toBeInTheDocument()
    expect(screen.queryByText(/Son işlem tarihi/)).toBeNull()
  })

  it('icerik yoksa bilgi verir', () => {
    render(<OkumaPaneli kayit={kayit()} onKapat={vi.fn()} />)
    expect(screen.getByText('İçerik bulunmuyor.')).toBeInTheDocument()
    expect(screen.queryByText('Çevrilmedi: orijinal metin')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Orijinali göster' })).toBeNull()
  })

  it('Esc onKapat cagirir', () => {
    const onKapat = vi.fn()
    render(<OkumaPaneli kayit={kayit({ govdeTr: 'Gövde.' })} onKapat={onKapat} />)
    // Tarayicidaki gercek olay: @restart/ui Esc'i code/keyCode ile tanir, yalniz key yetmez
    fireEvent.keyDown(document.activeElement, { key: 'Escape', code: 'Escape', keyCode: 27 })
    expect(onKapat).toHaveBeenCalledTimes(1)
  })

  it('Kapat dugmesi onKapat cagirir', () => {
    const onKapat = vi.fn()
    render(<OkumaPaneli kayit={kayit({ govdeTr: 'Gövde.' })} onKapat={onKapat} />)
    fireEvent.click(screen.getByRole('button', { name: 'Kapat' }))
    expect(onKapat).toHaveBeenCalledTimes(1)
  })

  it('kayit yoksa panel acilmaz', () => {
    render(<OkumaPaneli kayit={null} onKapat={vi.fn()} />)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('baslik alani: kimlik, baslik, skor, rozetler, kaynak ve tarih', () => {
    render(<OkumaPaneli kayit={kayit({
      ustBaslik: 'CVE-2026-1001', baslik: 'VPN ağ geçidinde RCE', skor: 9.8, govdeTr: 'Gövde.',
      rozetler: [{ metin: 'CISA KEV', tur: 'kev' }, { metin: 'CWE-78', tur: 'ur' }],
      ham: { translation_provider: 'gemini' },
    })} onKapat={vi.fn()} />)
    const panel = screen.getByRole('dialog', { name: 'VPN ağ geçidinde RCE' })
    expect(within(panel).getByText('CVE-2026-1001')).toBeInTheDocument()
    expect(within(panel).getByText('9.8').closest('.skor-kutusu')).toHaveClass('kritik')
    expect(within(panel).getByText('KRİTİK')).toBeInTheDocument()
    expect(within(panel).getByText('CISA KEV')).toHaveClass('rozet', 'kev')
    expect(within(panel).getByText('CWE-78')).toHaveClass('rozet', 'ur')
    expect(within(panel).getByText('Çeviri: Gemini')).toBeInTheDocument()
    expect(within(panel).getByText('Örnek Kaynak · 2026-10-30')).toBeInTheDocument()
  })

  it('tamamen cevrilmemis kayitta cevrilmedi rozeti uyariyla tekrarlanmaz', () => {
    render(<OkumaPaneli kayit={kayit({ govdeOrijinal: 'English body.', ham: { translation_provider: '', needs_translation: true } })} onKapat={vi.fn()} />)
    expect(screen.getAllByText('Çevrilmedi: orijinal metin')).toHaveLength(1)
  })

  it('ek alanlar ve tum referanslar listelenir; baglantilar guvenli', () => {
    const refler = ['https://a.test/1?x=1&y=2', 'https://a.test/2', 'http://a.test/3', 'https://a.test/4', 'javascript:alert(1)']
    render(<OkumaPaneli kayit={kayit({
      govdeTr: 'Gövde.',
      ekAlanlar: [{ etiket: 'Etkilenen ürünler', deger: 'Örnek VPN 7.0' }],
      referanslar: refler,
    })} onKapat={vi.fn()} />)
    expect(screen.getByText('Etkilenen ürünler')).toBeInTheDocument()
    expect(screen.getByText('Örnek VPN 7.0')).toBeInTheDocument()
    const ilk = screen.getByRole('link', { name: 'https://a.test/1?x=1&y=2' })
    expect(ilk).toHaveAttribute('href', 'https://a.test/1?x=1&y=2')
    expect(ilk).toHaveAttribute('target', '_blank')
    expect(ilk).toHaveAttribute('rel', 'noopener noreferrer')
    expect(screen.getByRole('link', { name: 'http://a.test/3' })).toBeInTheDocument()
    // guvenli olmayan adres metin olarak kalir, baglanti olmaz
    expect(screen.getByText('javascript:alert(1)').closest('a')).toBeNull()
    const kaynak = screen.getByRole('link', { name: /Orijinal kaynağa git/ })
    expect(kaynak).toHaveAttribute('href', 'https://ornek.test/kayit')
    expect(kaynak).toHaveAttribute('rel', 'noopener noreferrer')
  })

  it('guvenli olmayan kaynak adresi baglanti olmaz', () => {
    render(<OkumaPaneli kayit={kayit({ govdeTr: 'Gövde.', link: 'javascript:alert(1)' })} onKapat={vi.fn()} />)
    expect(screen.queryByRole('link', { name: /Orijinal kaynağa git/ })).toBeNull()
  })

  it('baska kayit acilinca orijinal yeniden gizlenir', () => {
    const { rerender } = render(<OkumaPaneli kayit={kayit({ govdeTr: 'Bir.', govdeOrijinal: 'One.' })} onKapat={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Orijinali göster' }))
    expect(screen.getByText('One.')).toBeInTheDocument()
    rerender(<OkumaPaneli kayit={kayit({ id: 2, link: 'https://ornek.test/2', govdeTr: 'İki.', govdeOrijinal: 'Two.' })} onKapat={vi.fn()} />)
    expect(screen.getByText('İki.')).toBeInTheDocument()
    expect(screen.queryByText('Two.')).toBeNull()
  })

  it('ayni kaydin yenilenmis nesnesinde orijinal acik kalir', () => {
    const { rerender } = render(<OkumaPaneli kayit={kayit({ govdeTr: 'Bir.', govdeOrijinal: 'One.' })} onKapat={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Orijinali göster' }))
    rerender(<OkumaPaneli kayit={kayit({ govdeTr: 'Bir.', govdeOrijinal: 'One.' })} onKapat={vi.fn()} />)
    expect(screen.getByText('One.')).toBeInTheDocument()
  })
})
