// CVE listesinde kimligin altindaki baslik (bulgu 7, 2026-10-16). API sablon basliklari
// ("CVE-x - Güvenlik Açığı") aciklamadan turetir (news/cve_basligi.py); burada "CVE-x - " oneki atilir.
// Hala sablonsa (aciklama yok) bos doner: kimligi tekrar etmekten baska bilgi tasimaz.
const SABLON = /^(Güvenlik Açığı|Aktif Sömürülen Zafiyet)$/

export const cveListeBasligi = (item) => {
  const baslik = (item?.turkish_title || item?.original_title || '').trim()
  const onek = `${item?.cve_id} - `
  const ozet = item?.cve_id && baslik.startsWith(onek) ? baslik.slice(onek.length) : baslik
  return SABLON.test(ozet) ? '' : ozet
}
