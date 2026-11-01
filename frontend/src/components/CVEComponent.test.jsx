import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import CVEComponent from './CVEComponent'
import { cveApi } from '../services/api'

vi.mock('../services/api', () => ({
  cveApi: {
    getCVEs: vi.fn(),
    getStats: vi.fn(),
    fetchCVEs: vi.fn(),
    clearCache: vi.fn(),
    exportCVEs: vi.fn(),
  },
  istekHataMesaji: (err, varsayilan) => err.response?.data?.message || `${varsayilan}: ${err.message}`,
}))

const saatOnce = (sa) => new Date(Date.now() - sa * 3600 * 1000).toISOString()

const cve = (id, cveId, skor, ek = {}) => ({
  id,
  cve_id: cveId,
  cvss_score: skor,
  severity: 'Orta',
  turkish_title: `${cveId} - Başlık ${id}`,
  original_title: cveId,
  turkish_description: `Türkçe açıklama ${id}.`,
  original_description: `English description ${id}.`,
  cwe_ids: [],
  references: [],
  affected_products: '',
  source: 'NVD',
  link: `https://nvd.nist.gov/vuln/detail/${cveId}`,
  published_date: '2026-10-30',
  created_at: saatOnce(id),
  needs_translation: false,
  translation_provider: 'gemini',
  ...ek,
})

const KAYITLAR = [
  cve(1, 'CVE-2026-0001', 9.8, { turkish_title: 'CVE-2026-0001 - VPN ağ geçidinde uzaktan kod çalıştırma' }),
  cve(2, 'CVE-2026-0002', 7.5),
  cve(3, 'CVE-2026-0003', 5.0),
]

// Adres cubugu yerine: testte gecerli konumu okur
function Konum() {
  const { search } = useLocation()
  return <output data-testid="konum">{search}</output>
}

const sayfa = (giris = '/cve') => render(
  <MemoryRouter initialEntries={[giris]}>
    <Routes>
      <Route path="/cve" element={<><CVEComponent /><Konum /></>} />
    </Routes>
  </MemoryRouter>,
)

describe('CVEComponent', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
    cveApi.getCVEs.mockResolvedValue({ data: { success: true, data: KAYITLAR } })
    cveApi.getStats.mockResolvedValue({ data: {
      success: true, total: 11527, by_source: { NVD: 1868, CIRCL: 90 },
      by_severity: { Kritik: 1495, Orta: 4977 }, last_update: saatOnce(1),
    } })
  })

  it('satira tiklayinca panel acilir ve adres degisir', async () => {
    sayfa()
    const baslik = await screen.findByText('VPN ağ geçidinde uzaktan kod çalıştırma')
    expect(screen.queryByRole('dialog')).toBeNull()
    fireEvent.click(baslik.closest('button'))
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('CVE-2026-0001')).toBeInTheDocument()
    expect(within(panel).getByText('Türkçe açıklama 1.')).toBeInTheDocument()
    expect(screen.getByTestId('konum')).toHaveTextContent('?kayit=1')
  })

  it('ceviri bekleyen CVE satirinda Cevrilmedi rozeti ve lang=en olur', async () => {
    const ingilizce = 'CVE-2026-0004 - Remote code execution in widget server'
    cveApi.getCVEs.mockResolvedValue({ data: { success: true, data: [
      ...KAYITLAR,
      cve(4, 'CVE-2026-0004', 8.1, {
        turkish_title: ingilizce, original_title: ingilizce, needs_translation: true, translation_provider: null,
      }),
    ] } })
    sayfa()
    const baslik = await screen.findByText('Remote code execution in widget server')
    const satir = baslik.closest('button')
    expect(within(satir).getByText('Çevrilmedi: orijinal metin')).toBeInTheDocument()
    expect(baslik.closest('[lang]')).toHaveAttribute('lang', 'en')
    const cevrili = screen.getByText('Başlık 2').closest('button')
    expect(within(cevrili).queryByText('Çevrilmedi: orijinal metin')).toBeNull()
    expect(screen.getByText('Başlık 2').closest('[lang]')).toHaveAttribute('lang', 'tr')
  })

  it('siddet filtresi sayaci gunceller', async () => {
    sayfa()
    expect(await screen.findByText('3 CVE gösteriliyor')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Kritik' }))
    expect(screen.getByText('1 / 3 CVE gösteriliyor')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Kritik' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByText('CVE-2026-0002')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Tümü' }))
    expect(screen.getByText('3 CVE gösteriliyor')).toBeInTheDocument()
  })

  it('paylasilan adres paneli acar, bilinmeyen kayit kapali kalir', async () => {
    const { unmount } = sayfa('/cve?kayit=2')
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('CVE-2026-0002')).toBeInTheDocument()
    unmount()

    sayfa('/cve?kayit=999')
    expect(await screen.findByText('3 CVE gösteriliyor')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('Esc paneli kapatir ve parametreyi siler', async () => {
    sayfa('/cve?kayit=1')
    const panel = await screen.findByRole('dialog')
    fireEvent.keyDown(panel, { key: 'Escape', code: 'Escape', keyCode: 27 })
    await waitFor(() => expect(screen.getByTestId('konum')).toBeEmptyDOMElement())
  })

  it('Cek sunucunun 429 mesajini gosterir', async () => {
    cveApi.fetchCVEs.mockRejectedValue({
      message: 'Request failed with status code 429',
      response: { status: 429, data: { message: 'Çok sık çekim: 12 dakika sonra tekrar deneyin.' } },
    })
    sayfa()
    await screen.findByText('3 CVE gösteriliyor')
    fireEvent.click(screen.getByRole('button', { name: /^Çek/ }))
    expect(await screen.findByText('Çok sık çekim: 12 dakika sonra tekrar deneyin.')).toBeInTheDocument()
    expect(cveApi.fetchCVEs).toHaveBeenCalledWith({ days: 7, sources: ['NVD', 'GitHub Advisory', 'Tenable', 'NVD Güncel', 'CISA KEV'] })
  })

  it('veritabani istatistiklerini gosterir', async () => {
    sayfa()
    expect(await screen.findByText(/Toplam 11\.527 kayıt/)).toBeInTheDocument()
    expect(screen.getByText('Kritik 1.495')).toBeInTheDocument()
  })
})
