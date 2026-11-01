import { describe, it, expect } from 'vitest'
import { paragraflar, kevOnekiAyir, cevrilmemisMi, okumaIcerigi } from './okuma'

const EN_UZUN = 'The vulnerability allows an attacker to execute arbitrary code on the server.'

describe('paragraflar', () => {
  it('bos satirla boler, trim eder, bosları atar', () => {
    expect(paragraflar('  A.\n\n\n\n  B.  \n\n')).toEqual(['A.', 'B.'])
  })
  it('CRLF govdeyi de paragraflara boler', () => {
    expect(paragraflar('A.\r\n\r\nB.\r\n \r\nC.')).toEqual(['A.', 'B.', 'C.'])
  })
  it('bos ve eksik metin bos liste olur', () => {
    expect(paragraflar('')).toEqual([])
    expect(paragraflar(null)).toEqual([])
    expect(paragraflar(undefined)).toEqual([])
  })
})

describe('kevOnekiAyir', () => {
  it('kev onekini ayirir', () => expect(kevOnekiAyir('Added to the CISA KEV catalog on 2026-10-20; required action due 2026-11-10. Gövde.'))
    .toEqual({ kevEklenme: '2026-10-20', sonTarih: '2026-11-10', govde: 'Gövde.' }))
  it('son tarih olmadan da calisir', () => expect(kevOnekiAyir('Added to the CISA KEV catalog on 2026-10-20. Gövde.'))
    .toEqual({ kevEklenme: '2026-10-20', sonTarih: null, govde: 'Gövde.' }))
  it('onek yoksa ya da basta degilse metin aynen doner', () => {
    expect(kevOnekiAyir('Normal metin.')).toEqual({ kevEklenme: null, sonTarih: null, govde: 'Normal metin.' })
    const ortada = 'Giris. Added to the CISA KEV catalog on 2026-10-20. Gövde.'
    expect(kevOnekiAyir(ortada)).toEqual({ kevEklenme: null, sonTarih: null, govde: ortada })
  })
  it('bos metin guvenli', () => {
    expect(kevOnekiAyir('')).toEqual({ kevEklenme: null, sonTarih: null, govde: '' })
    expect(kevOnekiAyir(null)).toEqual({ kevEklenme: null, sonTarih: null, govde: '' })
  })
})

describe('cevrilmemisMi', () => {
  it('orijinalle ayni paragraf isaretlenir', () => expect(cevrilmemisMi(EN_UZUN, [EN_UZUN])).toBe(true))
  it('ingilizce paragraf isaretlenir', () => expect(cevrilmemisMi('An attacker could exploit the vulnerability with a crafted request.', [])).toBe(true))
  it('turkce paragraf isaretlenmez', () => expect(cevrilmemisMi('Saldırgan özel hazırlanmış bir istekle zafiyeti istismar edebilir.', [])).toBe(false))
  it('kisa paragraf isaretlenmez', () => expect(cevrilmemisMi('Apache HTTP Server 2.4.62', ['Apache HTTP Server 2.4.62'])).toBe(false))
  it('tek isaret kelimesi yetmez', () => expect(cevrilmemisMi('Apache HTTP Server 2.4.62 and newer builds are listed here.', [])).toBe(false))
  it('isaret kelimeleri butun kelime olarak aranir', () => expect(cevrilmemisMi('Theory, android, tooling, offset: nothing here matches whole words at all.', [])).toBe(false))
})

describe('okumaIcerigi', () => {
  it('ceviri yoksa orijinal gosterilir', () => {
    const s = okumaIcerigi({ govdeTr: '', govdeOrijinal: 'A.\n\nB.' })
    expect(s.tamamenCevrilmedi).toBe(true); expect(s.paragraflar.map(p => p.metin)).toEqual(['A.', 'B.'])
    expect(s.paragraflar.every(p => p.cevrilmedi === false)).toBe(true)
  })
  it('ceviri varsa paragraflar tek tek isaretlenir', () => {
    const s = okumaIcerigi({ govdeTr: `Saldırgan özel hazırlanmış bir istekle zafiyeti istismar edebilir.\n\n${EN_UZUN}`, govdeOrijinal: EN_UZUN })
    expect(s.tamamenCevrilmedi).toBe(false)
    expect(s.paragraflar.map(p => p.cevrilmedi)).toEqual([false, true])
    expect(s.orijinal).toEqual([EN_UZUN])
  })
  it('ikisi de bossa bos doner', () => {
    expect(okumaIcerigi({ govdeTr: '', govdeOrijinal: '' })).toEqual({ paragraflar: [], orijinal: [], tamamenCevrilmedi: false })
    expect(okumaIcerigi({})).toEqual({ paragraflar: [], orijinal: [], tamamenCevrilmedi: false })
  })
})
