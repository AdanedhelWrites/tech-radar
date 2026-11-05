import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import NewsComponent from './NewsComponent'
import KubernetesComponent from './KubernetesComponent'
import SREComponent from './SREComponent'
import DevToolsComponent from './DevToolsComponent'
import AINewsComponent from './AINewsComponent'
import CVEComponent from './CVEComponent'
import { newsApi, k8sApi, sreApi, devtoolsApi, aiApi, cveApi } from '../services/api'

// Alti bolumun API'si ayni bicimde: liste, istatistik, cekim, sifirlama.
// vi.mock dosya basina tasindigi icin yardimci da vi.hoisted ile tanimlanir.
const { bolumApi } = vi.hoisted(() => ({
  bolumApi: (liste, cekim) => ({
    [liste]: vi.fn(), getStats: vi.fn(), [cekim]: vi.fn(), clearCache: vi.fn(),
  }),
}))

vi.mock('../services/api', () => ({
  newsApi: bolumApi('getNews', 'fetchNews'),
  k8sApi: bolumApi('getK8s', 'fetchK8s'),
  sreApi: bolumApi('getSRE', 'fetchSRE'),
  devtoolsApi: bolumApi('getDevTools', 'fetchDevTools'),
  aiApi: bolumApi('getAINews', 'fetchAINews'),
  cveApi: bolumApi('getCVEs', 'fetchCVEs'),
  istekHataMesaji: (err, varsayilan) => `${varsayilan}: ${err.message}`,
}))

// Ucuncu taraf feed'den gelmis gibi zararli govde (2026-10-31 oncesi raporda ham yaziliyordu)
const ZARARLI_GOVDE = '<script>alert(1)</script>\nikinci satir <img src=x onerror="alert(2)">'

const kayit = {
  id: 1,
  cve_id: 'CVE-2026-0001',
  severity: 'Orta',
  cvss_score: 5.0,
  source: 'Kaynak',
  version: 'v1.0',
  turkish_title: 'Başlık',
  original_title: 'Title',
  turkish_description: ZARARLI_GOVDE,
  original_description: ZARARLI_GOVDE,
  turkish_summary: ZARARLI_GOVDE,
  link: 'https://ornek.test/haber',
  date: '2026-10-30',
  published_date: '2026-10-30',
  created_at: '2026-10-30T10:00:00Z',
  needs_translation: false,
  translation_provider: 'gemini',
}

const BOLUMLER = [
  ['News', NewsComponent, newsApi, 'getNews'],
  ['Kubernetes', KubernetesComponent, k8sApi, 'getK8s'],
  ['SRE', SREComponent, sreApi, 'getSRE'],
  ['DevTools', DevToolsComponent, devtoolsApi, 'getDevTools'],
  ['AINews', AINewsComponent, aiApi, 'getAINews'],
  ['CVE', CVEComponent, cveApi, 'getCVEs'],
]

describe('HTML rapor disa aktarimi', () => {
  let raporlar

  beforeEach(() => {
    vi.clearAllMocks()
    raporlar = []
    // Blob icerigini yakalar; indirme tiklamasi jsdom'da gezinme denemesin
    vi.stubGlobal('Blob', class {
      constructor(parcalar) { raporlar.push(parcalar.join('')) }
    })
    URL.createObjectURL = vi.fn(() => 'blob:rapor')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it.each(BOLUMLER)('%s raporunda govde kacislanir, satir sonu <br> olur', async (_ad, Bilesen, api, liste) => {
    // 2026-11-05: alti bolum raporu da liste ucundan (gecerli filtreyle, boyut=100) alir.
    api[liste].mockResolvedValue({ data: { success: true, data: [kayit] } })
    api.getStats.mockResolvedValue({ data: {
      success: true, total: 0, by_source: {}, by_severity: {}, by_category: {}, last_update: null,
    } })

    render(<MemoryRouter><Bilesen /></MemoryRouter>)
    fireEvent.click(await screen.findByTitle(/HTML rapor olarak indir/))

    await waitFor(() => expect(raporlar).toHaveLength(1))
    const html = raporlar[0]
    expect(html).not.toMatch(/<script/i)
    expect(html).not.toMatch(/<img/i)
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;<br>ikinci satir &lt;img')
    // 500'u asmayan raporda kesme notu yok
    expect(html).not.toContain('İlk 500 kayıt')
    expect(api[liste]).toHaveBeenCalledWith(expect.objectContaining({ sayfa: 1, boyut: 100 }))
  })

  it('k8s_rapor_govdesinde_girinti_korunur', async () => {
    // Degisiklik gunlugu girintisi (2026-11-05 oncesi K8s raporundaki white-space: pre-wrap)
    for (const [Bilesen, api, liste] of [[KubernetesComponent, k8sApi, 'getK8s'], [NewsComponent, newsApi, 'getNews']]) {
      api[liste].mockResolvedValue({ data: { success: true, data: [kayit] } })
      api.getStats.mockResolvedValue({ data: { success: true, total: 0, by_source: {}, last_update: null } })
      const { unmount } = render(<MemoryRouter><Bilesen /></MemoryRouter>)
      fireEvent.click(await screen.findByTitle(/HTML rapor olarak indir/))
      await waitFor(() => expect(raporlar).toHaveLength(Bilesen === KubernetesComponent ? 1 : 2))
      unmount()
    }
    expect(raporlar[0]).toMatch(/\.article \.content \{[^}]*white-space: pre-wrap/)
    expect(raporlar[1]).not.toContain('pre-wrap')
  })
})
