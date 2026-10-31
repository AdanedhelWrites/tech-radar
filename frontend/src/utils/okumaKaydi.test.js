import { describe, it, expect } from 'vitest'
import { cveOkumaKaydi, haberOkumaKaydi } from './okumaKaydi'

const KEV_ORIJINAL = 'Added to the CISA KEV catalog on 2026-10-20; required action due 2026-11-10. A command injection vulnerability allows remote code execution.'
const REFERANSLAR = Array.from({ length: 7 }, (_, i) => `https://ornek.test/ref/${i}`)

const kevCve = (ek = {}) => ({
  id: 42,
  cve_id: 'CVE-2026-1001',
  source: 'CISA KEV',
  original_title: 'CVE-2026-1001 - Ornek VPN RCE',
  turkish_title: 'CVE-2026-1001 - Örnek VPN ağ geçidinde uzaktan kod çalıştırma',
  original_description: KEV_ORIJINAL,
  turkish_description: '2026-10-20 tarihinde CISA KEV kataloğuna eklendi; 2026-11-10 tarihine kadar yapılması gereken eylem zorunludur. Bir komut enjeksiyonu zafiyeti uzaktan kod çalıştırmaya izin verir.',
  cvss_score: 9.8,
  published_date: '2026-09-01',
  kev_added_date: '2026-10-21',
  link: 'https://nvd.nist.gov/vuln/detail/CVE-2026-1001',
  cwe_ids: ['CWE-78', 'CWE-20'],
  references: REFERANSLAR,
  affected_products: 'Örnek VPN Gateway 7.0.0 - 7.4.2',
  ...ek,
})

