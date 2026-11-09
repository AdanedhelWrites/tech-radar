import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import BolumSayfasi, { BolumCubugu } from './BolumSayfasi'
import { DONEM_SECENEKLERI, SIRALA_SECENEKLERI } from './secenekler'

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
            <BolumSayfasi bolum="news" baslik="Siber Güvenlik" kayitlar={KAYITLAR} yukleniyor={false} cubuk={null} gun={7} {...ozellikler} />
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
    expect(screen.getByText('Son 7 günde 3 kayıt · 1–3 gösteriliyor')).toBeInTheDocument()
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

  it('basligi orijinalin kopyasi olan cevrilmemis kayitta da rozet ve lang en', () => {
    // Uretimdeki yaygin durum: basarisiz ceviri turkish_title'a Ingilizce basligi kopyalar
    const kopya = haber(4, {
      original_title: 'Copied English headline',
      turkish_title: 'Copied English headline',
      needs_translation: true,
      translation_provider: null,
    })
    sayfa({ kayitlar: [haber(1), kopya] })
    const baslik = screen.getByText('Copied English headline')
    expect(baslik).toHaveAttribute('lang', 'en')
    expect(within(baslik.closest('button')).getByText('Çevrilmedi: orijinal metin')).toBeInTheDocument()
    // Cevrilmis satir Turkce kalir ve saglayici rozetini gosterir
    const cevrilmis = screen.getByText('Türkçe başlık 1')
    expect(cevrilmis).toHaveAttribute('lang', 'tr')
    expect(within(cevrilmis.closest('button')).getByText('Çeviri: Gemini')).toBeInTheDocument()
  })

  it('news bolumunde tarih date alanindan okunur', async () => {
    sayfa({}, '/news?kayit=1')
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('The Hacker News · 30 Ekim 2026')).toBeInTheDocument()
    expect(within(panel).queryByText(/29 Ekim 2026/)).toBeNull()
  })

  it('diger bolumlerde tarih published_date alanindan okunur', async () => {
    sayfa({ bolum: 'sre', baslik: 'SRE' }, '/news?kayit=1')
    const panel = await screen.findByRole('dialog')
    expect(within(panel).getByText('The Hacker News · 29 Ekim 2026')).toBeInTheDocument()
  })

  it('bolume ozgu bilgi rozetleri satirda gorunur', () => {
    const k8s = [haber(1, { category: 'security', version: 'v1.34.1' })]
    sayfa({ bolum: 'kubernetes', baslik: 'Kubernetes', kayitlar: k8s })
    const satir = screen.getByText('Türkçe başlık 1').closest('button')
    expect(within(satir).getByText('Güvenlik')).toHaveClass('rozet', 'bilgi')
    expect(within(satir).getByText('v1.34.1')).toHaveClass('rozet', 'bilgi')
  })

  it('sayim_gercek_toplami_ve_araligi_gosterir', () => {
    const yirmiBes = Array.from({ length: 25 }, (_, i) => haber(i + 1))
    const ozellik = { kayitlar: yirmiBes, toplam: 1234, sayfa: 2, sayfaSayisi: 50, boyut: 25 }
    const { unmount } = sayfa(ozellik)
    expect(screen.getByText('Son 7 günde 1.234 kayıt · 26–50 gösteriliyor')).toBeInTheDocument()
    unmount()
    // Tumu: donem metni yok
    sayfa({ ...ozellik, gun: null })
    expect(screen.getByText('1.234 kayıt · 26–50 gösteriliyor')).toBeInTheDocument()
  })

  it('sayfa_cubugu_listenin_altinda_ve_yuklenirken_gizli', () => {
    const onSayfa = vi.fn()
    const ozellik = { toplam: 53, sayfa: 1, sayfaSayisi: 3, boyut: 25, onSayfa }
    const { unmount } = sayfa(ozellik)
    const cubuk = screen.getByRole('navigation', { name: 'Sayfalar' })
    // Listenin altinda
    expect(document.querySelector('.oncelikli-liste').compareDocumentPosition(cubuk) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy()
    fireEvent.click(within(cubuk).getByRole('button', { name: '2' }))
    expect(onSayfa).toHaveBeenCalledWith(2)
    unmount()
    // Yeni sorgu yuklenirken eski sayilar ve cubuk gorunmez
    sayfa({ ...ozellik, yukleniyor: true })
    expect(screen.queryByRole('navigation', { name: 'Sayfalar' })).toBeNull()
    expect(screen.queryByText(/gösteriliyor/)).toBeNull()
    expect(screen.getByText('Kayıtlar yükleniyor…')).toBeInTheDocument()
  })

  it('secili kayit sayfada olmasa da panel acik kalir', async () => {
    const { rerender } = sayfa({}, '/news?kayit=2')
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    // Sayfa degisti: kayit 2 artik listede yok
    rerender(
      <MemoryRouter initialEntries={['/news?kayit=2']}>
        <Routes>
          <Route
            path="/news"
            element={<BolumSayfasi bolum="news" baslik="Siber Güvenlik" kayitlar={[haber(1)]} yukleniyor={false} cubuk={null} gun={7} />}
          />
        </Routes>
      </MemoryRouter>,
    )
    expect(within(screen.getByRole('dialog')).getByText('Türkçe açıklama 2.')).toBeInTheDocument()
  })

  it('cubuk islevi paneli kapatan kapat alir', async () => {
    // Bolum bileseni temizleme sonrasi paneli kapatabilsin (liste bosalinca panel artik acik kalir)
    sayfa({ cubuk: ({ kapat }) => <button type="button" onClick={kapat}>temizle</button> }, '/news?kayit=1')
    await screen.findByRole('dialog')
    fireEvent.click(screen.getByRole('button', { name: 'temizle' }))
    await waitFor(() => expect(screen.getByTestId('konum')).toBeEmptyDOMElement())
  })

  it('bos, yukleniyor ve eslesmeyen filtre durumlari', () => {
    const { unmount } = sayfa({ kayitlar: [], yukleniyor: true })
    expect(screen.getByText('Kayıtlar yükleniyor…')).toBeInTheDocument()
    unmount()
    // Veritabani bos
    const ikinci = sayfa({ kayitlar: [], toplam: 0, istatistik: { total: 0 } })
    expect(screen.getByText('Liste boş. Kayıt almak için "Çek" düğmesini kullanın.')).toBeInTheDocument()
    ikinci.unmount()
    // Veritabaninda kayit var, filtreye uyan yok
    sayfa({ kayitlar: [], toplam: 0, istatistik: { total: 40 } })
    expect(screen.getByText('Bu filtreyle eşleşen kayıt bulunamadı.')).toBeInTheDocument()
    expect(screen.queryByText(/gösteriliyor/)).toBeNull()
  })

  it('yukleme_hatasi_eski_liste_yerine_yeniden_dene_gosterir', () => {
    // Yeni sorgu hatayla bitti: eldeki (eski filtrenin) kayitlari gosterilmez
    const onYeniden = vi.fn()
    const { unmount } = sayfa({ hata: new Error('ag'), guncel: false, onYeniden, istatistik: { total: 0 } })
    expect(screen.getByRole('alert')).toHaveTextContent('Kayıtlar yüklenemedi')
    expect(screen.queryByText('Türkçe başlık 1')).toBeNull()
    expect(screen.queryByText(/Liste boş/)).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Yeniden dene' }))
    expect(onYeniden).toHaveBeenCalledTimes(1)
    unmount()
    // Guncel yanit varken (sessiz yenileme hatasi hata yazmaz) liste kalir
    sayfa({ hata: null, guncel: true })
    expect(screen.getByText('Türkçe başlık 1')).toBeInTheDocument()
  })

  it('arama_varken_bos_sonuc_eslesmeyen_filtre_der', () => {
    sayfa({ kayitlar: [], toplam: 0, istatistik: { total: 0 }, aramaVar: true })
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

describe('BolumCubugu', () => {
  const cubuk = (ozellik = {}) => {
    const geriCagrilar = { onGunDegis: vi.fn(), onSiralaDegis: vi.fn(), onKaynakDegis: vi.fn() }
    render(
      <BolumCubugu
        kimlik="test"
        gun={7}
        gunSecenekleri={DONEM_SECENEKLERI}
        sirala="yeni"
        siralaSecenekleri={SIRALA_SECENEKLERI}
        kaynaklar={[]}
        seciliKaynaklar={{}}
        yukleniyor={false}
        cekiliyor={false}
        {...geriCagrilar}
        {...ozellik}
      />,
    )
    return geriCagrilar
  }

  it('arama_kutusu_gecikmeyle_adrese_yazar', async () => {
    const onAraDegis = vi.fn()
    cubuk({ ara: '', onAraDegis })
    fireEvent.change(screen.getByRole('searchbox', { name: 'Kayıtlarda ara' }), { target: { value: ' log4j ' } })
    expect(onAraDegis).not.toHaveBeenCalled()
    await waitFor(() => expect(onAraDegis).toHaveBeenCalledWith('log4j'))
    expect(onAraDegis).toHaveBeenCalledTimes(1)
  })

  it('arama_kutusu_onAraDegis_yoksa_cizilmez', () => {
    cubuk()
    expect(screen.queryByRole('searchbox')).toBeNull()
  })

  it('donem_ve_sirala_secenekleri', () => {
    const { onGunDegis, onSiralaDegis } = cubuk()
    const donem = screen.getByRole('combobox', { name: 'Dönem' })
    expect(within(donem).getAllByRole('option').map(o => o.textContent)).toEqual(
      ['Son 1 gün', 'Son 3 gün', 'Son 7 gün', 'Son 14 gün', 'Son 30 gün', 'Tümü'])
    expect(donem).toHaveDisplayValue('Son 7 gün')
    fireEvent.change(donem, { target: { value: 'tumu' } })
    expect(onGunDegis).toHaveBeenLastCalledWith(null)
    fireEvent.change(donem, { target: { value: '30' } })
    expect(onGunDegis).toHaveBeenLastCalledWith(30)
    const sirala = screen.getByRole('combobox', { name: 'Sırala' })
    expect(within(sirala).getAllByRole('option').map(o => o.textContent)).toEqual(['En yeni', 'En eski'])
    fireEvent.change(sirala, { target: { value: 'eski' } })
    expect(onSiralaDegis).toHaveBeenCalledWith('eski')
    // Cek en fazla 15 gun ceker
    expect(screen.getByRole('button', { name: /^Çek/ })).toHaveAttribute(
      'title', 'Seçili kaynaklardan son 7 günün kayıtlarını çek')
  })

  it('tumu_ve_bolumde_olmayan_siralama', () => {
    // Tumu'de Cek 15 gun; bu bolumde olmayan siralama (adresten cvss) ilk secenek gibi gorunur
    cubuk({ gun: null, sirala: 'cvss' })
    expect(screen.getByRole('combobox', { name: 'Dönem' })).toHaveDisplayValue('Tümü')
    expect(screen.getByRole('combobox', { name: 'Sırala' })).toHaveDisplayValue('En yeni')
    expect(screen.getByRole('button', { name: /^Çek/ })).toHaveAttribute(
      'title', 'Seçili kaynaklardan son 15 günün kayıtlarını çek')
  })
})
