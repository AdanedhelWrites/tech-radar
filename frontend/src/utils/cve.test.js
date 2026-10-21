import { describe, it, expect } from 'vitest'
import { cveListeBasligi } from './cve'

// Bulgu 7 (2026-10-16): CVE listesi yalniz kimligi gosteriyordu; baslik (API'de aciklamadan turetilir,
// news/cve_basligi.py) kimligin altinda, "CVE-x - " oneki atilarak gosterilir.
describe('cveListeBasligi', () => {
  it('kimlik onekini atar', () => {
    expect(cveListeBasligi({ cve_id: 'CVE-2026-1', turkish_title: 'CVE-2026-1 - Linux çekirdeği: bpf hatası' }))
      .toBe('Linux çekirdeği: bpf hatası')
  })

  it('sablon baslikta bos doner (tekrar bilgi yok)', () => {
    expect(cveListeBasligi({ cve_id: 'CVE-2026-2', turkish_title: 'CVE-2026-2 - Güvenlik Açığı' })).toBe('')
  })

  it('turkce yoksa orijinali, onek yoksa basligin tamamini kullanir', () => {
    expect(cveListeBasligi({ cve_id: 'CVE-2026-3', turkish_title: '', original_title: 'Fortinet RCE' })).toBe('Fortinet RCE')
    expect(cveListeBasligi({})).toBe('')
  })
})
