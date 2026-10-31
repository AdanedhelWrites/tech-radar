// API kayitlarini okuma panelinin ortak bicimine (OkumaKaydi) donusturur (spec 2026-10-31 G5, §6).
import { kevOnekiAyir } from './okuma'
import { cveListeBasligi } from './cve'

// Ceviri KEV onekini de Turkceye cevirir ("2026-10-20 tarihinde CISA KEV kataloguna eklendi; ... ."),
// Ingilizce regex onu tanimaz. Yalniz orijinalde onek bulunduysa ve metnin ILK cumlesi hem "CISA KEV
// katalog" hem bir tarih iceriyorsa o cumle atilir; sonraki cumlelere hic dokunulmaz. Cumle sonu =
// ardindan bosluk ya da metin sonu gelen nokta; "14.10.2026" gibi tarihlerdeki noktalar sayilmaz.
const ILK_CUMLE = /^[^\n]{0,250}?\.(?:\s+|$)/
const KEV_ANMA = /CISA KEV katalo[gğ]/i
const TARIH = /\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4}|\d{1,2} (?:Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık) \d{4}/i

const trKevOnekiAt = (govde) => {
  const cumle = ILK_CUMLE.exec(govde)?.[0]
  return cumle && KEV_ANMA.test(cumle) && TARIH.test(cumle) ? govde.slice(cumle.length) : govde
}

// Kubernetes kategori ve DevTools kayit turu etiketleri: bolum sayfalari da buradan okur (tek kaynak)
export const KATEGORI = { release: 'Sürüm', security: 'Güvenlik', feature: 'Özellik', ecosystem: 'Ekosistem', blog: 'Blog' }
export const KAYIT_TURU = { release: 'Sürüm', blog: 'Blog', news: 'Haber' }

const metin = (d) => (typeof d === 'string' ? d : '')

// Kubernetes GitHub Releases govdesi yapisal degisiklik gunlugudur (news/k8s_scraper):
// "===SECTION: Ad===", "---ITEM---", aciklama satirlari, "<<<PR#123|@yazar|SIG ...>>>".
// Okuma paneli duz paragraf gosterir; gunluk "Ad (n)" basligi ve "• aciklama (#123 · @yazar · SIG)"
// paragraflarina cevrilir. Ogesiz bolumler ("Changelog since v1.x") eski gorunumdeki gibi atlanir.
// Turkce ve orijinal ayni bicime cevrildigi icin paragraf sezgisi oge bazinda calisir.
const GUNLUK_BOLUMU = /^===SECTION:\s*(.+)===$/
const GUNLUK_PR = /^<<<PR#(\d+)\|@([\w-]+)\|(.+)>>>$/

const degisiklikGunlugu = (govde) => {
  if (!govde.includes('===SECTION:')) return govde
  const bolumler = []
  let bolum = null
  let oge = null
  const ogeyiKapat = () => {
    if (oge?.aciklama && bolum) bolum.ogeler.push(oge)
    oge = null
  }
  for (const satir of govde.split('\n').map(s => s.trim())) {
    const baslik = GUNLUK_BOLUMU.exec(satir)
    const pr = GUNLUK_PR.exec(satir)
    if (baslik) {
      ogeyiKapat()
      bolum = { ad: baslik[1].trim(), ogeler: [] }
      bolumler.push(bolum)
    } else if (satir === '---ITEM---') {
      ogeyiKapat()
      oge = { aciklama: '', pr: null }
    } else if (pr) {
      if (oge) oge.pr = `#${pr[1]} · @${pr[2]} · ${pr[3].trim()}`
    } else if (satir) {
      oge ??= { aciklama: '', pr: null }
      oge.aciklama = oge.aciklama ? `${oge.aciklama} ${satir}` : satir
    }
  }
  ogeyiKapat()
  const paragraflar = bolumler.filter(b => b.ogeler.length > 0).flatMap(b => [
    `${b.ad} (${b.ogeler.length})`,
    ...b.ogeler.map(o => `• ${o.aciklama}${o.pr ? ` (${o.pr})` : ''}`),
  ])
  return paragraflar.length > 0 ? paragraflar.join('\n\n') : govde
}

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
  const trGovde = !tr.kevEklenme && orijinal.kevEklenme ? trKevOnekiAt(tr.govde) : tr.govde
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
    govdeTr: degisiklikGunlugu(bolum === 'news'
      ? metin(kayit?.turkish_description) || metin(kayit?.turkish_summary)
      : metin(kayit?.turkish_description)),
    govdeOrijinal: degisiklikGunlugu(metin(kayit?.original_description)),
    tarih: metin(bolum === 'news' ? kayit?.date : kayit?.published_date),
  }
}
