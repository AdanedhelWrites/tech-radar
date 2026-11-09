// ISO zamani "15 dk önce" gibi goreli metne cevirir (saglik seridi). Bos/bozuk/gelecek deger: '-'.
export const goreliZaman = (iso, simdi = Date.now()) => {
  if (!iso) return '-'
  const fark = Math.floor((simdi - Date.parse(iso)) / 1000)
  if (Number.isNaN(fark) || fark < 0) return '-'
  if (fark < 60) return 'az önce'
  if (fark < 3600) return `${Math.floor(fark / 60)} dk önce`
  if (fark < 86400) return `${Math.floor(fark / 3600)} sa önce`
  if (fark < 172800) return 'dün'
  return `${Math.floor(fark / 86400)} gün önce`
}

// "2026-11-05" ya da "2026-11-05T10:00:00Z" -> "5 Kasım 2026" (okuma paneli ve HTML rapor; 2026-11-09).
// Once ham ISO yaziliyordu, liste goreli zaman, raporun ust satiri tr-TR: tek bicim. Yalniz gun kismi
// okunur (saat dilimi gunu kaydirmasin). ISO olmayan metin (eski kayitlarin original_date'i) aynen doner.
const ISO_GUN = /^(\d{4})-(\d{2})-(\d{2})(?:$|[T ])/
export const tarihBicimle = (deger) => {
  const metin = typeof deger === 'string' ? deger.trim() : ''
  const eslesme = ISO_GUN.exec(metin)
  if (!eslesme) return metin
  const [, yil, ay, gun] = eslesme.map(Number)
  const tarih = new Date(yil, ay - 1, gun)
  if (tarih.getMonth() !== ay - 1) return metin
  return tarih.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' })
}