describe('cveOkumaKaydi', () => {
  it('cve kev onekini govdeden ayirir ve tum referanslari alir', () => {
    const k = cveOkumaKaydi(kevCve())
    expect(k.govdeOrijinal).toBe('A command injection vulnerability allows remote code execution.')
    expect(k.govdeTr).toBe('Bir komut enjeksiyonu zafiyeti uzaktan kod çalıştırmaya izin verir.')
    // eklenme tarihi once kev_added_date alanindan, son tarih onekten
    expect(k.kevMeta).toEqual({ kevEklenme: '2026-10-21', sonTarih: '2026-11-10' })
    expect(k.referanslar).toEqual(REFERANSLAR)
    expect(k.rozetler).toEqual([
      { metin: 'CISA KEV', tur: 'kev' },
      { metin: 'CWE-78', tur: 'ur' },
      { metin: 'CWE-20', tur: 'ur' },
    ])
    expect(k.ekAlanlar).toEqual([{ etiket: 'Etkilenen ürünler', deger: 'Örnek VPN Gateway 7.0.0 - 7.4.2' }])
    expect(k).toMatchObject({
      id: 42,
      ustBaslik: 'CVE-2026-1001',
      baslik: 'Örnek VPN ağ geçidinde uzaktan kod çalıştırma',
      skor: 9.8,
      tarih: '2026-09-01',
      kaynak: 'CISA KEV',
      link: 'https://nvd.nist.gov/vuln/detail/CVE-2026-1001',
    })
    expect(k.ham.cve_id).toBe('CVE-2026-1001')
  })

  it('kev_added_date yoksa kev meta onekten gelir', () => {
    const k = cveOkumaKaydi(kevCve({ kev_added_date: null }))
    expect(k.kevMeta).toEqual({ kevEklenme: '2026-10-20', sonTarih: '2026-11-10' })
  })

  it.each([
    "2026-10-30'da CISA KEV kataloguna eklendi; 2026-11-02 nedeniyle gerekli eylem. Gövde metni burada.",
    '14.10.2026 tarihinde CISA KEV kataloğuna eklenmiştir; 17.10.2026 tarihine kadar yapılması gereken eylem zorunludur. Gövde metni burada.',
    "2026-10-13 tarihinde CISA KEV kataloguna eklenmiştir; 2026-10-16 tarihine kadar gerekli aksiyonun alınması gerekmektedir. Gövde metni burada.",
    '20 Ekim 2026 tarihinde CISA KEV kataloğuna eklendi. Gövde metni burada.',
  ])('cevrilmis kev oneki turkce govdeden ayrilir: %s', (tr) => {
    expect(cveOkumaKaydi(kevCve({ turkish_description: tr })).govdeTr).toBe('Gövde metni burada.')
  })

  it.each([
    // KEV anmasi ilk cumlede degil: sonraki cumleler silinmez
    'Zafiyet uzaktan kod çalıştırmaya izin verir. Saldırganlar aktif olarak istismar eder. CISA KEV kataloğuna eklenmiştir. Yamayı uygulayın.',
    // ilk cumle KEV'i anar ama tarih yok: cevrilmis onek degil
    'Bu açık CISA KEV kataloğunda listelenir. Yamayı uygulayın.',
    // govde tamamen silinip kayit "cevrilmedi" durumuna dusmemeli
    'Bir komut enjeksiyonu zafiyeti. CISA KEV katalogu referans alınmalıdır.',
  ])('onek olmayan turkce cumleye dokunulmaz: %s', (tr) => {
    expect(cveOkumaKaydi(kevCve({ turkish_description: tr })).govdeTr).toBe(tr)
  })

  it('orijinalde kev oneki yoksa turkce govdeye dokunulmaz', () => {
    const tr = 'CISA KEV kataloğundaki zafiyetlerle ilişkilidir. Gövde metni burada.'
    const k = cveOkumaKaydi(kevCve({ source: 'NVD', original_description: 'Plain body.', turkish_description: tr, kev_added_date: null }))
    expect(k.govdeTr).toBe(tr)
    expect(k.kevMeta).toBeNull()
  })

  it('kev disi, skorsuz ve sablon baslikli cve', () => {
    const k = cveOkumaKaydi({
      id: 7, cve_id: 'CVE-2026-2002', source: 'NVD',
      original_title: 'CVE-2026-2002 - Güvenlik Açığı', turkish_title: '',
      original_description: 'Body.', turkish_description: '', cvss_score: null,
      published_date: '2026-10-01', link: 'https://nvd.nist.gov/x', cwe_ids: [], references: [],
      affected_products: '', kev_added_date: null,
    })
    expect(k.baslik).toBe('CVE-2026-2002')
    expect(k.skor).toBeNull()
    expect(k.kevMeta).toBeNull()
    expect(k.rozetler).toEqual([])
    expect(k.ekAlanlar).toEqual([])
    expect(k.referanslar).toEqual([])
    expect(k.govdeTr).toBe('')
    expect(k.govdeOrijinal).toBe('Body.')
  })

  it('eksik alanlarda cokmez', () => {
    const k = cveOkumaKaydi({ id: 1, cve_id: 'CVE-2026-3003' })
    expect(k).toMatchObject({ govdeTr: '', govdeOrijinal: '', referanslar: [], rozetler: [], kevMeta: null, link: '', kaynak: '', tarih: '' })
  })
})

const haber = (ek = {}) => ({
  id: 5,
  source: 'BleepingComputer',
  original_title: 'Original title',
  turkish_title: 'Türkçe başlık',
  original_description: 'Original description.',
  turkish_description: 'Türkçe açıklama.',
  turkish_summary: 'Türkçe özet.',
  link: 'https://ornek.test/haber',
  date: '2026-10-30',
  published_date: '2026-10-29',
  ...ek,
})

