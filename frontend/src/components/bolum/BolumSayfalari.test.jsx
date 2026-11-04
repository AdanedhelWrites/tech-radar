import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, within, waitFor, act } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import NewsComponent from '../NewsComponent'
import KubernetesComponent from '../KubernetesComponent'
import SREComponent from '../SREComponent'
import DevToolsComponent from '../DevToolsComponent'
import AINewsComponent from '../AINewsComponent'
import { newsApi, k8sApi, sreApi, devtoolsApi, aiApi } from '../../services/api'

// Bes bolum bileseni BolumSayfasi'na tasindi: her biri listesini, okuma panelini ve Cek'in
// sunucu mesajini (429 sogumasi) gosterir. 2026-11-05: donem, siralama, kaynak ve kategori
// sunucuda suzulur (adreste tutulur), liste sayfalanir; Cek en fazla 15 gun, rapor en fazla 500 kayit.

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
    baslik: 'Siber Güvenlik', kaynakSayisi: 12, ilkKaynak: 'The Hacker News',
    yuklemeHatasi: 'Siber güvenlik haberleri yüklenirken hata oluştu',
  },
  {
    ad: 'KubernetesComponent', Bilesen: KubernetesComponent, api: () => k8sApi, liste: 'getK8s', cek: 'fetchK8s',
    baslik: 'Kubernetes', kaynakSayisi: 3, ilkKaynak: 'K8s Blog',
    yuklemeHatasi: 'Kubernetes haberleri yüklenirken hata oluştu',
  },
  {
    ad: 'SREComponent', Bilesen: SREComponent, api: () => sreApi, liste: 'getSRE', cek: 'fetchSRE',
    baslik: 'SRE', kaynakSayisi: 5, ilkKaynak: 'SRE Weekly',
    yuklemeHatasi: 'SRE haberleri yüklenirken hata oluştu',
  },
  {
    ad: 'DevToolsComponent', Bilesen: DevToolsComponent, api: () => devtoolsApi, liste: 'getDevTools', cek: 'fetchDevTools',
    baslik: 'DevTools', kaynakSayisi: 13, ilkKaynak: 'Seq',
    yuklemeHatasi: 'DevTools güncellemeleri yüklenirken hata oluştu',
  },
  {
    ad: 'AINewsComponent', Bilesen: AINewsComponent, api: () => aiApi, liste: 'getAINews', cek: 'fetchAINews',
    baslik: 'Yapay Zeka', kaynakSayisi: 9, ilkKaynak: 'Hugging Face',
    yuklemeHatasi: 'AI güncellemeleri yüklenirken hata oluştu',
  },
]

function Konum() {
  const { search } = useLocation()
  return <output data-testid="konum">{search}</output>
}

const ac = (Bilesen, giris = '/bolum') => render(
  <MemoryRouter initialEntries={[giris]}>
    <Routes>
      <Route path="/bolum" element={<><Bilesen /><Konum /></>} />
    </Routes>
  </MemoryRouter>,
)

const kur = (api, liste, kayitlar, istatistik = {}) => {
  api[liste].mockResolvedValue({ data: { success: true, data: kayitlar } })
  api.getStats.mockResolvedValue({ data: { success: true, total: 250, by_source: {}, last_update: saatOnce(1), ...istatistik } })
}

const VARSAYILAN_ISTEK = { gun: 7, sirala: 'yeni', sayfa: 1, boyut: 25 }
const konum = () => screen.getByTestId('konum').textContent
const adresParametreleri = () => new URLSearchParams(konum())

