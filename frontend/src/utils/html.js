// HTML rapor disa aktarimi icin kacis (2026-10-08). Rapor sablon dizesiyle uretilip
// indirilir ve file:// kaynaginda acilir; ucuncu taraf feed'den gelen baslik/govde
// kacislanmadan yazilirsa icindeki <script> kullanicinin tarayicisinda calisirdi.
const KARSILIK = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

export const kacis = (deger) => String(deger ?? '').replace(/[&<>"']/g, (c) => KARSILIK[c])

// href icin: yalniz http(s) kabul, digerleri (javascript:, data:) bos kalir
export const guvenliHref = (url) => (/^https?:\/\//i.test(String(url ?? '')) ? kacis(url) : '')
