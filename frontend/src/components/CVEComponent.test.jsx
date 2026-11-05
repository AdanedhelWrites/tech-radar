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

  it('paylasilan adres paneli acar, bilinmeyen kayit kapali kalir', async () => {
    const { unmount } = sayfa('/cve?kayit=2')
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('CVE-2026-0002')).toBeInTheDocument()
    unmount()

    sayfa('/cve?kayit=999')
    expect(await screen.findByText('Son 7 günde 3 kayıt · 1–3 gösteriliyor')).toBeInTheDocument()
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
    await screen.findByText('Son 7 günde 3 kayıt · 1–3 gösteriliyor')
    fireEvent.click(screen.getByRole('button', { name: /^Çek/ }))
    expect(await screen.findByText('Çok sık çekim: 12 dakika sonra tekrar deneyin.')).toBeInTheDocument()
    expect(cveApi.fetchCVEs).toHaveBeenCalledWith({ days: 7, sources: ['NVD', 'GitHub Advisory', 'Tenable', 'NVD Güncel', 'CISA KEV'] })
  })

  it('veritabani istatistiklerini gosterir', async () => {
    sayfa()
    expect(await screen.findByText(/Toplam 11\.527 kayıt/)).toBeInTheDocument()
    expect(screen.getByText('Kritik 1.495')).toBeInTheDocument()
  })

  it('onem_sunucuya_gider', async () => {
    // 2026-11-05: onem istemcide 100 kaydin icinde degil, sunucuda butun kayitlarda suzulur
    const kritikler = Array.from({ length: 25 }, (_, i) => cve(100 + i, `CVE-2026-1${String(i).padStart(3, '0')}`, 9.5))
    cveApi.getCVEs.mockImplementation(async (params) => (params.onem === 'kritik'
      ? { data: { success: true, data: kritikler, toplam: 1559, sayfa: 1, sayfa_sayisi: 63, boyut: 25 } }
      : { data: { success: true, data: KAYITLAR, toplam: 3, sayfa: 1, sayfa_sayisi: 1, boyut: 25 } }))
    sayfa('/cve?sayfa=2')
    await screen.findByText('VPN ağ geçidinde uzaktan kod çalıştırma')
    const grup = screen.getByRole('group', { name: 'CVSS şiddet filtresi' })
    expect(within(grup).getByRole('button', { name: 'Tümü' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(within(grup).getByRole('button', { name: 'Kritik' }))
    // Adreste onem yazilir, sayfa silinir
    expect(screen.getByTestId('konum')).toHaveTextContent(/^\?onem=kritik$/)
    expect(within(grup).getByRole('button', { name: 'Kritik' })).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => expect(cveApi.getCVEs).toHaveBeenLastCalledWith(
      { gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25, onem: 'kritik' }))
    expect(await screen.findByText('Son 7 günde 1.559 kayıt · 1–25 gösteriliyor')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Sayfalar' })).toBeInTheDocument()
    // Tumu onemi adresten siler
    fireEvent.click(within(grup).getByRole('button', { name: 'Tümü' }))
    expect(screen.getByTestId('konum')).toBeEmptyDOMElement()
    await waitFor(() => expect(cveApi.getCVEs).toHaveBeenLastCalledWith({ gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25 }))
  })

  it('cvss_siralamasi_yalniz_zafiyetlerde', async () => {
    sayfa()
    await screen.findByText('VPN ağ geçidinde uzaktan kod çalıştırma')
    const sirala = screen.getByRole('combobox', { name: 'Sırala' })
    expect(within(sirala).getAllByRole('option').map(o => o.textContent)).toEqual(['En yeni', 'En eski', 'En yüksek CVSS'])
    const donem = screen.getByRole('combobox', { name: 'Dönem' })
    expect(within(donem).getAllByRole('option').map(o => o.textContent))
      .toEqual(['Son 1 gün', 'Son 3 gün', 'Son 7 gün', 'Son 14 gün', 'Son 30 gün', 'Tümü'])
    fireEvent.change(sirala, { target: { value: 'cvss' } })
    expect(screen.getByTestId('konum')).toHaveTextContent(/^\?sirala=cvss$/)
    await waitFor(() => expect(cveApi.getCVEs).toHaveBeenLastCalledWith({ gun: 7, sirala: 'cvss', sayfa: 1, boyut: 25 }))
    fireEvent.change(donem, { target: { value: 'tumu' } })
    await waitFor(() => expect(cveApi.getCVEs).toHaveBeenLastCalledWith({ sirala: 'cvss', sayfa: 1, boyut: 25 }))
    expect(await screen.findByText('3 kayıt · 1–3 gösteriliyor')).toBeInTheDocument()
  })

  it('adresten_acilis', async () => {
    cveApi.getCVEs.mockImplementation(async (params) => ({
      data: { success: true, data: KAYITLAR, toplam: 40, sayfa: params.sayfa, sayfa_sayisi: 2, boyut: 25 },
    }))
    sayfa('/cve?sirala=cvss&sayfa=2')
    expect(await screen.findByText('Son 7 günde 40 kayıt · 26–28 gösteriliyor')).toBeInTheDocument()
    expect(cveApi.getCVEs).toHaveBeenCalledWith({ gun: 7, sirala: 'cvss', sayfa: 2, boyut: 25 })
    expect(screen.getByRole('combobox', { name: 'Sırala' })).toHaveValue('cvss')
    expect(screen.getByRole('combobox', { name: 'Dönem' })).toHaveValue('7')
    const cubuk = screen.getByRole('navigation', { name: 'Sayfalar' })
    expect(within(cubuk).getByRole('button', { name: '2' })).toHaveAttribute('aria-current', 'page')
  })

  it('kaynak_secimi_listeyi_suzer_ve_ceker', async () => {
    cveApi.fetchCVEs.mockResolvedValue({ data: { success: true } })
    sayfa(`/cve?kaynak=${encodeURIComponent('Uydurma,CISA KEV')}`)
    await screen.findByText('VPN ağ geçidinde uzaktan kod çalıştırma')
    // Bilinmeyen kaynak istege gitmez; liste de Cek de ayni kumeyi kullanir
    expect(cveApi.getCVEs).toHaveBeenLastCalledWith({ gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25, kaynak: 'CISA KEV' })
    expect(screen.getByRole('button', { name: 'Kaynaklar 1/5' })).toBeInTheDocument()
    fireEvent.change(screen.getByRole('combobox', { name: 'Dönem' }), { target: { value: '30' } })
    fireEvent.click(screen.getByRole('button', { name: /^Çek/ }))
    await waitFor(() => expect(cveApi.fetchCVEs).toHaveBeenCalledWith({ days: 15, sources: ['CISA KEV'] }))
    await waitFor(() => expect(cveApi.getStats).toHaveBeenCalledTimes(2))
  })

  it('gecersiz_onem_istege_gitmez', async () => {
    sayfa('/cve?onem=uydurma&sirala=cvss')
    await screen.findByText('VPN ağ geçidinde uzaktan kod çalıştırma')
    expect(cveApi.getCVEs).toHaveBeenCalledTimes(1)
    expect(cveApi.getCVEs).toHaveBeenCalledWith({ gun: 7, sirala: 'cvss', sayfa: 1, boyut: 25 })
    const grup = screen.getByRole('group', { name: 'CVSS şiddet filtresi' })
    expect(within(grup).getByRole('button', { name: 'Tümü' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('cubuk_basliklari_zafiyetlere_ozgu', async () => {
    sayfa('/cve?gun=30')
    await screen.findByText('VPN ağ geçidinde uzaktan kod çalıştırma')
    expect(screen.getByRole('button', { name: /HTML rapor/ })).toHaveAttribute('title', 'CVE zafiyetlerini HTML rapor olarak indir')
    expect(screen.getByRole('button', { name: /Önbelleği temizle/ })).toHaveAttribute('title', 'Tüm CVE verilerini sil ve sıfırla')
    // Cek en fazla 15 gun ceker; baslik da bunu soyler
    expect(screen.getByRole('button', { name: /^Çek/ })).toHaveAttribute('title', 'Seçili kaynaklardan son 15 günün CVE kayıtlarını çek')
  })

  it('hata_sonrasi_sayim_gizlenir', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    cveApi.getCVEs.mockImplementation(async (params) => {
      if (params.sirala === 'eski') throw new Error('Network Error')
      return { data: { success: true, data: KAYITLAR, toplam: 3, sayfa: 1, sayfa_sayisi: 1, boyut: 25 } }
    })
    sayfa()
    await screen.findByText('Son 7 günde 3 kayıt · 1–3 gösteriliyor')
    fireEvent.change(screen.getByRole('combobox', { name: 'Sırala' }), { target: { value: 'eski' } })
    expect(await screen.findByText('CVE verileri yüklenirken hata oluştu')).toBeInTheDocument()
    expect(screen.queryByText(/gösteriliyor/)).toBeNull()
    vi.restoreAllMocks()
  })

  it('temizle_paneli_kapatir_ve_listeyi_yeniler', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    cveApi.clearCache.mockResolvedValue({ data: { success: true } })
    sayfa('/cve?kayit=1')
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    cveApi.getCVEs.mockResolvedValue({ data: { success: true, data: [], toplam: 0, sayfa: 1, sayfa_sayisi: 1, boyut: 25 } })
    cveApi.getStats.mockResolvedValue({ data: { success: true, total: 0, by_source: {}, by_severity: {}, last_update: null } })
    fireEvent.click(screen.getByRole('button', { name: /Önbelleği temizle/ }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(await screen.findByText('CVE listesi boş. Kayıt almak için "Çek" düğmesini kullanın.')).toBeInTheDocument()
    vi.restoreAllMocks()
  })

  it('rapor_gecerli_filtreyle_cvss_ve_kev_rozetleriyle', async () => {
    const raporlar = []
    vi.stubGlobal('Blob', class {
      constructor(parcalar) { raporlar.push(parcalar.join('')) }
    })
    URL.createObjectURL = vi.fn(() => 'blob:rapor')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    // kev: ceviri bekliyor (saglayici yok); skorsuz: severity metni; dusuk: CVSS < 4 de renkli
    const kev = cve(5, 'CVE-2026-0005', 8.8, {
      source: 'CISA KEV', severity: 'Yüksek', needs_translation: true, translation_provider: null,
    })
    const skorsuz = cve(6, 'CVE-2026-0006', null, { severity: 'Bilinmiyor' })
    const dusuk = cve(7, 'CVE-2026-0007', 3.1, { severity: 'Düşük', translation_provider: 'libretranslate' })
    const raporKayitlari = [KAYITLAR[0], kev, skorsuz, dusuk]
    cveApi.getCVEs.mockImplementation(async (params) => ({
      data: { success: true, data: params.boyut === 100 ? raporKayitlari : KAYITLAR, toplam: 4, sayfa: 1, sayfa_sayisi: 1, boyut: params.boyut },
    }))
    sayfa('/cve?onem=yuksek&sirala=cvss&sayfa=3')
    await screen.findByText('VPN ağ geçidinde uzaktan kod çalıştırma')
    fireEvent.click(screen.getByTitle(/HTML rapor olarak indir/))
    await waitFor(() => expect(raporlar).toHaveLength(1))
    expect(cveApi.getCVEs).toHaveBeenCalledWith({ gun: 7, sirala: 'cvss', sayfa: 1, boyut: 100, onem: 'yuksek' })
    const html = raporlar[0]
    expect(html).toContain('<span class="ek-rozet cveid">CVE-2026-0005</span>')
    expect(html).toContain('<span class="ek-rozet yuksek">CVSS 8.8</span>')
    expect(html).toContain('<span class="ek-rozet kev">CISA KEV</span>')
    expect(html).toContain('<span class="ek-rozet kritik">CVSS 9.8</span>')
    expect(html).toContain('<span class="ek-rozet skorsuz">Bilinmiyor</span>')
    expect(html).toContain('<span class="ek-rozet dusuk">CVSS 3.1</span>')
    // Ceviri etiketi (2026-11-05 oncesi CVE raporundaki ceviriEtiketiHtml karsiligi)
    expect(html).toContain('<span class="ek-rozet ceviri">Çeviri: Gemini</span>')
    expect(html).toContain('<span class="ek-rozet ceviri cevrilmedi">Çevrilmedi: orijinal metin</span>')
    expect(html).toContain('<span class="ek-rozet ceviri uyari">Makine çevirisi: LibreTranslate</span>')
    expect(html).toMatch(/\.ek-rozet\.ceviri \{/)
    expect(html).toMatch(/\.ek-rozet\.dusuk \{/)
    expect(html).toContain('Son 7 gün · En yüksek CVSS · Yüksek')
    expect(html.match(/class="article"/g)).toHaveLength(4)
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })
})
