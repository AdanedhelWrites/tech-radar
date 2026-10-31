import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import BolumSayfasi from './BolumSayfasi'

const saatOnce = (sa) => new Date(Date.now() - sa * 3600 * 1000).toISOString()

const haber = (id, ek = {}) => ({
  id,
  source: 'The Hacker News',
  original_title: `Original title ${id}`,
  turkish_title: `Türkçe başlık ${id}`,
  original_description: `Original description ${id}.`,
  turkish_description: `Türkçe açıklama ${id}.`,
  turkish_summary: '',
  link: `https://ornek.test/haber/${id}`,
  date: '2026-10-30',
  published_date: '2026-10-29',
  created_at: saatOnce(id),
  needs_translation: false,
  translation_provider: 'gemini',
  ...ek,
})

const CEVRILMEMIS = haber(3, {
  turkish_title: '',
  turkish_description: '',
  original_title: 'Untranslated headline about ransomware',
  needs_translation: true,
  translation_provider: null,
})

const KAYITLAR = [haber(1), haber(2), CEVRILMEMIS]

// Adres cubugu yerine: testte gecerli konumu okur
function Konum() {
  const { search } = useLocation()
  return <output data-testid="konum">{search}</output>
}

const sayfa = (ozellikler = {}, giris = '/news') => render(
  <MemoryRouter initialEntries={[giris]}>
    <Routes>
      <Route
        path="/news"
        element={(
          <>
            <BolumSayfasi bolum="news" baslik="Siber Güvenlik" kayitlar={KAYITLAR} yukleniyor={false} cubuk={null} {...ozellikler} />
            <Konum />
          </>
        )}
      />
    </Routes>
  </MemoryRouter>,
)

describe('BolumSayfasi', () => {
  it('kayitlari listeler', () => {
    sayfa({ cubuk: <div>cubuk yuvasi</div> })
    expect(screen.getByRole('heading', { name: 'Siber Güvenlik' })).toBeInTheDocument()
    expect(screen.getByText('cubuk yuvasi')).toBeInTheDocument()
    expect(screen.getByText('Türkçe başlık 1')).toBeInTheDocument()
    expect(screen.getByText('Türkçe başlık 2')).toBeInTheDocument()
    expect(screen.getByText('3 kayıt gösteriliyor')).toBeInTheDocument()
    // Satirda kaynak ve created_at'ten goreli zaman
    const satir = screen.getByText('Türkçe başlık 1').closest('button')
    expect(within(satir).getByText('The Hacker News')).toBeInTheDocument()
    expect(within(satir).getByText('1 sa önce')).toBeInTheDocument()
  })

  it('tiklaninca panel acilir ve adres degisir', async () => {
    sayfa()
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(screen.getByText('Türkçe başlık 2').closest('button'))
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('Türkçe açıklama 2.')).toBeInTheDocument()
    expect(screen.getByTestId('konum')).toHaveTextContent('?kayit=2')
  })

  it('cevrilmemis kayitta orijinal baslik ve uyari rozeti', () => {
    sayfa()
    const satir = screen.getByText('Untranslated headline about ransomware').closest('button')
    expect(within(satir).getByText('Çevrilmedi: orijinal metin')).toBeInTheDocument()
    // Cevrilmis kayitlarda bu rozet yok
    expect(screen.getAllByText('Çevrilmedi: orijinal metin')).toHaveLength(1)
  })

  it('news bolumunde tarih date alanindan okunur', async () => {
    sayfa({}, '/news?kayit=1')
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('The Hacker News · 2026-10-30')).toBeInTheDocument()
    expect(within(panel).queryByText(/2026-10-29/)).toBeNull()
  })

  it('diger bolumlerde tarih published_date alanindan okunur', async () => {
    sayfa({ bolum: 'sre', baslik: 'SRE' }, '/news?kayit=1')
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('The Hacker News · 2026-10-29')).toBeInTheDocument()
  })

  it('bolume ozgu bilgi rozetleri satirda gorunur', () => {
    const k8s = [haber(1, { category: 'security', version: 'v1.34.1' })]
    sayfa({ bolum: 'kubernetes', baslik: 'Kubernetes', kayitlar: k8s })
    const satir = screen.getByText('Türkçe başlık 1').closest('button')
    expect(within(satir).getByText('Güvenlik')).toHaveClass('rozet', 'bilgi')
    expect(within(satir).getByText('v1.34.1')).toHaveClass('rozet', 'bilgi')
  })

  it('filtre sayaci gunceller, filtre disi kalan secim acik kalir', async () => {
    const filtre = (k) => k.id !== 2
    sayfa({ filtre }, '/news?kayit=2')
    expect(screen.getByText('2 / 3 kayıt gösteriliyor')).toBeInTheDocument()
    const liste = screen.getByRole('list')
    expect(within(liste).getAllByRole('listitem')).toHaveLength(2)
    expect(within(liste).queryByText('Türkçe başlık 2')).toBeNull()
    // Secim tum liste uzerinden cozulur: filtre paneli kapatmaz
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('Türkçe açıklama 2.')).toBeInTheDocument()
  })

  it('bos, yukleniyor ve eslesmeyen filtre durumlari', () => {
    const { unmount } = sayfa({ kayitlar: [], yukleniyor: true })
    expect(screen.getByText('Kayıtlar yükleniyor…')).toBeInTheDocument()
    unmount()
    const ikinci = sayfa({ kayitlar: [] })
    expect(screen.getByText('Liste boş. Kayıt almak için "Çek" düğmesini kullanın.')).toBeInTheDocument()
    ikinci.unmount()
    sayfa({ filtre: () => false })
    expect(screen.getByText('Bu filtreyle eşleşen kayıt bulunamadı.')).toBeInTheDocument()
  })

  it('istatistik ve dagilim baslikta gosterilir', () => {
    sayfa({ istatistik: { total: 1234, last_update: saatOnce(2) }, dagilim: [['Sürüm', 61], ['Blog', 4]] })
    expect(screen.getByText('Toplam 1.234 kayıt')).toBeInTheDocument()
    expect(screen.getByText('Son güncelleme 2 sa önce')).toBeInTheDocument()
    expect(screen.getByText('Sürüm 61')).toBeInTheDocument()
  })

  it('Esc paneli kapatir ve parametreyi siler', async () => {
    sayfa({}, '/news?kayit=1')
    const panel = await screen.findByRole('dialog')
    fireEvent.keyDown(panel, { key: 'Escape', code: 'Escape', keyCode: 27 })
    await waitFor(() => expect(screen.getByTestId('konum')).toBeEmptyDOMElement())
  })
})
