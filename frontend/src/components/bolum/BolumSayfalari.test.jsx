import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import NewsComponent from '../NewsComponent'
import KubernetesComponent from '../KubernetesComponent'
import SREComponent from '../SREComponent'
import DevToolsComponent from '../DevToolsComponent'
import AINewsComponent from '../AINewsComponent'
import { newsApi, k8sApi, sreApi, devtoolsApi, aiApi } from '../../services/api'

// Bes bolum bileseni BolumSayfasi'na tasindi: her biri listesini, okuma panelini ve Cek'in
// sunucu mesajini (429 sogumasi) gosterir; donem varsayilani ve kaynak listesi korunur.

vi.mock('../../services/api', () => ({
  newsApi: { getNews: vi.fn(), fetchNews: vi.fn(), getStats: vi.fn(), clearCache: vi.fn(), exportNews: vi.fn() },
  k8sApi: { getK8s: vi.fn(), fetchK8s: vi.fn(), getStats: vi.fn(), clearCache: vi.fn(), exportK8s: vi.fn() },
  sreApi: { getSRE: vi.fn(), fetchSRE: vi.fn(), getStats: vi.fn(), clearCache: vi.fn(), exportSRE: vi.fn() },
  devtoolsApi: { getDevTools: vi.fn(), fetchDevTools: vi.fn(), getStats: vi.fn(), clearCache: vi.fn(), exportDevTools: vi.fn() },
  aiApi: { getAINews: vi.fn(), fetchAINews: vi.fn(), getStats: vi.fn(), clearCache: vi.fn(), exportAINews: vi.fn() },
  istekHataMesaji: (err, varsayilan) => err.response?.data?.message || `${varsayilan}: ${err.message}`,
}))

const saatOnce = (sa) => new Date(Date.now() - sa * 3600 * 1000).toISOString()

const kayit = (id, ek = {}) => ({
  id,
  source: 'Kaynak',
  original_title: `Original title ${id}`,
  turkish_title: `Türkçe başlık ${id}`,
  original_description: `Original description ${id}.`,
  turkish_description: `Türkçe açıklama ${id}.`,
  link: `https://ornek.test/${id}`,
  date: '2026-10-30',
  published_date: '2026-10-29',
  created_at: saatOnce(id),
  needs_translation: false,
  translation_provider: 'gemini',
  ...ek,
})

const SAYFALAR = [
  {
    ad: 'NewsComponent', Bilesen: NewsComponent, api: () => newsApi, liste: 'getNews', cek: 'fetchNews',
    baslik: 'Siber Güvenlik', gun: 7, kaynakSayisi: 12,
  },
  {
    ad: 'KubernetesComponent', Bilesen: KubernetesComponent, api: () => k8sApi, liste: 'getK8s', cek: 'fetchK8s',
    baslik: 'Kubernetes', gun: 7, kaynakSayisi: 3,
  },
  {
    ad: 'SREComponent', Bilesen: SREComponent, api: () => sreApi, liste: 'getSRE', cek: 'fetchSRE',
    baslik: 'SRE', gun: 7, kaynakSayisi: 5,
  },
  {
    ad: 'DevToolsComponent', Bilesen: DevToolsComponent, api: () => devtoolsApi, liste: 'getDevTools', cek: 'fetchDevTools',
    baslik: 'DevTools', gun: 30, kaynakSayisi: 13,
  },
  {
    ad: 'AINewsComponent', Bilesen: AINewsComponent, api: () => aiApi, liste: 'getAINews', cek: 'fetchAINews',
    baslik: 'Yapay Zeka', gun: 30, kaynakSayisi: 9,
  },
]

function Konum() {
  const { search } = useLocation()
  return <output data-testid="konum">{search}</output>
}

const ac = (Bilesen) => render(
  <MemoryRouter initialEntries={['/bolum']}>
    <Routes>
      <Route path="/bolum" element={<><Bilesen /><Konum /></>} />
    </Routes>
  </MemoryRouter>,
)