describe.each(SAYFALAR)('$ad', ({ Bilesen, api, liste, cek, baslik, kaynakSayisi, ilkKaynak, yuklemeHatasi }) => {
  beforeEach(() => {
    vi.clearAllMocks()
    kur(api(), liste, [kayit(1), kayit(2)])
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('liste ve okuma paneli', async () => {
    ac(Bilesen)
    expect(screen.getByRole('heading', { name: baslik })).toBeInTheDocument()
    const satir = (await screen.findByText('Türkçe başlık 2')).closest('button')
    expect(screen.getByText('Son 7 günde 2 kayıt · 1–2 gösteriliyor')).toBeInTheDocument()
    expect(screen.getByText('Toplam 250 kayıt')).toBeInTheDocument()
    expect(api()[liste]).toHaveBeenCalledWith(VARSAYILAN_ISTEK)
    fireEvent.click(satir)
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('Türkçe açıklama 2.')).toBeInTheDocument()
    expect(konum()).toBe('?kayit=2')
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
    expect(days).toBe(7)
    expect(sources).toHaveLength(kaynakSayisi)
  })

  it('liste_hatasi_uyari_gosterir', async () => {
    api()[liste].mockRejectedValue(new Error('Network Error'))
    vi.spyOn(console, 'error').mockImplementation(() => {})
    ac(Bilesen)
    expect(await screen.findByText(yuklemeHatasi)).toBeInTheDocument()
  })

  it('donem_secimi_listeyi_sunucuda_suzer', async () => {
    ac(Bilesen, '/bolum?sayfa=3')
    await screen.findByText('Türkçe başlık 1')
    fireEvent.change(screen.getByRole('combobox', { name: 'Dönem' }), { target: { value: '1' } })
    // Adreste sayfa silinir (1'e doner), istekte sayfa 1 gider
    expect(konum()).toBe('?gun=1')
    await waitFor(() => expect(api()[liste]).toHaveBeenLastCalledWith({ gun: 1, sirala: 'yeni', sayfa: 1, boyut: 25 }))
    expect(await screen.findByText('Son 1 günde 2 kayıt · 1–2 gösteriliyor')).toBeInTheDocument()
    // Siralama da sunucuya gider
    fireEvent.change(screen.getByRole('combobox', { name: 'Sırala' }), { target: { value: 'eski' } })
    expect(konum()).toBe('?gun=1&sirala=eski')
    await waitFor(() => expect(api()[liste]).toHaveBeenLastCalledWith({ gun: 1, sirala: 'eski', sayfa: 1, boyut: 25 }))
  })

  it('sayim_gercek_toplami_gosterir', async () => {
    const yirmiBes = Array.from({ length: 25 }, (_, i) => kayit(26 + i))
    api()[liste].mockImplementation(async (params) => ({
      data: { success: true, data: yirmiBes, toplam: 1234, sayfa: params.sayfa, sayfa_sayisi: 50, boyut: 25 },
    }))
    ac(Bilesen, '/bolum?sayfa=2')
    expect(await screen.findByText('Son 7 günde 1.234 kayıt · 26–50 gösteriliyor')).toBeInTheDocument()
    expect(api()[liste]).toHaveBeenCalledWith({ ...VARSAYILAN_ISTEK, sayfa: 2 })
    const cubuk = screen.getByRole('navigation', { name: 'Sayfalar' })
    fireEvent.click(within(cubuk).getByRole('button', { name: 'Sonraki ›' }))
    expect(konum()).toBe('?sayfa=3')
    await waitFor(() => expect(api()[liste]).toHaveBeenLastCalledWith({ ...VARSAYILAN_ISTEK, sayfa: 3 }))
    expect(await screen.findByText('Son 7 günde 1.234 kayıt · 51–75 gösteriliyor')).toBeInTheDocument()
  })

  it('kaynak_secimi_listeyi_suzer_ve_ceker', async () => {
    api()[cek].mockResolvedValue({ data: { success: true } })
    ac(Bilesen)
    await screen.findByText('Türkçe başlık 1')
    fireEvent.click(screen.getByRole('button', { name: `Kaynaklar ${kaynakSayisi}/${kaynakSayisi}` }))
    fireEvent.click(screen.getByRole('checkbox', { name: new RegExp(ilkKaynak) }))
    const kaynak = adresParametreleri().get('kaynak')
    expect(kaynak.split(',')).toHaveLength(kaynakSayisi - 1)
    expect(kaynak.split(',')).not.toContain(ilkKaynak)
    expect(adresParametreleri().has('sayfa')).toBe(false)
    await waitFor(() => expect(api()[liste]).toHaveBeenLastCalledWith({ ...VARSAYILAN_ISTEK, kaynak }))
    expect(screen.getByRole('button', { name: `Kaynaklar ${kaynakSayisi - 1}/${kaynakSayisi}` })).toBeInTheDocument()
    // Cek ayni kumeden ceker
    fireEvent.click(screen.getByRole('button', { name: /^Çek/ }))
    await waitFor(() => expect(api()[cek]).toHaveBeenCalledTimes(1))
    expect(api()[cek].mock.calls[0][0].sources).toEqual(kaynak.split(','))
    // Basarili cekim istatistigi yeniler (bekle: test sonrasi durum guncellemesi kalmasin)
    await waitFor(() => expect(api().getStats).toHaveBeenCalledTimes(2))
    // Kaynak geri secilince hepsi secili: adreste kaynak kalmaz
    fireEvent.click(screen.getByRole('checkbox', { name: new RegExp(ilkKaynak) }))
    expect(konum()).toBe('')
    await waitFor(() => expect(api()[liste]).toHaveBeenLastCalledWith(VARSAYILAN_ISTEK))
  })

  it('cek_en_fazla_15_gun', async () => {
    api()[cek].mockResolvedValue({ data: { success: true } })
    ac(Bilesen)
    await screen.findByText('Türkçe başlık 1')
    const donem = screen.getByRole('combobox', { name: 'Dönem' })
    const cekVeGun = async (deger) => {
      fireEvent.change(donem, { target: { value: deger } })
      const dugme = screen.getByRole('button', { name: /^Çek/ })
      await waitFor(() => expect(dugme).not.toBeDisabled())
      fireEvent.click(dugme)
      await waitFor(() => expect(dugme).not.toBeDisabled())
      return api()[cek].mock.lastCall[0].days
    }
    expect(await cekVeGun('tumu')).toBe(15)
    expect(await cekVeGun('30')).toBe(15)
    expect(await cekVeGun('7')).toBe(7)
    expect(await cekVeGun('3')).toBe(3)
  })

  it('rapor_gecerli_filtreyle_en_fazla_500', async () => {
    const raporlar = []
    vi.stubGlobal('Blob', class {
      constructor(parcalar) { raporlar.push(parcalar.join('')) }
    })
    URL.createObjectURL = vi.fn(() => 'blob:rapor')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    api()[liste].mockImplementation(async (params) => {
      if (params.boyut !== 100) return { data: { success: true, data: [kayit(1)], toplam: 730, sayfa: 1, sayfa_sayisi: 30, boyut: 25 } }
      const sayfadakiler = Array.from({ length: 100 }, (_, i) => kayit((params.sayfa - 1) * 100 + i + 1))
      return { data: { success: true, data: sayfadakiler, toplam: 730, sayfa: params.sayfa, sayfa_sayisi: 8, boyut: 100 } }
    })
    ac(Bilesen, `/bolum?gun=tumu&sirala=eski&kaynak=${encodeURIComponent(ilkKaynak)}&sayfa=4`)
    await screen.findByText('Türkçe başlık 1')
    fireEvent.click(screen.getByTitle(/HTML rapor olarak indir/))
    await waitFor(() => expect(raporlar).toHaveLength(1))
    // Sayfadan bagimsiz: gecerli filtre ve siralamayla 1..5. sayfalar, 100'er kayit
    const raporCagrilari = api()[liste].mock.calls.map(([p]) => p).filter(p => p.boyut === 100)
    expect(raporCagrilari).toEqual([1, 2, 3, 4, 5].map(sayfa => ({ sirala: 'eski', sayfa, boyut: 100, kaynak: ilkKaynak })))
    const html = raporlar[0]
    expect(html).toContain('İlk 500 kayıt (toplam 730)')
    expect(html.match(/class="article"/g)).toHaveLength(500)
    expect(html).toContain('Türkçe başlık 500')
    expect(html).not.toContain('Türkçe başlık 501')
  })

  it('temizle_paneli_kapatir_ve_listeyi_yeniler', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    api().clearCache.mockResolvedValue({ data: { success: true } })
    ac(Bilesen, '/bolum?kayit=1')
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    const oncekiCagri = api()[liste].mock.calls.length
    // Temizlik sonrasi liste bos gelir; panel son bilinen kayitla acik kalmamali
    api()[liste].mockResolvedValue({ data: { success: true, data: [], toplam: 0, sayfa: 1, sayfa_sayisi: 1, boyut: 25 } })
    api().getStats.mockResolvedValue({ data: { success: true, total: 0, by_source: {}, last_update: null } })
    fireEvent.click(screen.getByRole('button', { name: /Önbelleği temizle/ }))
    await waitFor(() => expect(konum()).toBe(''))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(api()[liste].mock.calls.length).toBeGreaterThan(oncekiCagri)
    expect(await screen.findByText('Liste boş. Kayıt almak için "Çek" düğmesini kullanın.')).toBeInTheDocument()
  })
})

