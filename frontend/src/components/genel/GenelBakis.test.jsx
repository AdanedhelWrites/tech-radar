import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import GenelBakis from './GenelBakis'
import { ozetApi, newsApi, k8sApi, sreApi, devtoolsApi, aiApi, saglikApi } from '../../services/api'

vi.mock('../../services/api', () => ({
  ozetApi: { getOzet: vi.fn() },
  newsApi: { getNews: vi.fn() },
  k8sApi: { getK8s: vi.fn() },
  sreApi: { getSRE: vi.fn() },
  devtoolsApi: { getDevTools: vi.fn() },
  aiApi: { getAINews: vi.fn() },
  saglikApi: { getSaglik: vi.fn() },
}))

const ANAHTAR = 'tr.sonZiyaret'
const saatOnce = (sa) => new Date(Date.now() - sa * 3600 * 1000).toISOString()

const cve = (ek = {}) => ({
  id: 11,
  cve_id: 'CVE-2026-1001',
  cvss_score: 9.8,
  severity: 'CRITICAL',
  turkish_title: 'CVE-2026-1001 - VPN ağ geçidinde uzaktan kod çalıştırma',
  original_title: 'CVE-2026-1001',
  turkish_description: 'Yönetim arayüzü internete açık kurulumlar etkileniyor.',
  original_description: 'Internet-facing management interfaces are affected.',
  cwe_ids: ['CWE-787'],
  references: [],
  affected_products: '',
  kev_added_date: '2026-10-30',
  source: 'NVD',
  link: 'https://nvd.nist.gov/vuln/detail/CVE-2026-1001',
  created_at: saatOnce(2),
  needs_translation: false,
  translation_provider: 'gemini',
  ...ek,
})

const ozet = (ek = {}) => ({
  generated_at: new Date().toISOString(),
  critical_count: 3,
  high_count: 12,
  kev_count: 2,
  priority: [cve()],
  chart: [{ cve_id: 'CVE-2026-1001', cvss_score: 9.8 }, { cve_id: 'CVE-2026-1002', cvss_score: 7.5 }],
  unscored_count: 0,
  sources: { total: 47, silent: 0 },
  fetch: { last_success_at: saatOnce(1), next_at: new Date(Date.now() + 3600 * 1000).toISOString() },
  ...ek,
})

const haber = (id, baslik, sa) => ({
  id, turkish_title: baslik, original_title: baslik, source: 'Örnek Kaynak',
  link: `https://ornek.test/${id}`, created_at: saatOnce(sa),
})
const liste = (kayitlar) => Promise.resolve({ data: { success: true, data: kayitlar } })

const sayfa = () => render(
  <MemoryRouter>
    <GenelBakis />
  </MemoryRouter>,
)

