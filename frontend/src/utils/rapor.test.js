import { describe, it, expect } from 'vitest'
import { raporHtml } from './rapor'

const kayit = {
  id: 1,
  source: 'Kaynak',
  version: 'v1.0<b>',
  turkish_title: 'Başlık',
  turkish_description: 'satir 1\n  - girintili madde',
  link: 'https://ornek.test/1',
  published_date: '2026-10-30',
}

const temel = { belgeBasligi: 'Rapor', baslik: 'Rapor', birim: 'kayıt', kayitlar: [kayit], toplam: 1 }

describe('raporHtml', () => {
  it('ek_rozet_sablonda_kacislanir', () => {
    // Cagiran ham metin verir; kacis sablonun isi (unutulamaz)
    const html = raporHtml({
      ...temel,
      ekRozetler: () => [{ metin: '<script>alert(1)</script>', sinif: 'kev" onclick="x' }, { metin: 'CVSS 9.8' }],
    })
    expect(html).not.toMatch(/<script/i)
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).toContain('class="ek-rozet kev&quot; onclick=&quot;x"')
    expect(html).toContain('<span class="ek-rozet">CVSS 9.8</span>')
  })

  it('varsayilan_ek_rozet_surumdur', () => {
    const html = raporHtml(temel)
    expect(html).toContain('<span class="ek-rozet">v1.0&lt;b&gt;</span>')
    expect(raporHtml({ ...temel, kayitlar: [{ ...kayit, version: '' }] })).not.toContain('class="ek-rozet')
  })

  it('bosluk_korunur_secenegi_girintiyi_korur', () => {
    // Kubernetes degisiklik gunlugu girintisi icin govdede white-space: pre-wrap
    expect(raporHtml({ ...temel, boslukKorunur: true })).toMatch(/\.article \.content \{[^}]*white-space: pre-wrap/)
    expect(raporHtml(temel)).not.toContain('pre-wrap')
  })
})