describe('haberOkumaKaydi', () => {
  it('news tarihi date alanindan, govde summary yedegiyle', () => {
    const k = haberOkumaKaydi(haber({ turkish_description: '' }), 'news')
    expect(k.tarih).toBe('2026-10-30')
    expect(k.govdeTr).toBe('Türkçe özet.')
    expect(k.govdeOrijinal).toBe('Original description.')
    expect(haberOkumaKaydi(haber(), 'news').govdeTr).toBe('Türkçe açıklama.')
    expect(k).toMatchObject({
      id: 5, ustBaslik: null, baslik: 'Türkçe başlık', skor: null, kevMeta: null,
      kaynak: 'BleepingComputer', link: 'https://ornek.test/haber', rozetler: [], ekAlanlar: [], referanslar: [],
    })
  })

  it('diger bolumlerde tarih published_date, ozet yedegi kullanilmaz', () => {
    const k = haberOkumaKaydi(haber({ turkish_description: '' }), 'sre')
    expect(k.tarih).toBe('2026-10-29')
    expect(k.govdeTr).toBe('')
  })

  it('turkce baslik yoksa orijinal baslik', () => {
    expect(haberOkumaKaydi(haber({ turkish_title: '' }), 'ai').baslik).toBe('Original title')
  })

  it('kubernetes kategori ve surum bilgi rozeti olur', () => {
    const k = haberOkumaKaydi(haber({ category: 'security', version: 'v1.34.1' }), 'kubernetes')
    expect(k.rozetler).toEqual([
      { metin: 'Güvenlik', tur: 'bilgi' },
      { metin: 'v1.34.1', tur: 'bilgi' },
    ])
  })

  it('yapisal degisiklik gunlugu okunur paragraflara donusur', () => {
    const gunluk = (aciklama1, aciklama2) => [
      '===SECTION: Changelog since v1.35.9===',
      '===SECTION: Feature===',
      '---ITEM---',
      `${aciklama1} \`kubectl\``,
      'devam satiri.',
      '<<<PR#143343|@palnabarun|SIG Release and Testing>>>',
      '---ITEM---',
      aciklama2,
      '===SECTION: Bug or Regression===',
      '---ITEM---',
      'Fixed a bug.',
      '<<<PR#142023|@troychiu|SIG Apps, SIG Node>>>',
    ].join('\n')
    const k = haberOkumaKaydi(haber({
      source: 'GitHub Releases',
      original_description: gunluk('Kubernetes is now built with Go 1.26.10', 'No PR line.'),
      turkish_description: gunluk('Kubernetes artık Go 1.26.10 ile derleniyor', 'PR satırı yok.'),
    }), 'kubernetes')
    // Ogesiz bolum basligi atlanir; isaretler (===, ---ITEM---, <<<PR>>>) metinde kalmaz
    expect(k.govdeTr.split('\n\n')).toEqual([
      'Feature (2)',
      '• Kubernetes artık Go 1.26.10 ile derleniyor `kubectl` devam satiri. (#143343 · @palnabarun · SIG Release and Testing)',
      '• PR satırı yok.',
      'Bug or Regression (1)',
      '• Fixed a bug. (#142023 · @troychiu · SIG Apps, SIG Node)',
    ])
    expect(k.govdeOrijinal.split('\n\n')[1]).toBe(
      '• Kubernetes is now built with Go 1.26.10 `kubectl` devam satiri. (#143343 · @palnabarun · SIG Release and Testing)',
    )
  })

  it('isaretsiz ya da ogesiz gunluk metne dokunulmaz', () => {
    expect(haberOkumaKaydi(haber({ turkish_description: 'Düz\n\nmetin.' }), 'kubernetes').govdeTr).toBe('Düz\n\nmetin.')
    const bos = '===SECTION: Changelog since v1.35.9==='
    expect(haberOkumaKaydi(haber({ turkish_description: bos }), 'kubernetes').govdeTr).toBe(bos)
  })

  it('devtools kayit turu ve surum bilgi rozeti olur, bos surum atlanir', () => {
    expect(haberOkumaKaydi(haber({ entry_type: 'release', version: '2.1.0' }), 'devtools').rozetler).toEqual([
      { metin: '2.1.0', tur: 'bilgi' },
      { metin: 'Sürüm', tur: 'bilgi' },
    ])
    expect(haberOkumaKaydi(haber({ entry_type: 'news', version: '' }), 'devtools').rozetler).toEqual([
      { metin: 'Haber', tur: 'bilgi' },
    ])
  })
})