describe('KubernetesComponent kategori filtresi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    kur(k8sApi, 'getK8s', [
      kayit(1, { category: 'release', version: 'v1.35.10', source: 'GitHub Releases' }),
      kayit(2, { category: 'security' }),
    ], { by_category: { release: 61, security: 15 } })
  })

  it('k8s_kategori_sunucuya_gider', async () => {
    ac(KubernetesComponent, '/bolum?sayfa=2')
    await screen.findByText('Türkçe başlık 1')
    expect(screen.getByText('Sürüm 61')).toBeInTheDocument()
    const grup = screen.getByRole('group', { name: 'Kategori filtresi' })
    expect(within(grup).getByRole('button', { name: 'Tümü' })).toHaveAttribute('aria-pressed', 'true')
    fireEvent.click(within(grup).getByRole('button', { name: 'Güvenlik' }))
    expect(konum()).toBe('?kategori=security')
    expect(within(grup).getByRole('button', { name: 'Güvenlik' })).toHaveAttribute('aria-pressed', 'true')
    await waitFor(() => expect(k8sApi.getK8s).toHaveBeenLastCalledWith({ ...VARSAYILAN_ISTEK, kategori: 'security' }))
    fireEvent.click(within(grup).getByRole('button', { name: 'Tümü' }))
    expect(konum()).toBe('')
    await waitFor(() => expect(k8sApi.getK8s).toHaveBeenLastCalledWith(VARSAYILAN_ISTEK))
  })

  it('k8s_gecersiz_kategori_tumu_sayilir_ve_gitmez', async () => {
    ac(KubernetesComponent, '/bolum?kategori=uydurma')
    await screen.findByText('Türkçe başlık 1')
    const grup = screen.getByRole('group', { name: 'Kategori filtresi' })
    expect(within(grup).getByRole('button', { name: 'Tümü' })).toHaveAttribute('aria-pressed', 'true')
    expect(k8sApi.getK8s).toHaveBeenLastCalledWith(VARSAYILAN_ISTEK)
  })

  it('son_secili_kaynak_kaldirilamaz', async () => {
    ac(KubernetesComponent, `/bolum?kaynak=${encodeURIComponent('CNCF Blog')}`)
    await screen.findByText('Türkçe başlık 1')
    fireEvent.click(screen.getByRole('button', { name: 'Kaynaklar 1/3' }))
    // Bos kaynak "hepsi" demek: tek secili kaynak kaldirilamaz
    expect(screen.getByRole('checkbox', { name: /CNCF Blog/ })).toBeDisabled()
    expect(screen.getByRole('checkbox', { name: /K8s Blog/ })).not.toBeDisabled()
    // Acilir menu konumlandirmasi (popper) tamamlansin
    await act(async () => {})
  })
})