const kur = (api, liste, kayitlar, istatistik = {}) => {
  api[liste].mockResolvedValue({ data: { success: true, data: kayitlar } })
  api.getStats.mockResolvedValue({ data: { success: true, total: 250, by_source: {}, last_update: saatOnce(1), ...istatistik } })
}

describe.each(SAYFALAR)('$ad', ({ Bilesen, api, liste, cek, baslik, gun, kaynakSayisi }) => {
  beforeEach(() => {
    vi.clearAllMocks()
    kur(api(), liste, [kayit(1), kayit(2)])
  })

  it('liste ve okuma paneli', async () => {
    ac(Bilesen)
    expect(screen.getByRole('heading', { name: baslik })).toBeInTheDocument()
    const satir = (await screen.findByText('Türkçe başlık 2')).closest('button')
    expect(screen.getByText('2 kayıt gösteriliyor')).toBeInTheDocument()
    expect(screen.getByText('Toplam 250 kayıt')).toBeInTheDocument()
    fireEvent.click(satir)
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('Türkçe açıklama 2.')).toBeInTheDocument()
    expect(screen.getByTestId('konum')).toHaveTextContent('?kayit=2')
  })

  it('Cek sunucunun 429 mesajini gosterir', async () => {
    api()[cek].mockRejectedValue({
      message: 'Request failed with status code 429',
      response: { status: 429, data: { message: 'Çok sık çekim: 12 dakika sonra tekrar deneyin.' } },
    })
    ac(Bilesen)
    await screen.findByText('Türkçe başlık 1')
    fireEvent.click(screen.getByRole('button', { name: /^Çek/ }))
    expect(await screen.findByText('Çok sık çekim: 12 dakika sonra tekrar deneyin.')).toBeInTheDocument()
    const [{ days, sources }] = api()[cek].mock.calls[0]
    expect(days).toBe(gun)
    expect(sources).toHaveLength(kaynakSayisi)
  })
})

describe('KubernetesComponent kategori filtresi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    kur(k8sApi, 'getK8s', [
      kayit(1, { category: 'release', version: 'v1.35.10', source: 'GitHub Releases' }),
      kayit(2, { category: 'security' }),
      kayit(3, { category: 'ecosystem' }),
    ], { by_category: { release: 61, security: 15 } })
  })

  it('kategori secilince liste ve sayac daralir, dagilim baslikta', async () => {
    ac(KubernetesComponent)
    await screen.findByText('3 kayıt gösteriliyor')
    expect(screen.getByText('Sürüm 61')).toBeInTheDocument()
    const grup = screen.getByRole('group', { name: 'Kategori filtresi' })
    fireEvent.click(within(grup).getByRole('button', { name: 'Güvenlik' }))
    expect(screen.getByText('1 / 3 kayıt gösteriliyor')).toBeInTheDocument()
    expect(within(grup).getByRole('button', { name: 'Güvenlik' })).toHaveAttribute('aria-pressed', 'true')
    const listeOgeleri = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(listeOgeleri).toHaveLength(1)
    expect(within(listeOgeleri[0]).getByText('Türkçe başlık 2')).toBeInTheDocument()
    fireEvent.click(within(grup).getByRole('button', { name: 'Tümü' }))
    expect(screen.getByText('3 kayıt gösteriliyor')).toBeInTheDocument()
  })
})

describe('DevToolsComponent kayit turu', () => {
  it('surum ve kayit turu rozetleri, tur dagilimi baslikta', async () => {
    vi.clearAllMocks()
    kur(devtoolsApi, 'getDevTools', [kayit(1, { version: '17.2', entry_type: 'release' })], { by_type: { release: 163, news: 28 } })
    ac(DevToolsComponent)
    const satir = (await screen.findByText('Türkçe başlık 1')).closest('button')
    expect(within(satir).getByText('17.2')).toHaveClass('rozet', 'bilgi')
    expect(within(satir).getByText('Sürüm')).toHaveClass('rozet', 'bilgi')
    expect(screen.getByText('Sürüm 163')).toBeInTheDocument()
    expect(screen.getByText('Haber 28')).toBeInTheDocument()
  })
})
