import { describe, it, expect } from 'vitest'
import { kacis, guvenliHref } from './html'

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
