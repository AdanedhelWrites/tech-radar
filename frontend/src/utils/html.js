// HTML rapor disa aktarimi icin kacis (2026-10-08). Rapor sablon dizesiyle uretilip
// indirilir ve file:// kaynaginda acilir; ucuncu taraf feed'den gelen baslik/govde
// kacislanmadan yazilirsa icindeki <script> kullanicinin tarayicisinda calisirdi.
const KARSILIK = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

export const kacis = (deger) => String(deger ?? '').replace(/[&<>"']/g, (c) => KARSILIK[c])

// Rapor govdesi icin: once kacis, sonra satir sonu -> <br>. Sira ters olursa ya <br>
// de kacislanir ya da govde ham kalir (2026-10-31 oncesi alti raporda govde hamdi).
export const kacisliParagraf = (deger) => kacis(deger).replace(/\r?\n/g, '<br>')

// href icin: yalniz http(s) kabul, digerleri (javascript:, data:) bos kalir
export const guvenliHref = (url) => (/^https?:\/\//i.test(String(url ?? '')) ? kacis(url) : '')
