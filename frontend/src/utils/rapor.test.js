import { describe, it, expect, vi } from 'vitest'
import { raporHtml, raporKayitlariniGetir } from './rapor'

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

  it('varsayilan_ek_rozet_ceviri_durumunu_tasir', () => {
    // Haber bolumlerinin raporunda da makine cevirisi ve cevrilmemis kayit ayirt edilir
    const libre = raporHtml({ ...temel, kayitlar: [{ ...kayit, version: '', translation_provider: 'libretranslate' }] })
    expect(libre).toContain('class="ek-rozet ceviri uyari"')
    const cevrilmedi = raporHtml({ ...temel, kayitlar: [{ ...kayit, version: '', needs_translation: true, translation_provider: '' }] })
    expect(cevrilmedi).toContain('class="ek-rozet ceviri cevrilmedi"')
  })

  it('tarih_turkce_ve_baglanti_guvenli', () => {
    const html = raporHtml(temel)
    expect(html).toContain('<span class="date">30 Ekim 2026</span>')
    expect(html).toContain('href="https://ornek.test/1" target="_blank" rel="noopener noreferrer"')
    // Gecersiz adreste baglanti hic cizilmez (bos href raporun kendisini aciyordu)
    const gecersiz = raporHtml({ ...temel, kayitlar: [{ ...kayit, link: 'javascript:alert(1)' }] })
    expect(gecersiz).not.toContain('Kaynağa Git')
    expect(gecersiz).not.toContain('href=""')
  })

  it('bosluk_korunur_secenegi_girintiyi_korur', () => {
    // Kubernetes degisiklik gunlugu girintisi icin govdede white-space: pre-wrap
    expect(raporHtml({ ...temel, boslukKorunur: true })).toMatch(/\.article \.content \{[^}]*white-space: pre-wrap/)
    expect(raporHtml(temel)).not.toContain('pre-wrap')
  })
})

describe('raporKayitlariniGetir', () => {
  it('sayfalar_arasi_ayni_id_bir_kez_gelir', async () => {
    // Sayfalar arasinda yeni kayit gelince kayma ayni kaydi iki sayfada dondurur
    const yanitlar = [
      { data: { success: true, data: [{ id: 1 }, { id: 2 }], toplam: 3, sayfa_sayisi: 2 } },
      { data: { success: true, data: [{ id: 2 }, { id: 3 }], toplam: 3, sayfa_sayisi: 2 } },
    ]
    const getir = vi.fn().mockImplementation(async ({ sayfa }) => yanitlar[sayfa - 1])
    const { kayitlar, toplam } = await raporKayitlariniGetir(getir, {})
    expect(kayitlar.map(k => k.id)).toEqual([1, 2, 3])
    expect(toplam).toBe(3)
  })
})
