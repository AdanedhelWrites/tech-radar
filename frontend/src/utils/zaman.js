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
