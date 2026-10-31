// API kayitlarini okuma panelinin ortak bicimine (OkumaKaydi) donusturur (spec 2026-10-31 G5, §6).
import { kevOnekiAyir } from './okuma'
import { cveListeBasligi } from './cve'

// Ceviri KEV onekini de Turkceye cevirir ("2026-10-20 tarihinde CISA KEV kataloguna eklendi; ... ."),
// Ingilizce regex onu tanimaz. Yalniz orijinalde onek bulunduysa, metnin basindaki ve "CISA KEV katalog"
// geciren ilk cumle (en fazla 200 karakter) atilir. Tarihler "14.10.2026" bicimindeyse noktadan sonra
// bosluk gelmedigi icin cumle sonu sayilmaz.
const TR_KEV_ONEK = /^[^\n]{0,200}?CISA KEV katalo[gğ][^\n]{0,200}?\.(?:\s+|$)/i

const KATEGORI = { release: 'Sürüm', security: 'Güvenlik', feature: 'Özellik', ecosystem: 'Ekosistem', blog: 'Blog' }
const KAYIT_TURU = { release: 'Sürüm', blog: 'Blog', news: 'Haber' }

const metin = (d) => (typeof d === 'string' ? d : '')

const kayitIskeleti = (kayit) => ({
  id: kayit?.id,
  ustBaslik: null,
  baslik: '',
  skor: null,
  rozetler: [],
  govdeTr: '',
  govdeOrijinal: '',
  kevMeta: null,
  tarih: '',
  kaynak: metin(kayit?.source),
  link: metin(kayit?.link),
  ekAlanlar: [],
  referanslar: [],
  ham: kayit || {},
})

export const cveOkumaKaydi = (cve) => {
  const orijinal = kevOnekiAyir(metin(cve?.original_description))
  const tr = kevOnekiAyir(metin(cve?.turkish_description))
  const trGovde = !tr.kevEklenme && orijinal.kevEklenme ? tr.govde.replace(TR_KEV_ONEK, '') : tr.govde
  const onek = orijinal.kevEklenme ? orijinal : tr
  const kevEklenme = cve?.kev_added_date || onek.kevEklenme
  const kevMeta = kevEklenme ? { kevEklenme, sonTarih: onek.sonTarih } : null
  const kev = cve?.source === 'CISA KEV' || !!kevMeta
  const cweler = Array.isArray(cve?.cwe_ids) ? cve.cwe_ids.filter(Boolean) : []
  const urunler = metin(cve?.affected_products).trim()

  return {
    ...kayitIskeleti(cve),
    ustBaslik: cve?.cve_id || null,
    baslik: cveListeBasligi(cve) || cve?.cve_id || '',
    skor: Number.isFinite(cve?.cvss_score) ? cve.cvss_score : null,
    rozetler: [
      ...(kev ? [{ metin: 'CISA KEV', tur: 'kev' }] : []),
      ...cweler.map(c => ({ metin: String(c), tur: 'ur' })),
    ],
    govdeTr: trGovde,
    govdeOrijinal: orijinal.govde,
    kevMeta,
    tarih: metin(cve?.published_date),
    ekAlanlar: urunler ? [{ etiket: 'Etkilenen ürünler', deger: urunler }] : [],
    referanslar: Array.isArray(cve?.references) ? cve.references.filter(r => typeof r === 'string' && r) : [],
  }
}

export const haberOkumaKaydi = (kayit, bolum) => {
  const rozetler = []
  if (kayit?.category) rozetler.push({ metin: KATEGORI[kayit.category] || kayit.category, tur: 'bilgi' })
  if (kayit?.version) rozetler.push({ metin: kayit.version, tur: 'bilgi' })
  if (kayit?.entry_type) rozetler.push({ metin: KAYIT_TURU[kayit.entry_type] || kayit.entry_type, tur: 'bilgi' })

  return {
    ...kayitIskeleti(kayit),
    baslik: metin(kayit?.turkish_title) || metin(kayit?.original_title),
    rozetler,
    govdeTr: bolum === 'news'
      ? metin(kayit?.turkish_description) || metin(kayit?.turkish_summary)
      : metin(kayit?.turkish_description),
    govdeOrijinal: metin(kayit?.original_description),
    tarih: metin(bolum === 'news' ? kayit?.date : kayit?.published_date),
  }
}