describe('Ortak bolum davranisi (NewsComponent uzerinden)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    kur(newsApi, 'getNews', [kayit(1), kayit(2)])
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('bilinmeyen_kaynak_listeye_ve_ceke_gitmez', async () => {
    newsApi.fetchNews.mockResolvedValue({ data: { success: true } })
    ac(NewsComponent, `/bolum?kaynak=${encodeURIComponent('Uydurma,The Hacker News')}`)
    await screen.findByText('Türkçe başlık 1')
    expect(newsApi.getNews).toHaveBeenLastCalledWith({ ...VARSAYILAN_ISTEK, kaynak: 'The Hacker News' })
    expect(newsApi.getNews.mock.calls.every(([p]) => !String(p.kaynak).includes('Uydurma'))).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: /^Çek/ }))
    await waitFor(() => expect(newsApi.fetchNews).toHaveBeenCalledTimes(1))
    expect(newsApi.fetchNews.mock.calls[0][0].sources).toEqual(['The Hacker News'])
    await waitFor(() => expect(newsApi.getStats).toHaveBeenCalledTimes(2))
  })

  it('cvss_siralamasi_haber_bolumlerinde_yok', async () => {
    ac(NewsComponent)
    await screen.findByText('Türkçe başlık 1')
    const sirala = screen.getByRole('combobox', { name: 'Sırala' })
    expect(within(sirala).getAllByRole('option').map(o => o.textContent)).toEqual(['En yeni', 'En eski'])
  })

  it('yalniz_bilinmeyen_kaynak_hepsi_sayilir', async () => {
    newsApi.fetchNews.mockResolvedValue({ data: { success: true } })
    ac(NewsComponent, '/bolum?kaynak=Uydurma')
    await screen.findByText('Türkçe başlık 1')
    expect(newsApi.getNews).toHaveBeenLastCalledWith(VARSAYILAN_ISTEK)
    expect(screen.getByRole('button', { name: 'Kaynaklar 12/12' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /^Çek/ }))
    await waitFor(() => expect(newsApi.fetchNews).toHaveBeenCalledTimes(1))
    expect(newsApi.fetchNews.mock.calls[0][0].sources).toHaveLength(12)
    await waitFor(() => expect(newsApi.getStats).toHaveBeenCalledTimes(2))
  })

  it('hata_sonrasi_sayim_ve_sayfa_cubugu_eski_toplamla_karismaz', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const yirmiBes = Array.from({ length: 25 }, (_, i) => kayit(i + 1))
    newsApi.getNews.mockImplementation(async (params) => {
      if (params.sayfa === 2) throw new Error('Network Error')
      return { data: { success: true, data: yirmiBes, toplam: 1234, sayfa: params.sayfa, sayfa_sayisi: 50, boyut: 25 } }
    })
    ac(NewsComponent)
    expect(await screen.findByText('Son 7 günde 1.234 kayıt · 1–25 gösteriliyor')).toBeInTheDocument()
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Sayfalar' })).getByRole('button', { name: 'Sonraki ›' }))
    expect(await screen.findByText('Siber güvenlik haberleri yüklenirken hata oluştu')).toBeInTheDocument()
    // Eski sorgunun toplami yeni sayfanin araligiyla gosterilmez ("26–50"), sayfa cubugu da gizli
    expect(screen.queryByText(/gösteriliyor/)).toBeNull()
    expect(screen.queryByRole('navigation', { name: 'Sayfalar' })).toBeNull()
  })

  it('rapor_hazirlanirken_ikinci_tiklama_yok_sayilir', async () => {
    const raporlar = []
    vi.stubGlobal('Blob', class {
      constructor(parcalar) { raporlar.push(parcalar.join('')) }
    })
    URL.createObjectURL = vi.fn(() => 'blob:rapor')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    let coz
    newsApi.getNews.mockImplementation((params) => {
      if (params.boyut !== 100) return Promise.resolve({ data: { success: true, data: [kayit(1)] } })
      return new Promise(r => { coz = () => r({ data: { success: true, data: [kayit(1)], toplam: 1, sayfa: 1, sayfa_sayisi: 1, boyut: 100 } }) })
    })
    ac(NewsComponent)
    await screen.findByText('Türkçe başlık 1')
    const dugme = screen.getByTitle(/HTML rapor olarak indir/)
    fireEvent.click(dugme)
    expect(dugme).toBeDisabled()
    fireEvent.click(dugme)
    const raporCagrilari = () => newsApi.getNews.mock.calls.filter(([p]) => p.boyut === 100)
    expect(raporCagrilari()).toHaveLength(1)
    await act(async () => { coz() })
    await waitFor(() => expect(raporlar).toHaveLength(1))
    expect(dugme).not.toBeDisabled()
    expect(raporCagrilari()).toHaveLength(1)
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