describe('GenelBakis', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    ozetApi.getOzet.mockResolvedValue({ data: ozet() })
    newsApi.getNews.mockImplementation(() => liste([haber(1, 'Fidye yazılımı grubu yeni site açtı', 3)]))
    k8sApi.getK8s.mockImplementation(() => liste([haber(2, 'Kubernetes beta sürüm notları', 5)]))
    sreApi.getSRE.mockImplementation(() => liste([]))
    devtoolsApi.getDevTools.mockImplementation(() => liste([]))
    aiApi.getAINews.mockImplementation(() => liste([]))
    saglikApi.getSaglik.mockResolvedValue({ data: { sections: {} } })
  })

  it('kritik varsa baslik ve kev cumlesi', async () => {
    sayfa()
    expect(await screen.findByText('3 kritik zafiyet')).toBeInTheDocument()
    expect(screen.getByText(/değerlendirme bekliyor/)).toBeInTheDocument()
    expect(screen.getByText(/2 tanesi son 7 günde CISA KEV kataloğuna eklendi, aktif istismar doğrulanmış\./)).toBeInTheDocument()
    expect(screen.getByText('Zafiyet Durumu · Son 24 Saat')).toBeInTheDocument()
  })

  it('kritik yoksa sakin cumle', async () => {
    ozetApi.getOzet.mockResolvedValue({ data: ozet({
      critical_count: 0, high_count: 0, kev_count: 0, priority: [], chart: [], unscored_count: 0,
    }) })
    sayfa()
    expect(await screen.findByText('Son 24 saatte kritik zafiyet yok')).toBeInTheDocument()
    expect(screen.getByText('Son 7 günde 0 yüksek önem dereceli zafiyet kaydedildi.')).toBeInTheDocument()
    expect(screen.queryByText(/kritik zafiyet$/)).toBeNull()
    expect(screen.queryByText(/CISA KEV kataloğuna eklendi/)).toBeNull()
  })

  it('ilk ziyarette son ziyaret cumlesi ve Yeni rozeti yok', async () => {
    sayfa()
    expect(await screen.findByText('3 kritik zafiyet')).toBeInTheDocument()
    expect(ozetApi.getOzet).toHaveBeenCalledTimes(1)
    expect(ozetApi.getOzet.mock.calls[0][0]).toBeUndefined()
    expect(screen.queryByText(/Son ziyaretinizden/)).toBeNull()
    expect(screen.queryByText('Yeni')).toBeNull()
  })

  it('son ziyaret varsa since gonderilir, cumle ve Yeni rozeti gorunur', async () => {
    const sonZiyaret = saatOnce(10)
    localStorage.setItem(ANAHTAR, sonZiyaret)
    ozetApi.getOzet.mockResolvedValue({ data: ozet({
      new_since_count: 4,
      priority: [cve(), cve({ id: 12, cve_id: 'CVE-2026-0999', created_at: saatOnce(30) })],
    }) })
    sayfa()
    expect(await screen.findByText(/Son ziyaretinizden bu yana 4 yeni kayıt eklendi\./)).toBeInTheDocument()
    expect(ozetApi.getOzet).toHaveBeenCalledWith(sonZiyaret)
    // Yalniz son ziyaretten sonra gelen kayit "Yeni" alir
    expect(screen.getAllByText('Yeni')).toHaveLength(1)
    expect(screen.getByText('Yeni').closest('button')).toHaveTextContent('CVE-2026-1001')
  })

  it('sayfa gizlenince en yeni created_at son ziyaret olarak yazilir', async () => {
    const enYeni = saatOnce(1)
    newsApi.getNews.mockImplementation(() => liste([{ ...haber(1, 'En yeni haber', 1), created_at: enYeni }, haber(3, 'Eski haber', 40)]))
    sayfa()
    expect(await screen.findByText('En yeni haber')).toBeInTheDocument()
    expect(await screen.findByText('3 kritik zafiyet')).toBeInTheDocument()
    expect(localStorage.getItem(ANAHTAR)).toBeNull()

    window.dispatchEvent(new Event('pagehide'))
    expect(localStorage.getItem(ANAHTAR)).toBe(enYeni)
  })

  it('kaynak sessizse kutu uyari gosterir', async () => {
    ozetApi.getOzet.mockResolvedValue({ data: ozet({ sources: { total: 47, silent: 2 } }) })
    sayfa()
    const deger = await screen.findByText('45/47')
    expect(screen.getByText('2 kaynak sessiz')).toBeInTheDocument()
    expect(deger.closest('.ozet-kutusu')).toHaveClass('uyari')
  })

  it('oncelikli satir paneli acar', async () => {
    sayfa()
    const baslik = await screen.findByText('VPN ağ geçidinde uzaktan kod çalıştırma')
    expect(screen.getByRole('link', { name: 'Tümünü görüntüle →' })).toHaveAttribute('href', '/cve')
    fireEvent.click(baslik.closest('button'))
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('CVE-2026-1001')).toBeInTheDocument()
    expect(within(panel).getByText('Yönetim arayüzü internete açık kurulumlar etkileniyor.')).toBeInTheDocument()
  })

  it('gundem kaydi paneli acar', async () => {
    sayfa()
    const oge = await screen.findByText('Kubernetes beta sürüm notları')
    fireEvent.click(oge.closest('button'))
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByRole('heading', { name: 'Kubernetes beta sürüm notları' })).toBeInTheDocument()
  })

  it('ozet hatasinda gundem calisir', async () => {
    ozetApi.getOzet.mockRejectedValue(new Error('404'))
    sayfa()
    expect(await screen.findByText('Özet bilgisi alınamadı.')).toBeInTheDocument()
    expect(screen.getByText('Gündem')).toBeInTheDocument()
    expect(await screen.findByText('Fidye yazılımı grubu yeni site açtı')).toBeInTheDocument()
  })
})
