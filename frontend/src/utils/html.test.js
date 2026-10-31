import { describe, it, expect } from 'vitest'
import { kacis, kacisliParagraf, guvenliHref } from './html'

describe('kacis', () => {
  it('bes HTML karakterini kacislar', () => {
    expect(kacis('<script>alert("x") & \'y\'</script>'))
      .toBe('&lt;script&gt;alert(&quot;x&quot;) &amp; &#39;y&#39;&lt;/script&gt;')
  })
  it('null ve undefined bos dize olur', () => {
    expect(kacis(null)).toBe('')
    expect(kacis(undefined)).toBe('')
  })
  it('sayi dizeye cevrilir, duz metin degismez', () => {
    expect(kacis(42)).toBe('42')
    expect(kacis('CVE-2026-1234 kritik')).toBe('CVE-2026-1234 kritik')
  })
})

describe('kacisliParagraf', () => {
  it('script ve img onerror kacislanir, satir sonlari <br> olur', () => {
    const sonuc = kacisliParagraf('<script>alert(1)</script>\nikinci <img src=x onerror="alert(2)">\r\nucuncu')
    expect(sonuc).toBe(
      '&lt;script&gt;alert(1)&lt;/script&gt;<br>ikinci &lt;img src=x onerror=&quot;alert(2)&quot;&gt;<br>ucuncu',
    )
    expect(sonuc).not.toMatch(/<script|<img/i)
  })
  it('govdedeki hazir <br> etiketi de kacislanir', () => {
    expect(kacisliParagraf('a<br>b')).toBe('a&lt;br&gt;b')
  })
  it('null ve undefined bos dize olur', () => {
    expect(kacisliParagraf(null)).toBe('')
    expect(kacisliParagraf(undefined)).toBe('')
  })
})

describe('guvenliHref', () => {
  it('http ve https kabul edilir ve kacislanir', () => {
    expect(guvenliHref('https://ornek.test/a?b=1&c=2')).toBe('https://ornek.test/a?b=1&amp;c=2')
    expect(guvenliHref('HTTP://ornek.test')).toBe('HTTP://ornek.test')
  })
  it('javascript:, data:, goreli ve bos deger bos dize olur', () => {
    expect(guvenliHref('javascript:alert(1)')).toBe('')
    expect(guvenliHref('data:text/html,x')).toBe('')
    expect(guvenliHref('/yerel/yol')).toBe('')
    expect(guvenliHref('')).toBe('')
    expect(guvenliHref(undefined)).toBe('')
  })
})
