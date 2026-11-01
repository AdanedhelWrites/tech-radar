import { describe, it, expect } from 'vitest'
import { cveListeBasligi, skorSinifi } from './cve'

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

// Skor kutusu ve rozet renk sinifi (arayuz yenileme, tema.css .skor-kutusu)
describe('skorSinifi', () => {
  it('esiklerde dogru sinifi verir', () => {
    expect(skorSinifi(10)).toBe('kritik')
    expect(skorSinifi(9.0)).toBe('kritik')
    expect(skorSinifi(8.9)).toBe('yuksek')
    expect(skorSinifi(7.0)).toBe('yuksek')
    expect(skorSinifi(6.9)).toBe('orta')
    expect(skorSinifi(4.0)).toBe('orta')
    expect(skorSinifi(3.9)).toBe('')
  })

  it('skor yoksa ya da sayi degilse bos doner', () => {
    expect(skorSinifi(null)).toBe('')
    expect(skorSinifi(undefined)).toBe('')
    expect(skorSinifi(Number.NaN)).toBe('')
  })
})
