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

// Alti bolumun API'si ayni bicimde: liste, istatistik, cekim, sifirlama, disa aktarim.
// vi.mock dosya basina tasindigi icin yardimci da vi.hoisted ile tanimlanir.
const { bolumApi } = vi.hoisted(() => ({
  bolumApi: (liste, cekim, aktarim) => ({
    [liste]: vi.fn(), getStats: vi.fn(), [cekim]: vi.fn(), clearCache: vi.fn(), [aktarim]: vi.fn(),
  }),
}))

vi.mock('../services/api', () => ({
  newsApi: bolumApi('getNews', 'fetchNews', 'exportNews'),
  k8sApi: bolumApi('getK8s', 'fetchK8s', 'exportK8s'),
  sreApi: bolumApi('getSRE', 'fetchSRE', 'exportSRE'),
  devtoolsApi: bolumApi('getDevTools', 'fetchDevTools', 'exportDevTools'),
  aiApi: bolumApi('getAINews', 'fetchAINews', 'exportAINews'),
  cveApi: bolumApi('getCVEs', 'fetchCVEs', 'exportCVEs'),
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
  ['News', NewsComponent, newsApi, 'getNews', 'exportNews'],
  ['Kubernetes', KubernetesComponent, k8sApi, 'getK8s', 'exportK8s'],
  ['SRE', SREComponent, sreApi, 'getSRE', 'exportSRE'],
  ['DevTools', DevToolsComponent, devtoolsApi, 'getDevTools', 'exportDevTools'],
  ['AINews', AINewsComponent, aiApi, 'getAINews', 'exportAINews'],
  ['CVE', CVEComponent, cveApi, 'getCVEs', 'exportCVEs'],
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

  it.each(BOLUMLER)('%s raporunda govde kacislanir, satir sonu <br> olur', async (_ad, Bilesen, api, liste, aktarim) => {
    api[liste].mockResolvedValue({ data: { success: true, data: [] } })
    api.getStats.mockResolvedValue({ data: {
      success: true, total: 0, by_source: {}, by_severity: {}, by_category: {}, last_update: null,
    } })
    api[aktarim].mockResolvedValue({ data: { success: true, data: [kayit] } })

    render(<MemoryRouter><Bilesen /></MemoryRouter>)
    fireEvent.click(await screen.findByTitle(/HTML rapor olarak indir/))

    await waitFor(() => expect(raporlar).toHaveLength(1))
    const html = raporlar[0]
    expect(html).not.toMatch(/<script/i)
    expect(html).not.toMatch(/<img/i)
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;<br>ikinci satir &lt;img')
  })
})
