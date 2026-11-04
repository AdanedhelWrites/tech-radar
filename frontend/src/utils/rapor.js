import { kacis, kacisliParagraf, guvenliHref } from './html'

// Bolum HTML raporu (spec 2026-11-05 G4, §7): gecerli filtre ve siralamayla, sayfadan bagimsiz.
// Liste ucundan boyut=100 ile sirayla en fazla 5 sayfa (500 kayit) alinir; toplam daha buyukse
// raporun basina "Ilk 500 kayit (toplam N)" notu konur. Govde ve rozetler utils/html ile kacislanir.
// boslukKorunur: govdede white-space: pre-wrap (Kubernetes degisiklik gunlugunun girintisi).

export const RAPOR_SAYFA_BOYUTU = 100
export const RAPOR_EN_FAZLA_SAYFA = 5

const sayi = (n) => Number(n || 0).toLocaleString('tr-TR')

// getir: bolumun liste cagrisi (params) => axios yaniti; istek: useListeSorgusu'nun gecerli istegi
// (sayfa ve boyut burada ezilir). Son sayfaya varilinca durur: sunucu asiri sayfayi son sayfaya
// cektigi icin devam etmek ayni kayitlari tekrar eklerdi.
export async function raporKayitlariniGetir(getir, istek) {
  const kayitlar = []
  const goruldu = new Set()
  let toplam = 0
  for (let sayfa = 1; sayfa <= RAPOR_EN_FAZLA_SAYFA; sayfa++) {
    const { data: veri } = await getir({ ...istek, sayfa, boyut: RAPOR_SAYFA_BOYUTU })
    if (!veri?.success) throw new Error(veri?.message || 'Rapor kayıtları alınamadı')
    const sayfadakiler = veri.data || []
    // Sayfalar arasinda yeni kayit gelirse kayma ayni kaydi iki sayfada dondurur: id ile tekillestir
    for (const kayit of sayfadakiler) {
      if (!goruldu.has(kayit.id)) {
        goruldu.add(kayit.id)
        kayitlar.push(kayit)
      }
    }
    toplam = veri.toplam ?? kayitlar.length
    if (sayfadakiler.length === 0 || sayfa >= (veri.sayfa_sayisi ?? 1)) break
  }
  return { kayitlar, toplam }
}

// Varsayilanlar haber disindaki bolumlerin alanlari; Siber Guvenlik tarih/icerik'i kendisi verir
const varsayilanTarih = (k) => k.published_date || ''
const varsayilanIcerik = (k) => k.turkish_description || k.original_description || ''
// Ek rozetler ham metin dondurur: [{ metin, sinif? }] (surum; Zafiyetler'de CVE kimligi, CVSS, KEV).
// Kacis sablonda yapilir, cagiran unutamaz.
const varsayilanEkRozetler = (k) => (k.version ? [{ metin: k.version }] : [])

const rozetHtml = ({ metin, sinif = '' }) =>
  `<span class="ek-rozet${sinif ? ` ${kacis(sinif)}` : ''}">${kacis(metin)}</span>`

export function raporHtml({
  belgeBasligi, baslik, birim, aciklama = '', vurgu = '#5b86a7',
  kayitlar, toplam,
  tarih = varsayilanTarih, icerik = varsayilanIcerik, ekRozetler = varsayilanEkRozetler,
  boslukKorunur = false,
}) {
  const gun = new Date().toLocaleDateString('tr-TR')
  const kesildi = toplam > kayitlar.length
  return `<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<title>${kacis(belgeBasligi)} - ${gun}</title>
<style>
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0f; color: #e0e0e0; max-width: 960px; margin: 0 auto; padding: 2rem; }
  h1 { color: ${vurgu}; border-bottom: 2px solid #1a1a24; padding-bottom: 0.5rem; }
  .meta { color: #888; font-size: 0.85rem; margin-bottom: 2rem; }
  .not { background: #1a1a24; border-left: 3px solid ${vurgu}; padding: 0.5rem 0.75rem; margin-bottom: 1.5rem; font-size: 0.9rem; }
  .article { background: #111118; border: 1px solid #1a1a24; border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }
  .article h3 { margin: 0 0 0.5rem 0; font-size: 1.1rem; color: #e0e0e0; }
  .article .source { display: inline-block; background: ${vurgu}; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; margin-right: 0.5rem; }
  .article .ek-rozet { display: inline-block; background: #1a1a24; color: ${vurgu}; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-family: monospace; margin-right: 0.5rem; }
  .article .ek-rozet.cveid { background: transparent; padding-left: 0; font-weight: bold; font-size: 0.9rem; }
  .article .ek-rozet.kritik { background: #dc3545; color: #fff; }
  .article .ek-rozet.yuksek { background: #fd7e14; color: #fff; }
  .article .ek-rozet.orta { background: #ffc107; color: #000; }
  .article .ek-rozet.dusuk { background: #28a745; color: #fff; }
  .article .ek-rozet.skorsuz { background: #6c757d; color: #fff; }
  .article .ek-rozet.kev { background: #7a1f2b; color: #fff; }
  .article .ek-rozet.ceviri { background: #6c757d; color: #fff; font-family: inherit; }
  .article .ek-rozet.ceviri.uyari { background: #ffc107; color: #212529; }
  .article .ek-rozet.ceviri.cevrilmedi { background: #e9ecef; color: #212529; }
  .article .date { color: #888; font-size: 0.8rem; }
  .article .content { margin-top: 0.75rem; line-height: 1.7; color: #ccc;${boslukKorunur ? ' white-space: pre-wrap;' : ''} }
  .article a { color: ${vurgu}; text-decoration: none; }
  .article a:hover { text-decoration: underline; }
  @media print { body { background: #fff; color: #000; } .article { border-color: #ddd; background: #f9f9f9; } .article h3, .article .content { color: #000; } h1 { color: #333; } }
</style>
</head>
<body>
<h1>${kacis(baslik)}</h1>
<p class="meta">${gun} tarihinde oluşturuldu &mdash; ${sayi(kayitlar.length)} ${kacis(birim)}${aciklama ? ` &mdash; ${kacis(aciklama)}` : ''}</p>
${kesildi ? `<p class="not">İlk ${sayi(kayitlar.length)} kayıt (toplam ${sayi(toplam)})</p>\n` : ''}${kayitlar.map(item => `<div class="article">
  <span class="source">${kacis(item.source || '')}</span>${ekRozetler(item).map(rozetHtml).join('')}<span class="date">${kacis(tarih(item))}</span>
  <h3>${kacis(item.turkish_title || item.original_title || '')}</h3>
  <div class="content">${kacisliParagraf(icerik(item))}</div>
  <a href="${guvenliHref(item.link)}" target="_blank">Kaynağa Git &rarr;</a>
</div>`).join('\n')}
</body></html>`
}

// Raporu dosya olarak indirir: <dosyaOnEki>_YYYY-AA-GG.html
export function raporIndir(html, dosyaOnEki) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${dosyaOnEki}_${new Date().toISOString().split('T')[0]}.html`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
